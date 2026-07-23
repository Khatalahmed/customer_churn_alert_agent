"""
verifier.py

WHAT : This script checks the agent's evidence. For every customer the
       agent judged, it re-computes the same five numbers straight from the
       database, then compares them with what the agent claimed.
WHY  : An LLM can make up or miscount facts. We must not trust its numbers
       blindly. This gives an "evidence fidelity" score: how many of the
       agent's facts are actually true.
FLOW : load predictions -> for each user, query the real numbers from the
       database -> compare field by field -> print mismatches and the
       overall fidelity score.
LOGIC: We query the database ourselves, on purpose, so the check does not
       depend on the agent's own tools. If the agent's number is not equal
       to the real number, it is a mismatch (a possible hallucination).
"""
import json
import sqlite3

DB_PATH = "qcommerce.db"


def real_facts(conn, user_id):
    """Compute the true five numbers for one user, straight from the DB."""
    cur = conn.cursor()
    prev = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp BETWEEN datetime('now','-60 days')
                                     AND datetime('now','-30 days')""",
        (user_id,),
    ).fetchone()[0]
    recent = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp >= datetime('now','-30 days')""",
        (user_id,),
    ).fetchone()[0]
    orders = cur.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    tickets = cur.execute(
        "SELECT COUNT(*) FROM support_tickets WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    worst = cur.execute(
        "SELECT MIN(rating) FROM reviews WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    worst = worst if worst is not None else 0    # 0 means the user has no reviews
    return {
        "logins_prev_30_60d": prev,
        "logins_recent_30d": recent,
        "total_orders": orders,
        "total_tickets": tickets,
        "worst_review_rating": worst,
    }


# --- load the agent's predictions ---
with open("churn_predictions.json") as f:
    predictions = json.load(f)

# read-only connection, same safety rule as the tools
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

total_fields = 0
matched_fields = 0
users_with_errors = []

print("=" * 70)
print("EVIDENCE VERIFIER")
print("=" * 70)

for p in predictions:
    uid = p["user_id"]
    claimed = p["evidence"]
    real = real_facts(conn, uid)

    mismatches = []
    for field, real_value in real.items():
        total_fields += 1
        if claimed.get(field) == real_value:
            matched_fields += 1
        else:
            mismatches.append(
                f"{field}: agent said {claimed.get(field)}, real is {real_value}"
            )

    if mismatches:
        users_with_errors.append(uid)
        print(f"\n[MISMATCH] user {uid} ({p['full_name']}):")
        for m in mismatches:
            print(f"    - {m}")

conn.close()

fidelity = matched_fields / total_fields if total_fields else 0.0

print("\n" + "-" * 70)
print(f"Users checked:      {len(predictions)}")
print(f"Users with errors:  {len(users_with_errors)}  {users_with_errors}")
print(f"Fields checked:     {total_fields}")
print(f"Fields correct:     {matched_fields}")
print(f"Evidence fidelity:  {fidelity:.2%}")
print("=" * 70)