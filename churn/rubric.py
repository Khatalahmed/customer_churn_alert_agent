"""
rubric.py

WHAT : Decides a customer's churn risk level from facts. Pure Python, no LLM.
WHY  : The agent used to assign HIGH / MEDIUM / LOW itself. Measured, its
       verdicts added nothing to precision (0.14 vs the ML shortlist's 0.13),
       and it was really just applying a fixed rule - with LLM variability on
       top. The rule now lives in code: reproducible, unit-tested, free. The
       LLM keeps the job it is actually good at, explaining the evidence in
       plain language.
LOGIC: two independent signals, each answerable from the database.
       - DISSATISFACTION: an unresolved complaint about something that hurts
         (delivery, payment, refund, quality, wrong/missing order), or a
         review of 2 stars or less.
       - DISENGAGEMENT: fewer logins than the previous period, or none in
         either.
       HIGH = both, MEDIUM = one, LOW = neither. A high ML probability alone
       never makes a customer HIGH: the evidence has to back it.
"""
# ticket categories that signal a real problem (an account question does not)
SERIOUS_CATEGORIES = ("DELIVERY_DELAY", "PAYMENT", "REFUND",
                      "PRODUCT_QUALITY", "ORDER_ISSUE")

ACTION_FOR = {"HIGH": "retention call", "MEDIUM": "coupon", "LOW": "ignore"}


def has_dissatisfaction(facts: dict) -> bool:
    """An unfixed serious complaint, or a 1-2 star review. Silence is not evidence."""
    worst = facts.get("worst_review_rating", 0) or 0
    return facts.get("unresolved_serious_tickets", 0) > 0 or 1 <= worst <= 2


def has_disengagement(facts: dict) -> bool:
    """Logging in less than before - or not at all in either period."""
    prev = facts.get("logins_prev_30_60d", 0)
    recent = facts.get("logins_recent_30d", 0)
    return recent < prev or (prev == 0 and recent == 0)


def assess(facts: dict) -> dict:
    """Return the risk level, the action, and which signals fired."""
    dissatisfied = has_dissatisfaction(facts)
    disengaged = has_disengagement(facts)
    level = ("HIGH" if dissatisfied and disengaged
             else "MEDIUM" if dissatisfied or disengaged
             else "LOW")
    return {
        "risk_level": level,
        "suggested_action": ACTION_FOR[level],
        "dissatisfaction": dissatisfied,
        "disengagement": disengaged,
    }


def explain(verdict: dict) -> str:
    """One line naming which signals fired - used when the LLM adds nothing."""
    parts = []
    parts.append("unresolved complaint or low review" if verdict["dissatisfaction"]
                 else "no dissatisfaction signal")
    parts.append("logins falling" if verdict["disengagement"]
                 else "still logging in")
    return f"{verdict['risk_level']}: " + ", ".join(parts)
