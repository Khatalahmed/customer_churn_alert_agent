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

from .config import analysis_time, connect_readonly

UNRESOLVED = ("OPEN", "IN_PROGRESS", "WAITING_ON_CUSTOMER")


def _connect_readonly() -> sqlite3.Connection:
    """Open the database in read-only mode. The tools can read but never write."""
    conn = connect_readonly()
    conn.row_factory = sqlite3.Row  # now we can use row["full_name"] like a dict
    return conn


@tool
def get_user_tickets(user_id: int) -> str:
    """Get all the support tickets from one customer.

    This returns a summary (total_tickets, unresolved_tickets) plus each
    ticket with its type, priority, status, subject, description, and
    resolution notes, all as of the analysis time. It helps us find bad
    signs, like a refund that was never given or a delivery problem that was
    never fixed.

    Args:
        user_id: the id of the customer.
    """
    conn = _connect_readonly()
    as_of = analysis_time(conn)
    rows = conn.execute(
        """SELECT ticket_id, category, priority, status, subject,
                  description, resolution_notes, created_at, resolved_at
           FROM support_tickets
           WHERE user_id = ? AND created_at < ?
           ORDER BY created_at DESC""",
        (user_id, as_of),
    ).fetchall()
    conn.close()
    tickets = [dict(r) for r in rows]
    for t in tickets:
        # resolved only AFTER the analysis time -> it was still open at that time
        if t["resolved_at"] and t["resolved_at"] >= as_of:
            t.update(status="OPEN", resolution_notes=None, resolved_at=None)
    # counted here, in code, so the LLM copies the number instead of counting
    unresolved = sum(1 for t in tickets if t["status"] in UNRESOLVED)
    return json.dumps({
        "analysis_time": as_of,
        "total_tickets": len(tickets),
        "unresolved_tickets": unresolved,
        "tickets": tickets,
    }, indent=2)


@tool
def get_user_reviews(user_id: int) -> str:
    """Get all the product reviews from one customer.

    This returns a summary (total_reviews, worst_review_rating) plus each
    review with its rating (1 to 5), title, and text. It helps us see if the
    customer is unhappy (low ratings or bad words). If there are no reviews,
    worst_review_rating is 0 - silence is also a sign: the customer ordered
    but never left a review.

    Args:
        user_id: the id of the customer.
    """
    conn = _connect_readonly()
    as_of = analysis_time(conn)
    rows = conn.execute(
        """SELECT review_id, rating, review_title, review_text, created_at
           FROM reviews
           WHERE user_id = ? AND created_at < ?
           ORDER BY created_at DESC""",
        (user_id, as_of),
    ).fetchall()
    conn.close()
    reviews = [dict(r) for r in rows]
    # computed here, in code, so the LLM copies the number instead of scanning
    return json.dumps({
        "analysis_time": as_of,
        "total_reviews": len(reviews),
        "worst_review_rating": min((r["rating"] for r in reviews), default=0),
        "reviews": reviews,
    }, indent=2)
