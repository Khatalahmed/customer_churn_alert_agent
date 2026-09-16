"""
metrics.py

WHAT : The measurements this project reports, in three categories:
       ML model quality, calibration quality, and ranking quality.

WHAT IT MEASURES (ML model quality)
  PR-AUC       The area under the precision-recall curve. Floor is the base
               rate (~1.4%), not 0.5, which is why we report it instead of
               ROC-AUC. A perfect model scores 1.0; random scores ~0.014.
  Precision@K  Share of real churners among the top-K customers by score.
               This is what the product actually delivers, because the agent
               only investigates K customers.
  AP@K         Mean precision at every position where a churner appears in
               the top K.  Less noisy than a single threshold metric.
  Bootstrap CI 95% confidence interval on Precision@K by resampling; shows
               how much one result could move at this sample size.

WHAT IT MEASURES (calibration quality)
  Brier score  Mean squared error of the probabilities.  Only meaningful for
               calibrated scores; a lower number is better.
  ECE          Expected Calibration Error: probability-weighted average of
               |predicted - observed| across bins.  Zero is perfect.
  Calibration  A table of (bin, mean predicted, observed rate, n).
  curve data   Same but formatted for plotting (predicted on x, observed on
               y, identity line = perfect calibration).

WHAT IT DOES NOT MEASURE
  - Whether the model's scores CAUSE churn.  These metrics only say whether
    the scores RANK customers correctly, not why.
  - Fairness, subgroup performance, or temporal stability (see drift.py).
  - Whether the intervention uplift values in actions.py are correct
    (they are ASSUMED; see the uplift_source field on each intervention).

WHEN TO UPDATE
  Re-run `python -m churn.train_model` after any change to features.py,
  labels.py, or the XGBoost hyperparameters.  The metrics are saved to
  model_metrics.json; the UI reads that file directly.
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


def average_precision_at_k(y, score, k: int) -> float:
    """Mean precision at each rank where a churner lands in the top K.

    Unlike precision_at_k (a single snapshot at rank K), this rewards the
    model for ranking churners earlier: two churners at positions 1 and 2
    score higher than two at positions K-1 and K, even though precision@K
    is the same for both. Useful when K >> number of churners.
    """
    y = np.asarray(y)
    score = np.asarray(score)
    order = np.argsort(-score)[:k]
    hits, running = 0, 0.0
    for rank, idx in enumerate(order, start=1):
        if y[idx] == 1:
            hits += 1
            running += hits / rank
    return float(running / hits) if hits else 0.0


def precision_at_k_bootstrap_ci(
    y, score, k: int, n_boot: int = 1000, seed: int = 42
) -> tuple[float, float]:
    """95% bootstrap confidence interval for Precision@K.

    At n=35 churners each customer is ~3 pp, so a point estimate can move
    by 6 pp in either direction just by luck. This interval shows how much
    the reported number could plausibly move at the current sample size.

    Returns (low, high) as fractions (not percentages).
    """
    rng = np.random.RandomState(seed)
    y = np.asarray(y)
    score = np.asarray(score)
    n = len(y)
    if n == 0:
        return (0.0, 0.0)
    # Resample rows as pairs.  Sampling y and score with separate index arrays
    # silently breaks their relationship and produces an interval for random
    # labels against random scores, not uncertainty in this ranking.
    estimates = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, size=n)
        estimates.append(precision_at_k(y[idx], score[idx], k))
    estimates.sort()
    return (round(estimates[int(n_boot * 0.025)], 4),
            round(estimates[int(n_boot * 0.975)], 4))


def pr_auc(y, score) -> float:
    """Average precision. Floor is the base rate, not 0.5 - unlike ROC-AUC."""
    return float(average_precision_score(y, score))


def brier(y, proba) -> float:
    """Mean squared error of the probabilities. Lower is better; only
    meaningful for calibrated scores."""
    return float(brier_score_loss(y, proba))


def ece(y, proba, bins: int = 10) -> float:
    """Expected Calibration Error: probability-weighted |predicted - observed|.

    ECE = sum_b (n_b / N) * |predicted_b - observed_b|

    Zero means the model is perfectly calibrated. Unlike Brier score, ECE is
    not penalised for low predicted probabilities that happen to also be low
    observed rates; it is purely about the gap between what the model says and
    what happened. Uses equal-width bins so calibration is measured where
    predictions live, not forced into equal population groups.
    """
    y = np.asarray(y, dtype=float)
    proba = np.asarray(proba, dtype=float)
    n = len(y)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (proba >= lo) & (proba < hi if hi < 1.0 else proba <= hi)
        if not mask.any():
            continue
        n_b = mask.sum()
        total += (n_b / n) * abs(proba[mask].mean() - y[mask].mean())
    return float(total)


def calibration_curve_data(y, proba, n_bins: int = 10) -> list[dict]:
    """Predicted vs observed churn rate in equal-width bins, for plotting.

    Returns a list of dicts with keys:
      bin_centre  midpoint of the predicted-probability bin
      predicted   mean predicted probability in the bin
      observed    actual churn rate in the bin
      n           number of customers in the bin

    The identity line (predicted == observed) represents perfect calibration.
    Empty bins are omitted. Use calibration_table() (quantile strategy) for
    the dense-population table view; this one is for the calibration curve.
    """
    y = np.asarray(y, dtype=float)
    proba = np.asarray(proba, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (proba >= lo) & (proba < hi if hi < 1.0 else proba <= hi)
        if not mask.any():
            continue
        rows.append({
            "bin_centre": round((lo + hi) / 2, 4),
            "predicted":  round(float(proba[mask].mean()), 4),
            "observed":   round(float(y[mask].mean()), 4),
            "n":          int(mask.sum()),
        })
    return rows


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
