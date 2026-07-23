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