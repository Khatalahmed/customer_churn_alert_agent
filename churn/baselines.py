"""
baselines.py

WHAT : Compares the XGBoost model against the simple things a team would try
       first: picking at random, a dormancy rule ("no orders in N days"), a
       login-drop rule, and logistic regression. Same snapshots, same
       held-out test, same metrics.
WHY  : "We used XGBoost" is not a result. A model only earns its place if it
       beats the obvious rule. This is the comparison that says whether the
       ML layer is worth having at all.
FLOW : training snapshots -> fit logistic regression and XGBoost -> score the
       held-out later snapshot with every method -> AUC, precision@15,
       recall@15 and lift over the base rate.
LOGIC: precision@15 matters most: the agent only investigates 15 customers,
       so what counts is how many of the top 15 really churn.
"""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .config import TEST_CUTOFF_DAYS, TRAIN_CUTOFFS_DAYS
from .features import build_snapshots
from .metrics import pr_auc, precision_at_k
from .train_model import make_model

TOP_K = 15


def dormancy_score(df: pd.DataFrame) -> np.ndarray:
    """Rank by days since the last order - the classic "gone quiet" rule."""
    return df["days_since_last_order"].fillna(999).to_numpy()


def login_drop_score(df: pd.DataFrame) -> np.ndarray:
    """Rank by the fall in logins: earlier fortnight minus the recent one."""
    return (df["logins_prev_14_28d"] - df["logins_last_14d"]).to_numpy()


def logistic_pipeline() -> object:
    """Logistic regression needs imputing and scaling; XGBoost does not."""
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )


def evaluate(y, score, k: int = TOP_K) -> dict:
    """AUC, precision@k, recall@k and lift over the base rate."""
    y = np.asarray(y)
    base = y.mean()
    precision = precision_at_k(y, score, k)
    top = np.argsort(-np.asarray(score))[:k]
    return {
        "auc": roc_auc_score(y, score),
        "pr_auc": pr_auc(y, score),
        f"precision@{k}": precision,
        f"recall@{k}": y[top].sum() / y.sum(),
        "lift": precision / base,
    }


def compare(train: pd.DataFrame, test: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """One row per method, scored on the held-out snapshot."""
    y_train, y_test = train["churned"], test["churned"]

    logreg = logistic_pipeline().fit(train[cols], y_train)
    xgb = make_model(y_train).fit(train[cols], y_train)

    scores = {
        "dormancy rule (days since last order)": dormancy_score(test),
        "login drop (prev 14d - last 14d)": login_drop_score(test),
        "logistic regression": logreg.predict_proba(test[cols])[:, 1],
        "XGBoost (this project)": xgb.predict_proba(test[cols])[:, 1],
    }
    rows = {name: evaluate(y_test, s) for name, s in scores.items()}
    return pd.DataFrame(rows).T


def rolling_comparison(cutoffs) -> pd.DataFrame:
    """Walk forward: train on earlier cutoffs, test on the next one.

    One held-out snapshot has ~16 churners, so a single precision@15 moves by
    7 points per customer. Repeating the comparison at every cutoff shows
    whether a method is really ahead or just lucky once.
    """
    frames = []
    for i in range(1, len(cutoffs)):
        train, cols = build_snapshots(cutoffs[:i])
        test, _ = build_snapshots([cutoffs[i]])
        if test["churned"].sum() == 0 or train["churned"].sum() == 0:
            continue
        table = compare(train, test, cols)
        table["tested_at"] = test["as_of"].iloc[0][:10]
        frames.append(table.reset_index(names="method"))
    return pd.concat(frames, ignore_index=True)


def main():
    train, cols = build_snapshots(TRAIN_CUTOFFS_DAYS)
    test, _ = build_snapshots([TEST_CUTOFF_DAYS])
    base = test["churned"].mean()

    table = compare(train, test, cols)

    print("=" * 78)
    print(f"BASELINE COMPARISON  (held-out snapshot {test['as_of'].iloc[0]}, "
          f"{len(test)} active, {int(test['churned'].sum())} churn)")
    print("=" * 78)
    print(f"{'method':<40}{'AUC':>7}{'PR-AUC':>8}{'prec@15':>9}{'recall@15':>11}{'lift':>7}")
    print("-" * 78)
    print(f"{'pick at random':<40}{0.5:>7.2f}{base:>8.3f}{base:>9.2f}"
          f"{TOP_K / len(test):>11.2f}{1.0:>7.1f}x")
    for name, r in table.iterrows():
        print(f"{name:<40}{r['auc']:>7.2f}{r['pr_auc']:>8.3f}{r[f'precision@{TOP_K}']:>9.2f}"
              f"{r[f'recall@{TOP_K}']:>11.2f}{r['lift']:>6.1f}x")
    print("=" * 78)

    # the dormancy rule as a yes/no flag, the way a team would actually run it
    flagged = test["days_since_last_order"].fillna(999) >= 14
    if flagged.any():
        hits = int(test.loc[flagged, "churned"].sum())
        print(f'Rule "no orders in 14 days" as a flag: {int(flagged.sum())} customers flagged, '
              f"{hits} churn -> precision {hits / flagged.sum():.2f}, "
              f"recall {hits / test['churned'].sum():.2f}")
    print(f"(base rate {base:.1%} - the precision of picking customers at random)")

    # --- the same comparison at every cutoff, not just the last one ---
    cutoffs = list(TRAIN_CUTOFFS_DAYS) + [TEST_CUTOFF_DAYS]
    rolling = rolling_comparison(cutoffs)
    print(chr(10) + "=" * 78)
    print(f"WALK-FORWARD: same comparison at {rolling['tested_at'].nunique()} cutoffs "
          f"(train on everything earlier)")
    print("=" * 78)
    pivot = rolling.pivot(index="method", columns="tested_at", values=f"precision@{TOP_K}")
    pivot["mean"] = pivot.mean(axis=1)
    print("precision@15 by test date:")
    print(pivot.round(2).to_string())
    auc = rolling.pivot(index="method", columns="tested_at", values="auc")
    auc["mean"] = auc.mean(axis=1)
    print(chr(10) + "AUC by test date:")
    print(auc.round(2).to_string())


if __name__ == "__main__":
    main()
