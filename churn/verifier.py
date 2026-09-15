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

from .config import PREDICTIONS_PATH, connect_readonly


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


def verify(conn, predictions: list[dict]) -> dict:
    """Check every claimed evidence field against the DB.

    Returns totals plus {user_id: [mismatch lines]} for users with errors.
    """
    total_fields = 0
    matched_fields = 0
    mismatches_by_user = {}

    for p in predictions:
        uid = p["user_id"]
        claimed = p["evidence"]
        mismatches = []
        for field, real_value in real_facts(conn, uid).items():
            total_fields += 1
            if claimed.get(field) == real_value:
                matched_fields += 1
            else:
                mismatches.append(
                    f"{field}: agent said {claimed.get(field)}, real is {real_value}"
                )
        if mismatches:
            mismatches_by_user[uid] = mismatches

    return {
        "total_fields": total_fields,
        "matched_fields": matched_fields,
        "mismatches": mismatches_by_user,
        "fidelity": matched_fields / total_fields if total_fields else 0.0,
    }


def main():
    # --- load the agent's predictions ---
    with open(PREDICTIONS_PATH) as f:
        predictions = json.load(f)
    names = {p["user_id"]: p["full_name"] for p in predictions}

    # read-only connection, same safety rule as the tools
    conn = connect_readonly()
    result = verify(conn, predictions)
    conn.close()

    print("=" * 70)
    print("EVIDENCE VERIFIER")
    print("=" * 70)
    for uid, lines in result["mismatches"].items():
        print(f"\n[MISMATCH] user {uid} ({names[uid]}):")
        for m in lines:
            print(f"    - {m}")

    users_with_errors = list(result["mismatches"])
    print("\n" + "-" * 70)
    print(f"Users checked:      {len(predictions)}")
    print(f"Users with errors:  {len(users_with_errors)}  {users_with_errors}")
    print(f"Fields checked:     {result['total_fields']}")
    print(f"Fields correct:     {result['matched_fields']}")
    print(f"Evidence fidelity:  {result['fidelity']:.2%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
