"""
archetype_eval.py

WHAT : Measures the model's churn recall PER ARCHETYPE, and the false-alarm
       rate on the two "trap" archetypes (vacationer, loyal bulk-buyer).
WHY  : A single recall number hides WHERE the model struggles. Per-archetype
       recall shows it catches sudden cliff-droppers easily but slow faders
       less well - and whether it wrongly flags customers who only LOOK
       dormant (vacationers, loyal low-frequency buyers).
FLOW : load answer key (archetype + churned) -> score all customers with the
       model -> flag if churn_probability > threshold -> group by archetype
       -> print recall (churned types) and false-alarm rate (traps).
"""
import json

import joblib

from .features import build_features

THRESHOLD = 0.5

bundle = joblib.load("churn_model.pkl")
model, cols = bundle["model"], bundle["features"]

df, _ = build_features()
df["churn_probability"] = model.predict_proba(df[cols])[:, 1]
flagged = set(df.loc[df["churn_probability"] > THRESHOLD, "user_id"])

with open("churn_truth.json") as f:
    truth = json.load(f)

by_arch = {}
for r in truth:
    by_arch.setdefault(r["archetype"], []).append(r["user_id"])

print("=" * 68)
print(f"PER-ARCHETYPE MODEL PERFORMANCE  (flag if churn prob > {THRESHOLD})")
print("=" * 68)
print(f"{'archetype':<20}{'churned?':<12}{'n':>4}{'flagged':>9}{'rate':>8}")
print("-" * 68)

ORDER = ["cliff_dropper", "gradual_fader", "vacationer", "loyal_bulk_buyer", "regular_active"]
CHURNED_TYPES = {"cliff_dropper", "gradual_fader"}

for arch in ORDER:
    ids = by_arch.get(arch, [])
    if not ids:
        continue
    n = len(ids)
    hit = sum(1 for uid in ids if uid in flagged)
    rate = hit / n
    if arch in CHURNED_TYPES:
        churned_label, meaning = "yes", "recall"
    elif arch == "regular_active":
        churned_label, meaning = "no", "false-alarm"
    else:
        churned_label, meaning = "NO (trap)", "false-alarm"
    print(f"{arch:<20}{churned_label:<12}{n:>4}{hit:>9}{rate:>7.0%}  ({meaning})")
print("=" * 68)