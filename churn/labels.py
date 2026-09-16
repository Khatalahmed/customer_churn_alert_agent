"""
labels.py

WHAT : Two definitions that the rest of the project depends on and that were
       previously implicit: who counts as an ACTIVE customer at a cutoff, and
       what it means to have CHURNED - derived from raw events, with no
       answer key.
WHY  : "Active" was "logged in at least once in the last 28 days", written
       into one SQL query in features.py. The business question is about
       ordering, the label came from the simulator's hidden active_until, and
       nothing said how the two related. A definition nobody can restate is a
       definition nobody can check.
FLOW : active_customers() picks the population at T. observable_churn()
       labels it from what actually happened afterwards. label_agreement()
       compares that with the answer key, which is how we know the key is not
       doing any secret work.
LOGIC: churn here means "stopped for good", so the observable label is "the
       last thing this customer ever did falls inside the horizon". That
       needs follow-up data to be trustworthy: the customer must have had
       time to come back and not done so. MIN_FOLLOW_UP_DAYS is the measured
       floor, not a guess - see the table in the docstring below.
"""
from datetime import datetime, timedelta

from .config import ACTIVE_WINDOW_DAYS, HORIZON_DAYS

# Measured agreement between the observable label and the answer key, by how
# much data exists after the horizon ends (held-out snapshots, this database):
#     ~98 days of follow-up   precision 94%, recall 92%
#     ~70 days                precision 88%, recall 95%
#     ~42 days                precision 73%, recall 100%
#     ~14 days                precision 11%  - "quiet" is indistinguishable
#                                              from "gone"
# Below the floor the label is not wrong so much as premature.
MIN_FOLLOW_UP_DAYS = 60


def active_customers(conn, as_of: str, window_days: int = ACTIVE_WINDOW_DAYS) -> set[int]:
    """Customers who ordered OR logged in during the window before `as_of`.

    Ordering is the behaviour the business cares about; logging in is the
    behaviour that shows intent. Requiring both would drop customers who are
    still shopping, and requiring orders alone would drop 75 customers here
    who are still opening the app - so the population is the union.

    In this database every order implies a login, so orders are a strict
    subset and the union is identical to the login-only population it
    replaces (2,561 customers, base rate 1.37%). The definition changes; no
    measured number does. That is the point of writing it down.
    """
    rows = conn.execute(
        """SELECT DISTINCT user_id FROM (
               SELECT user_id, placed_at AS ts FROM orders
               UNION ALL
               SELECT user_id, event_timestamp FROM auth_audit_log
               WHERE event_type = 'LOGIN')
           WHERE ts >= datetime(?, ?) AND ts < ?""",
        (as_of, f"-{window_days} days", as_of),
    ).fetchall()
    return {r[0] for r in rows}


def last_seen(conn, before: str | None = None) -> dict[int, str]:
    """The last time each customer did anything at all (order or login)."""
    clause, params = "", ()
    if before:
        clause, params = "WHERE ts < ?", (before,)
    rows = conn.execute(
        f"""SELECT user_id, MAX(ts) FROM (
                SELECT user_id, placed_at AS ts FROM orders
                UNION ALL
                SELECT user_id, event_timestamp FROM auth_audit_log
                WHERE event_type = 'LOGIN')
            {clause} GROUP BY user_id""",
        params,
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def observable_churn(conn, as_of: str, now: str, horizon_days: int = HORIZON_DAYS,
                     min_follow_up: int = MIN_FOLLOW_UP_DAYS) -> dict:
    """Label churn from raw events: last activity ever falls inside the horizon.

    This is the definition a real team can compute - no hidden state, no
    answer key. It is also the definition that needs patience: a customer who
    is merely quiet looks identical to one who has left until enough time has
    passed for them to have come back.

    Returns the labelled ids plus `trustworthy`, which is False when there is
    less than `min_follow_up` days of data after the horizon. Reporting that
    flag is the honest half: at the held-out cutoff, with 14 days of
    follow-up, this label flags 327 customers of whom 35 really churned.
    """
    end = datetime.fromisoformat(as_of) + timedelta(days=horizon_days)
    follow_up = (datetime.fromisoformat(now) - end).days
    seen = last_seen(conn)
    churned = {uid for uid in active_customers(conn, as_of)
               if as_of < seen.get(uid, "") <= end.isoformat(sep=" ")}
    return {
        "churned_ids": churned,
        "follow_up_days": follow_up,
        "trustworthy": follow_up >= min_follow_up,
        "note": ("" if follow_up >= min_follow_up else
                 f"only {follow_up} days of follow-up: a quiet customer is not yet "
                 f"distinguishable from a departed one (need {min_follow_up})"),
    }


def label_agreement(observed_ids: set[int], keyed_ids: set[int]) -> dict:
    """How well the observable label matches the answer key.

    The key exists only because a simulator wrote it. If the same labels fall
    out of the raw events, the key is a convenience rather than a crutch -
    and if they do not, the difference is the definition doing real work and
    belongs in the README, not in a comment.
    """
    hits = len(observed_ids & keyed_ids)
    return {
        "observed": len(observed_ids),
        "keyed": len(keyed_ids),
        "agree": hits,
        "precision": hits / len(observed_ids) if observed_ids else 0.0,
        "recall": hits / len(keyed_ids) if keyed_ids else 0.0,
    }
