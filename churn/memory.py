"""
memory.py

WHAT : Remembers which customers we already contacted, so we do not flag the
       same person every week (no nagging).
WHY  : Churn detection runs again and again. If we contacted a customer last
       week, we should give the coupon or call time to work before flagging
       them again.
FLOW : contacts are saved in contacted.json as {user_id: date}. We can mark
       new contacts, and ask which customers were contacted recently.
"""
import json
import os
from datetime import datetime, timedelta

STORE_PATH = "contacted.json"


def load_contacted() -> dict:
    """Load the contact log ({user_id: 'YYYY-MM-DD'}). Empty if none yet."""
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH) as f:
        return json.load(f)


def mark_contacted(user_ids) -> int:
    """Record that we contacted these customers today."""
    data = load_contacted()
    today = datetime.now().strftime("%Y-%m-%d")
    for uid in user_ids:
        data[str(uid)] = today
    with open(STORE_PATH, "w") as f:
        json.dump(data, f, indent=2)
    return len(user_ids)


def recently_contacted_ids(days: int = 30) -> set:
    """Return the set of user_ids contacted within the last `days` days."""
    data = load_contacted()
    cutoff = datetime.now() - timedelta(days=days)
    recent = set()
    for uid, date_str in data.items():
        contacted_on = datetime.strptime(date_str, "%Y-%m-%d")
        if contacted_on >= cutoff:
            recent.add(int(uid))
    return recent