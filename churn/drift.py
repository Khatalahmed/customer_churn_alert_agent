"""
drift.py

WHAT : Checks whether new data has "drifted" away from what the model was
       trained on, using PSI (Population Stability Index). If the world
       changes, the model gets stale and should be retrained.
WHY  : A model trained on old data can quietly go wrong when reality shifts
       (e.g., a delivery outage changes everyone's behaviour). A drift check
       lets the model flag ITSELF for retraining instead of failing silently.
FLOW : baseline = the feature distribution the model was trained on ->
       new batch = current / incoming data -> PSI per feature -> flag the
       features that drifted.
LOGIC: PSI < 0.1 = stable; 0.1-0.2 = small shift; > 0.2 = significant drift
       (retrain). Here we simulate a "bad delivery month" to show it firing.
NOTE : psi() is kept at module level so tests can import it. The demo below
       only runs when this file is executed directly.
"""
import numpy as np
import pandas as pd

from .features import build_features


def psi(baseline, new, bins: int = 10) -> float:
    """Population Stability Index between two distributions of one feature."""
    base = baseline.dropna()
    newv = new.dropna()
    if len(base) == 0 or len(newv) == 0:
        return 0.0
    # bin edges from the baseline's quantiles (unique guards against ties)
    edges = np.unique(np.percentile(base, np.linspace(0, 100, bins + 1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    b_counts, _ = np.histogram(base, bins=edges)
    n_counts, _ = np.histogram(newv, bins=edges)
    b_pct = b_counts / max(b_counts.sum(), 1) + 1e-6
    n_pct = n_counts / max(n_counts.sum(), 1) + 1e-6
    return float(np.sum((n_pct - b_pct) * np.log(n_pct / b_pct)))


def ks_statistic(baseline, new) -> float:
    """Two-sample Kolmogorov-Smirnov statistic: the largest gap between the
    two cumulative distributions.

    PSI bins the data, so it under-reacts exactly where this project's
    features live: a rate that is 0 for most customers puts almost everyone
    in one bin, and a shift inside that bin is invisible. KS compares the
    distributions directly and needs no bins.
    """
    base = np.sort(np.asarray(baseline.dropna(), dtype=float))
    newv = np.sort(np.asarray(new.dropna(), dtype=float))
    if len(base) == 0 or len(newv) == 0:
        return 0.0
    grid = np.concatenate([base, newv])
    cdf_base = np.searchsorted(base, grid, side="right") / len(base)
    cdf_new = np.searchsorted(newv, grid, side="right") / len(newv)
    return float(np.max(np.abs(cdf_base - cdf_new)))


def ks_critical_value(n_baseline: int, n_new: int, alpha: float = 0.05) -> float:
    """The KS statistic that counts as a real shift at this sample size.

    A fixed threshold cannot work for KS: with 200 customers a gap of 0.12 is
    noise, with 20,000 it is a different world. c(alpha) * sqrt((n+m)/nm) is
    the standard critical value.
    """
    c = {0.10: 1.22, 0.05: 1.36, 0.01: 1.63}.get(alpha)
    if c is None:
        raise ValueError("alpha must be one of 0.10, 0.05, 0.01")
    if n_baseline == 0 or n_new == 0:
        return float("inf")
    return c * ((n_baseline + n_new) / (n_baseline * n_new)) ** 0.5


# A KS gap has to be both real and big enough to matter. With ~2,500 customers
# on each side the 5% critical value is 0.038, so a gap of 0.06 - a couple of
# extra orders per customer as a cohort ages - is "significant" and utterly
# uninteresting. A monitor that pages on that gets switched off, and then it
# catches nothing at all.
KS_PRACTICAL_FLOOR = 0.10


def feature_drift(baseline, new, columns, psi_alert: float = 0.2,
                  psi_watch: float = 0.1, alpha: float = 0.05,
                  ks_floor: float = KS_PRACTICAL_FLOOR) -> list[dict]:
    """PSI and KS for every feature, with a severity for each.

    Two tests, because they fail differently: PSI is blind inside a crowded
    bin, KS is blind to a shift that moves mass symmetrically. A feature is
    escalated on whichever fires - but KS must clear both its critical value
    (is it real?) and the practical floor (is it big enough to act on?).
    """
    rows = []
    for col in columns:
        base, newv = baseline[col], new[col]
        value = psi(base, newv)
        ks = ks_statistic(base, newv)
        critical = ks_critical_value(len(base.dropna()), len(newv.dropna()), alpha)
        ks_significant = ks > critical
        ks_material = ks_significant and ks > ks_floor
        severity = ("alert" if value > psi_alert or ks_material
                    else "watch" if value > psi_watch or ks_significant else "stable")
        rows.append({"feature": col, "psi": round(value, 3), "ks": round(ks, 3),
                     "ks_critical": round(critical, 3),
                     "ks_significant": ks_significant, "ks_material": ks_material,
                     "severity": severity})
    return rows


def prediction_drift(baseline_scores, new_scores, psi_alert: float = 0.2) -> dict:
    """Drift in the SCORES, not the inputs.

    The features can each look fine while the model's output distribution
    moves, and the output is what the worklist is built from - if the mean
    risk doubles, the shortlist means something different today than it did
    yesterday, whatever the inputs say.
    """
    value = psi(pd.Series(baseline_scores), pd.Series(new_scores))
    base_mean = float(np.mean(baseline_scores)) if len(baseline_scores) else 0.0
    new_mean = float(np.mean(new_scores)) if len(new_scores) else 0.0
    return {
        "psi": round(value, 3),
        "baseline_mean": round(base_mean, 4),
        "new_mean": round(new_mean, 4),
        "mean_ratio": round(new_mean / base_mean, 2) if base_mean else None,
        "severity": "alert" if value > psi_alert else "stable",
    }


if __name__ == "__main__":
    df, cols = build_features()
    baseline = df[cols]

    # --- simulate a "next month" batch where DELIVERY quality dropped ---
    # (a service incident: more cancellations and more unresolved tickets)
    new = baseline.copy()
    new["cancellation_rate"] = np.minimum(1.0, new["cancellation_rate"] + 0.20)
    new["unresolved_ticket_rate"] = np.minimum(1.0, new["unresolved_ticket_rate"] + 0.15)

    print("=" * 60)
    print("DATA DRIFT CHECK  (PSI: baseline vs new batch)")
    print("=" * 60)
    drifted = []
    for c in cols:
        val = psi(baseline[c], new[c])
        if val > 0.2:
            flag, _ = "DRIFT !!", drifted.append(c)
        elif val > 0.1:
            flag = "small shift"
        else:
            flag = "stable"
        print(f"  {c:<26} PSI={val:5.3f}  {flag}")
    print("-" * 60)
    if drifted:
        print(f"ACTION: {len(drifted)} feature(s) drifted -> RETRAIN the model.")
        print(f"        drifted: {drifted}")
    else:
        print("ACTION: no significant drift -> model is still valid.")
    print("=" * 60)