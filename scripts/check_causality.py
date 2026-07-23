"""
check_causality.py

WHAT : Prove that churned customers really do have worse experiences than
       active ones. We compare the two groups on ratings, cancellations,
       and unresolved tickets.
WHY  : Before training a model, we must confirm the data has real signal.
       If churned and active customers looked the same, no model could tell
       them apart. This check shows the causal link we built is really there.
FLOW : read the answer key (who churned) -> split users into two groups ->
       compute the average bad-experience numbers for each group -> compare.
"""
import json
import sqlite3

with open("churn_truth.json") as f:
    truth = json.load(f)
churned_ids = [r["user_id"] for r in truth if r["churned"]]
active_ids = [r["user_id"] for r in truth if not r["churned"]]

conn = sqlite3.connect("file:qcommerce.db?mode=ro", uri=True)
cur = conn.cursor()


def group_stats(user_ids):
    """Compute the average bad-experience numbers for a group of users."""
    ph = ",".join("?" for _ in user_ids)   # a "?" placeholder per user_id

    avg_rating = cur.execute(
        f"SELECT AVG(rating) FROM reviews WHERE user_id IN ({ph})", user_ids
    ).fetchone()[0]

    total_orders = cur.execute(
        f"SELECT COUNT(*) FROM orders WHERE user_id IN ({ph})", user_ids
    ).fetchone()[0]
    cancelled = cur.execute(
        f"SELECT COUNT(*) FROM orders WHERE order_status='CANCELLED' "
        f"AND user_id IN ({ph})", user_ids
    ).fetchone()[0]
    cancel_rate = cancelled / total_orders if total_orders else 0.0

    total_tickets = cur.execute(
        f"SELECT COUNT(*) FROM support_tickets WHERE user_id IN ({ph})", user_ids
    ).fetchone()[0]
    unresolved = cur.execute(
        f"SELECT COUNT(*) FROM support_tickets "
        f"WHERE status IN ('OPEN','IN_PROGRESS','WAITING_ON_CUSTOMER') "
        f"AND user_id IN ({ph})", user_ids
    ).fetchone()[0]
    unresolved_rate = unresolved / total_tickets if total_tickets else 0.0
    tickets_per_user = total_tickets / len(user_ids)

    return avg_rating, cancel_rate, unresolved_rate, tickets_per_user


cr = group_stats(churned_ids)
ac = group_stats(active_ids)

print("=" * 64)
print("CAUSALITY CHECK: churned vs active customers")
print("=" * 64)
print(f"{'metric':<28}{'churned':>12}{'active':>12}")
print("-" * 64)
print(f"{'avg review rating':<28}{cr[0]:>12.2f}{ac[0]:>12.2f}")
print(f"{'cancellation rate':<28}{cr[1]:>12.2%}{ac[1]:>12.2%}")
print(f"{'unresolved ticket rate':<28}{cr[2]:>12.2%}{ac[2]:>12.2%}")
print(f"{'tickets per customer':<28}{cr[3]:>12.2f}{ac[3]:>12.2f}")
print("=" * 64)
conn.close()