"""
logins.py

WHAT : One function that counts logins in the two engagement windows, used by
       the scoring tools, the evidence verifier and the prose verifier.
WHY  : Four modules each wrote their own version of this query. Two used
       14/28-day windows (matching the model's features), two used 30/60, and
       one counted a login landing exactly on the boundary twice because it
       used SQL BETWEEN, which is inclusive at both ends. An agent explaining
       a prediction with a different fortnight from the one the model reacted
       to is not explaining the prediction.
LOGIC: both windows are half-open - [T-recent, T) and [T-prev, T-recent) - so
       every login falls in exactly one of them, and the lengths come from
       config, not from a string typed into each query.
"""
from .config import LOGIN_PREV_DAYS, LOGIN_RECENT_DAYS


def login_counts(conn, user_id: int, as_of: str) -> tuple[int, int]:
    """(logins in the previous window, logins in the recent window) before `as_of`."""
    cur = conn.cursor()
    prev = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id = ? AND event_type = 'LOGIN'
             AND event_timestamp >= datetime(?, ?)
             AND event_timestamp <  datetime(?, ?)""",
        (user_id, as_of, f"-{LOGIN_PREV_DAYS} days", as_of, f"-{LOGIN_RECENT_DAYS} days"),
    ).fetchone()[0]
    recent = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id = ? AND event_type = 'LOGIN'
             AND event_timestamp >= datetime(?, ?)
             AND event_timestamp <  ?""",
        (user_id, as_of, f"-{LOGIN_RECENT_DAYS} days", as_of),
    ).fetchone()[0]
    return prev, recent
