"""
eval.py

WHAT : This script grades the agent. It compares the agent's predictions
       with the answer key, then prints precision, recall, and F1 score.
WHY  : "It looks like it works" is not proof. Numbers are proof. Because
       we planted the churned customers ourselves, we know the true answer,
       so we can measure the agent honestly.
FLOW : load the answer key (who really churned) -> load the predictions
       (who the agent flagged) -> compare the two sets -> print the score
       and the mistakes.
LOGIC: We treat HIGH or MEDIUM risk as "flagged as churn". LOW means safe.
       precision = of the ones we flagged, how many really churned.
       recall    = of the ones who really churned, how many we caught.
"""
import json

# --- 1. Load the answer key: which customers truly churned ---
with open("churn_truth.json") as f:
    truth = json.load(f)
truly_churned = {row["user_id"] for row in truth if row["churned"]}

# --- 2. Load the agent's predictions ---
with open("churn_predictions.json") as f:
    predictions = json.load(f)
# We count a customer as "flagged" if the risk is HIGH or MEDIUM.
flagged = {p["user_id"] for p in predictions if p["risk_level"] in ("HIGH", "MEDIUM")}

# --- 3. Compare the two sets ---
true_positives  = flagged & truly_churned      # flagged AND really churned (correct)
false_positives = flagged - truly_churned      # flagged but NOT churned (false alarm)
false_negatives = truly_churned - flagged      # churned but we missed them

tp, fp, fn = len(true_positives), len(false_positives), len(false_negatives)

# --- 4. Compute the scores (guard against divide-by-zero) ---
precision = tp / (tp + fp) if (tp + fp) else 0.0
recall    = tp / (tp + fn) if (tp + fn) else 0.0
f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

# --- 5. Print the report ---
print("=" * 60)
print("CHURN AGENT EVALUATION")
print("=" * 60)
print(f"Truly churned (ground truth): {sorted(truly_churned)}")
print(f"Flagged by agent (HIGH/MED):  {sorted(flagged)}")
print("-" * 60)
print(f"True positives  (caught):      {sorted(true_positives)}  = {tp}")
print(f"False positives (false alarm): {sorted(false_positives)}  = {fp}")
print(f"False negatives (missed):      {sorted(false_negatives)}  = {fn}")
print("-" * 60)
print(f"Precision: {precision:.2f}   (of flagged, how many really churned)")
print(f"Recall:    {recall:.2f}   (of churned, how many we caught)")
print(f"F1 score:  {f1:.2f}")
print("=" * 60)