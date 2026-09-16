"""
archetype_eval.py

WHAT : Measures the model PER ARCHETYPE on the held-out, later snapshot:
       recall on the two churner types and the false-alarm rate on the two
       "trap" types (vacationer, loyal bulk-buyer) and regular customers.
WHY  : A single AUC hides WHERE the model struggles. Traps only LOOK like
       churners - a vacationer goes quiet, a loyal bulk-buyer orders rarely -
       so they show whether the model mistakes quiet for leaving.
FLOW : held-out snapshot -> saved model (trained only on earlier snapshots,
       so this is out-of-time, not in-sample) -> flag if probability >
       threshold -> group by archetype.
LOGIC: counts are small (one snapshot, ~220 customers, ~16 churners), so the
       table prints n for every cell - read rates with that in mind.
"""
import json

import joblib

from .config import MODEL_PATH, TEST_CUTOFF_DAYS, TRUTH_PATH
from .features import build_snapshots

THRESHOLD = 0.5
ORDER = ["cliff_dropper", "gradual_fader", "vacationer", "loyal_bulk_buyer", "regular_active"]
TRAPS = {"vacationer", "loyal_bulk_buyer"}


def main():
    test, _ = build_snapshots([TEST_CUTOFF_DAYS])
    bundle = joblib.load(MODEL_PATH)
    test["proba"] = bundle["model"].predict_proba(test[bundle["features"]])[:, 1]
    test["flagged"] = test["proba"] > THRESHOLD
    top15 = set(test.nlargest(15, "proba")["user_id"])

    with open(TRUTH_PATH) as f:
        archetype = {r["user_id"]: r["archetype"] for r in json.load(f)}
    test["archetype"] = test["user_id"].map(archetype)

    print("=" * 84)
    print(f"PER-ARCHETYPE PERFORMANCE  (out-of-time snapshot {test['as_of'].iloc[0]}, "
          f"flag if prob > {THRESHOLD})")
    print("=" * 84)
    print(f"{'archetype':<25}{'active':>7}{'churn':>7}{'recall':>12}{'false alarms':>16}{'in top-15':>11}")
    print("-" * 84)
    for arch in ORDER:
        g = test[test["archetype"] == arch]
        if g.empty:
            continue
        pos, neg = g[g["churned"] == 1], g[g["churned"] == 0]
        recall = f"{pos['flagged'].sum()}/{len(pos)}" if len(pos) else "-"
        alarms = f"{neg['flagged'].sum()}/{len(neg)} ({neg['flagged'].mean():.0%})" if len(neg) else "-"
        in_top = sum(uid in top15 for uid in g["user_id"])
        tag = " (trap)" if arch in TRAPS else ""
        print(f"{arch + tag:<25}{len(g):>7}{len(pos):>7}{recall:>12}{alarms:>16}{in_top:>11}")
    print("=" * 84)
    print("recall = churners in the next 14 days that were flagged; false alarms = flagged among the rest")


if __name__ == "__main__":
    main()
