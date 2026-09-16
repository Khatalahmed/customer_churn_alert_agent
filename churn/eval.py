"""
eval.py

WHAT : This script grades the agent. It compares the agent's predictions
       with what actually happened in the 14 days after the analysis time,
       then prints precision, recall, and F1 score.
WHY  : "It looks like it works" is not proof. Numbers are proof. Because
       we planted the churned customers ourselves, we know the true answer,
       so we can measure the agent honestly.
FLOW : customers active at the analysis time -> label who churns in the next
       14 days (answer key) -> load the predictions (who the agent flagged)
       -> compare the two sets -> print the score and the mistakes.
LOGIC: We treat HIGH or MEDIUM risk as "flagged as churn". LOW means safe.
       precision = of the ones we flagged, how many really churned.
       recall    = of the ones who really churned, how many we caught.
"""
import json

from .config import HORIZON_DAYS, PREDICTIONS_PATH
from .features import add_labels, build_features


def future_churners(as_of=None) -> set:
    """Customers active at `as_of` who stop being active within the horizon."""
    df, _ = build_features(as_of=as_of)
    df = add_labels(df)
    return set(df.loc[df["churned"] == 1, "user_id"])


def score(predictions: list[dict], truly_churned: set) -> dict:
    """Compare flagged customers (HIGH/MEDIUM) with the truly churned set."""
    flagged = {p["user_id"] for p in predictions if p["risk_level"] in ("HIGH", "MEDIUM")}

    true_positives  = flagged & truly_churned      # flagged AND really churned (correct)
    false_positives = flagged - truly_churned      # flagged but NOT churned (false alarm)
    false_negatives = truly_churned - flagged      # churned but we missed them

    tp, fp, fn = len(true_positives), len(false_positives), len(false_negatives)

    # guard against divide-by-zero
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "flagged": flagged,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main():
    # --- 1. The answer key: who churned in the horizon after the analysis time ---
    df, _ = build_features()
    as_of = df["as_of"].iloc[0]
    labelled = add_labels(df)          # drops customers who had already churned
    truly_churned = set(labelled.loc[labelled["churned"] == 1, "user_id"])

    # --- 2. Load the agent's predictions ---
    with open(PREDICTIONS_PATH) as f:
        predictions = json.load(f)

    # --- 3. Compare the two sets ---
    s = score(predictions, truly_churned)

    # --- 4. Print the report ---
    print("=" * 60)
    print("CHURN AGENT EVALUATION")
    print("=" * 60)
    print(f"Analysis time: {as_of}  |  scored: {len(df)} active customers, "
          f"{len(labelled)} with a known 14-day outcome "
          f"({len(df) - len(labelled)} had already churned before the cutoff)")
    print(f"Churned in the next {HORIZON_DAYS} days (ground truth): {sorted(truly_churned)}")
    print(f"Flagged by agent (HIGH/MED):  {sorted(s['flagged'])}")
    print("-" * 60)
    print(f"True positives  (caught):      {sorted(s['true_positives'])}  = {len(s['true_positives'])}")
    print(f"False positives (false alarm): {sorted(s['false_positives'])}  = {len(s['false_positives'])}")
    print(f"False negatives (missed):      {sorted(s['false_negatives'])}  = {len(s['false_negatives'])}")
    print("-" * 60)
    print(f"Precision: {s['precision']:.2f}   (of flagged, how many really churned)")
    print(f"Recall:    {s['recall']:.2f}   (of churned, how many we caught)")
    print(f"F1 score:  {s['f1']:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
