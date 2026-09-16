"""
verifier.py

WHAT : Re-computes the five evidence numbers for every customer the agent
       judged, straight from the database, and compares them to what the
       agent claimed.
WHY  : An LLM can make up or miscount facts. We must not trust its numbers
       blindly. This gives an "evidence fidelity" score: how many of the
       agent's facts are actually true.
FLOW : load predictions -> query the real numbers from the database
       (real_facts one-at-a-time, or real_facts_batch for a list) ->
       compare field by field -> report mismatches and the overall score.
LOGIC: We query the database ourselves so the check does not depend on the
       agent's own tools. If the agent's number differs from the DB value
       it is a mismatch (a possible hallucination).
PERF : real_facts() opens a separate cursor per customer. For the /worklist
       hot path use real_facts_batch(), which fetches all customers in 4
       queries regardless of worklist size.
"""
import json

from .config import (LOGIN_PREV_FIELD, LOGIN_RECENT_FIELD, PREDICTIONS_PATH,
                     analysis_time, connect_readonly)
from .logins import login_counts
from .rubric import SERIOUS_CATEGORIES


def real_facts(conn, user_id, as_of=None):
    """Compute the true five numbers for one user, as of the analysis time."""
    as_of = as_of or analysis_time(conn)   # the pipeline's point in time
    cur = conn.cursor()
    prev, recent = login_counts(conn, user_id, as_of)   # shared with the tools
    orders = cur.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id=? AND placed_at < ?", (user_id, as_of)
    ).fetchone()[0]
    tickets = cur.execute(
        "SELECT COUNT(*) FROM support_tickets WHERE user_id=? AND created_at < ?", (user_id, as_of)
    ).fetchone()[0]
    serious = cur.execute(
        f"""SELECT COUNT(*) FROM support_tickets
            WHERE user_id=? AND created_at < ?
              AND (resolved_at IS NULL OR resolved_at >= ?)
              AND category IN ({','.join('?' * len(SERIOUS_CATEGORIES))})""",
        (user_id, as_of, as_of, *SERIOUS_CATEGORIES),
    ).fetchone()[0]
    worst = cur.execute(
        "SELECT MIN(rating) FROM reviews WHERE user_id=? AND created_at < ?", (user_id, as_of)
    ).fetchone()[0]
    worst = worst if worst is not None else 0    # 0 means the user has no reviews
    return {
        LOGIN_PREV_FIELD: prev,
        LOGIN_RECENT_FIELD: recent,
        "total_orders": orders,
        "total_tickets": tickets,
        "unresolved_serious_tickets": serious,
        "worst_review_rating": worst,
    }


def real_facts_batch(conn, user_ids: list[int], as_of: str) -> dict[int, dict]:
    """Compute the five evidence fields for a list of users in 4 queries.

    Returns {user_id: facts_dict} with the same keys as real_facts().
    Empty fact dicts (all zeros) are used for users with no data in a table.
    This is the batched sibling of real_facts(); use it on the /worklist
    hot path where calling real_facts() per customer would cost 4×N queries.
    """
    if not user_ids:
        return {}
    placeholders = ",".join("?" * len(user_ids))
    cur = conn.cursor()

    # Initialise with zeros so every user_id has an entry even with no data.
    result: dict[int, dict] = {
        uid: {
            LOGIN_PREV_FIELD: 0,
            LOGIN_RECENT_FIELD: 0,
            "total_orders": 0,
            "total_tickets": 0,
            "unresolved_serious_tickets": 0,
            "worst_review_rating": 0,
        }
        for uid in user_ids
    }

    # 1. login counts — replicate login_counts() logic for every user at once
    from .config import LOGIN_RECENT_DAYS, LOGIN_PREV_DAYS
    for uid, prev_count, recent_count in cur.execute(
        f"""SELECT user_id,
               SUM(event_timestamp <  datetime(?, '-{LOGIN_RECENT_DAYS} days')
                   AND event_timestamp >= datetime(?, '-{LOGIN_PREV_DAYS} days')) AS prev,
               SUM(event_timestamp >= datetime(?, '-{LOGIN_RECENT_DAYS} days')
                   AND event_timestamp <  ?) AS recent
           FROM auth_audit_log
           WHERE event_type = 'LOGIN' AND event_timestamp < ?
             AND user_id IN ({placeholders})
           GROUP BY user_id""",
        (as_of, as_of, as_of, as_of, as_of, *user_ids),
    ):
        if uid in result:
            result[uid][LOGIN_PREV_FIELD] = int(prev_count or 0)
            result[uid][LOGIN_RECENT_FIELD] = int(recent_count or 0)

    # 2. total orders
    for uid, count in cur.execute(
        f"""SELECT user_id, COUNT(*) FROM orders
           WHERE placed_at < ? AND user_id IN ({placeholders})
           GROUP BY user_id""",
        (as_of, *user_ids),
    ):
        if uid in result:
            result[uid]["total_orders"] = int(count)

    # 3. total tickets
    for uid, count in cur.execute(
        f"""SELECT user_id, COUNT(*) FROM support_tickets
           WHERE created_at < ? AND user_id IN ({placeholders})
           GROUP BY user_id""",
        (as_of, *user_ids),
    ):
        if uid in result:
            result[uid]["total_tickets"] = int(count)

    # 4. unresolved serious tickets + worst review in a single scan each
    serious_placeholders = ",".join("?" * len(SERIOUS_CATEGORIES))
    for uid, count in cur.execute(
        f"""SELECT user_id, COUNT(*) FROM support_tickets
            WHERE created_at < ?
              AND (resolved_at IS NULL OR resolved_at >= ?)
              AND category IN ({serious_placeholders})
              AND user_id IN ({placeholders})
            GROUP BY user_id""",
        (as_of, as_of, *SERIOUS_CATEGORIES, *user_ids),
    ):
        if uid in result:
            result[uid]["unresolved_serious_tickets"] = int(count)

    for uid, worst in cur.execute(
        f"""SELECT user_id, MIN(rating) FROM reviews
           WHERE created_at < ? AND user_id IN ({placeholders})
           GROUP BY user_id""",
        (as_of, *user_ids),
    ):
        if uid in result:
            result[uid]["worst_review_rating"] = int(worst) if worst is not None else 0

    return result


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
