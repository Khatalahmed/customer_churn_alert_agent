"""
retrain.py

WHAT : Decides whether to retrain, by measuring whether retraining actually
       helps - then promotes the refreshed model only if it does.
WHY   : "Retrain monthly" is a habit, not a decision. Retraining costs
       nothing here but it is not free of risk: a model refit on a noisy
       recent period can be worse than the one you had. So this backtests two
       policies over the history we have - a model trained once and never
       refreshed, versus one refreshed at every cutoff - and compares them on
       snapshots neither had seen.
FLOW  : for each snapshot after the first two: train STALE (earliest snapshot
        only) and FRESH (everything before this point), score the snapshot,
        compare PR-AUC -> if FRESH wins on average, retrain on all labelled
        data and save; otherwise keep the champion.
LOGIC: PR-AUC, not ROC-AUC: at a ~1.4% base rate ROC-AUC barely moves and
       would make every policy look identical.
NOTE : a champion-vs-challenger bake-off needs a snapshot newer than the one
       the champion trained on. The newest labelled snapshot IS the
       champion's test set, so this backtest is the honest version of that
       question given the data we have.
"""
import joblib
import pandas as pd

from .config import PRODUCTION_MODEL_PATH, TEST_CUTOFF_DAYS, TRAIN_CUTOFFS_DAYS
from .features import build_snapshots
from .metrics import pr_auc
from .train_model import calibrate, make_model


def _fit(frames, cols):
    train = pd.concat(frames, ignore_index=True)
    model = make_model(train["churned"])
    model.fit(train[cols], train["churned"])
    return model


def backtest_retraining(cutoffs=None) -> pd.DataFrame:
    """PR-AUC per snapshot for a stale model vs one refreshed each period."""
    cutoffs = cutoffs or list(TRAIN_CUTOFFS_DAYS) + [TEST_CUTOFF_DAYS]
    snaps, cols = [], None
    for days in cutoffs:
        snap, cols = build_snapshots([days])
        if len(snap) and snap["churned"].sum() > 0:
            snaps.append(snap)

    rows = []
    for i in range(2, len(snaps)):
        test = snaps[i]
        stale = _fit(snaps[:1], cols)          # trained once, never refreshed
        fresh = _fit(snaps[:i], cols)          # refreshed with everything since
        rows.append({
            "tested_at": test["as_of"].iloc[0][:10],
            "churn": int(test["churned"].sum()),
            "stale": pr_auc(test["churned"], stale.predict_proba(test[cols])[:, 1]),
            "fresh": pr_auc(test["churned"], fresh.predict_proba(test[cols])[:, 1]),
        })
    return pd.DataFrame(rows)


def promote(cutoffs=None, path=PRODUCTION_MODEL_PATH) -> dict:
    """Retrain on ALL labelled snapshots and save as the production model.

    Deliberately NOT churn_model.pkl. This model has seen the snapshot every
    reported metric is measured on, so scoring with it would quietly turn
    those numbers in-sample - the exact trap this project spent a day
    escaping. The evaluated model stays where it is; production gets the
    model trained on everything, as it should.
    """
    cutoffs = cutoffs or list(TRAIN_CUTOFFS_DAYS) + [TEST_CUTOFF_DAYS]
    train, cols = build_snapshots(cutoffs)
    X, y, groups = train[cols], train["churned"], train["user_id"]
    model = make_model(y)
    model.fit(X, y)
    calibrated = calibrate(make_model(y), X, y, groups)
    joblib.dump({"model": calibrated, "tree_model": model, "features": cols,
                 "trained_on_cutoffs_days": list(cutoffs), "evaluation_safe": False}, path)
    return {"rows": len(train), "churn": int(y.sum()), "cutoffs": list(cutoffs), "path": path}


def main():
    table = backtest_retraining()
    stale, fresh = table["stale"].mean(), table["fresh"].mean()

    print("=" * 70)
    print("RETRAINING POLICY  (PR-AUC per snapshot, neither model had seen it)")
    print("=" * 70)
    print(f"{'tested at':<14}{'churn':>7}{'stale':>9}{'refreshed':>11}")
    for _, r in table.iterrows():
        print(f"{r['tested_at']:<14}{int(r['churn']):>7}{r['stale']:>9.3f}{r['fresh']:>11.3f}")
    print("-" * 70)
    print(f"{'mean':<14}{'':>7}{stale:>9.3f}{fresh:>11.3f}")

    if fresh > stale:
        print(f"\nRefreshing wins (+{fresh - stale:.3f} PR-AUC) -> retraining on all "
              f"labelled snapshots and promoting.")
        info = promote()
        print(f"Saved model trained on {info['rows']} rows, {info['churn']} churn events, "
              f"cutoffs {info['cutoffs']}")
        print(f"  -> {info['path']}")
        print("  (churn_model.pkl is untouched: this one has seen the test snapshot,")
        print("   so reporting metrics with it would be in-sample)")
    else:
        print(f"\nRefreshing does NOT help ({fresh - stale:+.3f} PR-AUC) -> keeping the "
              f"current model. Retraining on a habit would have made this worse.")
    print("=" * 70)


if __name__ == "__main__":
    main()
