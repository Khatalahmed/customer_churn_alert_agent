"""
metrics.py

WHAT : The measurements this project reports: precision/recall at K, PR-AUC,
       Brier score, and a calibration table.
WHY  : With a 1.4% churn rate, ROC-AUC flatters everything - it averages over
       thresholds nobody would ever use. PR-AUC is the honest summary (its
       floor is the base rate, not 0.5), and precision@K is what the product
       actually delivers, because the agent only investigates K customers.
       Calibration matters separately: a "0.9" should mean nine times out of
       ten, or any expected-value calculation built on it is fiction.
"""
import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss


def precision_at_k(y, score, k: int) -> float:
    """Share of real churners among the k highest-scored customers."""
    top = np.argsort(-np.asarray(score))[:k]
    return float(np.asarray(y)[top].mean())


def recall_at_k(y, score, k: int) -> float:
    """Share of all churners that the k highest-scored customers capture."""
    y = np.asarray(y)
    if y.sum() == 0:
        return 0.0
    top = np.argsort(-np.asarray(score))[:k]
    return float(y[top].sum() / y.sum())


def pr_auc(y, score) -> float:
    """Average precision. Floor is the base rate, not 0.5 - unlike ROC-AUC."""
    return float(average_precision_score(y, score))


def brier(y, proba) -> float:
    """Mean squared error of the probabilities. Lower is better; only
    meaningful for calibrated scores."""
    return float(brier_score_loss(y, proba))


def calibration_table(y, proba, bins: int = 5, strategy: str = "quantile") -> list[dict]:
    """Predicted vs observed churn rate, in bins of predicted probability.

    A calibrated model has predicted ~= observed in every row. Default bins are
    QUANTILES: with a 1.4% base rate every prediction sits in the bottom
    equal-width bucket, which tells you nothing. Pass strategy="width" for
    equal-width bins. Empty bins are skipped.
    """
    y = np.asarray(y)
    proba = np.asarray(proba)
    if strategy == "quantile":
        edges = np.unique(np.quantile(proba, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = 0.0, 1.0
    else:
        edges = np.linspace(0, 1, bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (proba >= lo) & (proba < hi if hi < 1 else proba <= hi)
        if not mask.any():
            continue
        rows.append({
            "bucket": f"{lo:.3f}-{hi:.3f}",
            "n": int(mask.sum()),
            "predicted": float(proba[mask].mean()),
            "observed": float(y[mask].mean()),
        })
    return rows
