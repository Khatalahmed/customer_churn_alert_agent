"""
tools.py
WHAT : These are the SQL tools that the sub-agents use. Each one is a
       normal Python function. We add @tool on top so the AI agent can
       call it.
WHY  : Our database does not change, and our questions are always the
       same. So writing the SQL by hand is fast, free, and safe. This is
       better than letting the AI write its own SQL (the choice from the
       18 July class).
FLOW : The agent calls a tool -> the tool opens the database in read-only
       mode -> it runs a fixed SQL query -> it gives back a JSON text that
       the AI can read.
LOGIC: Read-only means the tool can look but cannot change anything. An
       agent tool must never delete or edit data. One line (mode=ro) makes
       this safe.
"""
import json
import sqlite3

from langchain.tools import tool

DB_PATH = "qcommerce.db"


def _connect_readonly() -> sqlite3.Connection:
    """Open the database in read-only mode. The tools can read but never write."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row  # now we can use row["full_name"] like a dict
    return conn


@tool
def get_inactive_users(days: int = 14, top_n: int = 10) -> str:
    """Find the customers who are most inactive.

    This returns customers who have not placed an order in the last `days`
    days. They are sorted so the quietest customer comes first, and we only
    return `top_n` of them. For each customer we also show their login
    pattern: how many times they logged in before (30 to 60 days ago)
    compared to now (last 30 days). A big drop is the main churn signal.

    Args:
        days: how many days with no order counts as "inactive" (default 14).
        top_n: the most customers to return (default 10).
    """
    conn = _connect_readonly()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT u.user_id, u.full_name, u.city,
               MAX(o.placed_at) AS last_order,
               COUNT(o.order_id) AS total_orders
        FROM users u
        LEFT JOIN orders o ON o.user_id = u.user_id
        WHERE u.user_type = 'CUSTOMER'
        GROUP BY u.user_id
        HAVING last_order IS NULL
            OR last_order < datetime('now', ?)
        ORDER BY last_order
        LIMIT ?
        """,
        (f"-{days} days", top_n),
    ).fetchall()

    results = []
    for r in rows:
        uid = r["user_id"]
        prev = cur.execute(
            """SELECT COUNT(*) FROM auth_audit_log
               WHERE user_id = ? AND event_type = 'LOGIN'
                 AND event_timestamp BETWEEN datetime('now','-60 days')
                                         AND datetime('now','-30 days')""",
            (uid,),
        ).fetchone()[0]
        recent = cur.execute(
            """SELECT COUNT(*) FROM auth_audit_log
               WHERE user_id = ? AND event_type = 'LOGIN'
                 AND event_timestamp >= datetime('now','-30 days')""",
            (uid,),
        ).fetchone()[0]
        results.append({
            "user_id": uid,
            "full_name": r["full_name"],
            "city": r["city"],
            "last_order": r["last_order"],
            "total_orders": r["total_orders"],
            "logins_prev_30_60d": prev,
            "logins_recent_30d": recent,
        })
    conn.close()
    return json.dumps(results, indent=2)


@tool
def get_user_tickets(user_id: int) -> str:
    """Get all the support tickets from one customer.

    This returns each ticket with its type, priority, status, subject,
    description, and resolution notes. It helps us find bad signs, like a
    refund that was never given or a delivery problem that was never fixed.

    Args:
        user_id: the id of the customer.
    """
    conn = _connect_readonly()
    rows = conn.execute(
        """SELECT ticket_id, category, priority, status, subject,
                  description, resolution_notes, created_at, resolved_at
           FROM support_tickets
           WHERE user_id = ?
           ORDER BY created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    tickets = [dict(r) for r in rows]
    return json.dumps(tickets, indent=2)


@tool
def get_user_reviews(user_id: int) -> str:
    """Get all the product reviews from one customer.

    This returns each review with its rating (1 to 5), title, and text. It
    helps us see if the customer is unhappy (low ratings or bad words). If
    the result is empty, that is also a sign - the customer ordered but
    never left a review.

    Args:
        user_id: the id of the customer.
    """
    conn = _connect_readonly()
    rows = conn.execute(
        """SELECT review_id, rating, review_title, review_text, created_at
           FROM reviews
           WHERE user_id = ?
           ORDER BY created_at DESC""",
        (user_id,),
    ).fetchall()
    conn.close()
    reviews = [dict(r) for r in rows]
    return json.dumps(reviews, indent=2)