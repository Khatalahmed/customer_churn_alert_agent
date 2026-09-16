"""
train_model.py

WHAT : Trains XGBoost to predict who stops being active in the next 14 days,
       using point-in-time snapshots, and reports honest metrics.
WHY  : Training and testing on the same moment in time hides how a model
       behaves on the future. Here the model trains on earlier snapshots and
       is tested on a LATER one whose labels start where the training labels
       end - the way it would actually be used.
FLOW : training snapshots (70, 56, 42 days back) -> grouped cross-validation
       (a customer never appears in both train and validation folds) ->
       fit on all training snapshots -> out-of-time test on the 28-day
       snapshot: AUC and precision at the top of the ranking -> save model.
LOGIC: churn in a 14-day window is rare (~5-10% of active customers), so
       scale_pos_weight stops the model from predicting "everyone stays".
       Precision@15 matters most: the agent only investigates the top 15.
NOTE : make_model() and grouped_cv_aucs() are importable; training only runs
       when this file is executed.
"""
import joblib
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

from .config import HORIZON_DAYS, MODEL_PATH, TEST_CUTOFF_DAYS, TRAIN_CUTOFFS_DAYS
from .features import build_snapshots


def make_model(y_train) -> XGBClassifier:
    """The one XGBoost config, weighted for the churn rate in y_train."""
    # churn is rare -> weight the positive class so the model takes it seriously
    pos = int(y_train.sum())
    neg = len(y_train) - pos
    return XGBClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=neg / pos,
        eval_metric="logloss",
        random_state=42,
    )


def grouped_cv_aucs(X, y, groups, n_folds: int = 5, seed: int = 42) -> list[float]:
    """AUC per fold, with every customer's rows kept in a single fold."""
    aucs = []
    folds = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for train_idx, val_idx in folds.split(X, y, groups):
        model = make_model(y.iloc[train_idx])
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        aucs.append(roc_auc_score(y.iloc[val_idx], model.predict_proba(X.iloc[val_idx])[:, 1]))
    return aucs


def precision_at_k(y, proba, k: int) -> float:
    """Share of real churners among the k highest-scored customers."""
    top = np.argsort(-np.asarray(proba))[:k]
    return float(np.asarray(y)[top].mean())


if __name__ == "__main__":
    train, cols = build_snapshots(TRAIN_CUTOFFS_DAYS)
    test, _ = build_snapshots([TEST_CUTOFF_DAYS])

    print("=" * 64)
    print(f"POINT-IN-TIME CHURN MODEL  (predict: stops being active in the next {HORIZON_DAYS} days)")
    print("=" * 64)
    for name, snap in (("train", train), ("test", test)):
        for as_of, g in snap.groupby("as_of"):
            print(f"  {name:<5} cutoff {as_of}  active={len(g):>3}  churn in horizon={int(g['churned'].sum()):>2}")

    # --- grouped cross-validation on the training snapshots ---
    aucs = grouped_cv_aucs(train[cols], train["churned"], train["user_id"])
    print(f"\nGrouped 5-fold CV AUC (train snapshots): {np.mean(aucs):.3f} +/- {np.std(aucs):.3f}"
          f"  (folds: {', '.join(f'{a:.2f}' for a in aucs)})")

    # --- fit on all training snapshots, test on the later held-out snapshot ---
    model = make_model(train["churned"])
    model.fit(train[cols], train["churned"])
    proba = model.predict_proba(test[cols])[:, 1]
    y_test = test["churned"]
    base_rate = y_test.mean()

    print(f"\nOUT-OF-TIME TEST  (cutoff {test['as_of'].iloc[0]}, {len(test)} active customers, "
          f"{int(y_test.sum())} churn)")
    print(f"ROC-AUC:        {roc_auc_score(y_test, proba):.3f}")
    print(f"Base rate:      {base_rate:.1%}  (precision of picking customers at random)")
    for k in (15, 30):
        p = precision_at_k(y_test, proba, k)
        print(f"Precision@{k:<3}   {p:.2f}  ({round(p * k)}/{k}, {p / base_rate:.1f}x random)")

    print("\nFeature importance (higher = more useful to the model):")
    for name, imp in sorted(zip(cols, model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name:<26} {imp:.3f}")

    # the saved model never saw the test snapshot, so agent eval on it stays honest
    joblib.dump({
        "model": model,
        "features": cols,
        "horizon_days": HORIZON_DAYS,
        "train_cutoffs_days": list(TRAIN_CUTOFFS_DAYS),
        "test_cutoff_days": TEST_CUTOFF_DAYS,
    }, MODEL_PATH)
    print(f"\nSaved model to {MODEL_PATH}")
