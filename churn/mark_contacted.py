"""
mark_contacted.py

WHAT : Marks the customers in the latest report as "contacted today", so the
       next run will not flag them again for 30 days.
WHY  : This closes the loop. After the retention team acts on the report, we
       record it, and memory.py makes future runs skip these customers.
FLOW : read churn_predictions.json -> mark each user_id as contacted.
"""
import json

from .memory import mark_contacted

with open("churn_predictions.json") as f:
    preds = json.load(f)

ids = [p["user_id"] for p in preds]
n = mark_contacted(ids)
print(f"Marked {n} customers as contacted. Future runs will skip them for 30 days.")