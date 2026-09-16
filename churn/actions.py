"""
actions.py

WHAT : Turns a risk verdict into a SPECIFIC intervention and its expected
       value, so the worklist is ordered by money at risk rather than by
       probability.
WHY   : "HIGH risk - retention call" does not tell a team what to do or
       whether it is worth doing. A customer with a 13% chance of leaving and
       Rs 200 of monthly margin is worth less attention than a 9% customer
       worth Rs 900, and an unresolved refund needs the refund fixed, not a
       coupon on top of it.
LOGIC: expected value = P(churn) x present value of the margin x uplift - cost.
       P(churn) is calibrated (see train_model), so it can be multiplied by
       money honestly. EVERYTHING ELSE BELOW IS AN ASSUMPTION: margin rate,
       how many months of margin a save is worth, each intervention's uplift
       and cost. They are gathered in one block so they are easy to challenge
       and easy to replace with real finance numbers. The rupee figures are
       therefore ILLUSTRATIVE - they show the decision logic, they are not a
       measured business result.
"""
from .rubric import SERIOUS_CATEGORIES

# --- assumptions (replace with real finance numbers before believing any of it) ---
MARGIN_RATE = 0.25          # gross margin on an order
CURRENCY = "Rs"

# A rescued customer is not worth six months of margin in cash today, which is
# what "MONTHS_SAVED = 6" quietly assumed. Two things reduce it:
#   - they may leave anyway next month, or the month after (MONTHLY_SURVIVAL)
#   - a rupee in six months is worth less than a rupee now (MONTHLY_DISCOUNT)
# So the value of a save is the present value of a margin stream that decays,
# summed over a horizon, instead of a flat multiple.
MONTHLY_SURVIVAL = 0.93     # a rescued customer's chance of still being here next month
MONTHLY_DISCOUNT = 0.01     # ~12.7% a year
VALUE_HORIZON_MONTHS = 12   # beyond this the discounted terms are rounding error

# How wrong the assumptions could be, for the sensitivity band. An expected
# value of Rs 10 built on an uplift nobody has measured is not a decision.
UPLIFT_UNCERTAINTY = 0.5    # the true uplift could be half, or one and a half times

# uplift = the share of would-be churners this intervention actually rescues.
# Ordered by how specific the fix is: fixing the actual complaint beats a coupon.
INTERVENTIONS = {
    "resolve_open_ticket": {"label": "resolve the open ticket, then call",
                            "uplift": 0.30, "cost": 250},
    "delivery_credit":     {"label": "apologise + delivery credit",
                            "uplift": 0.20, "cost": 150},
    "replace_item":        {"label": "replace the item + apology",
                            "uplift": 0.25, "cost": 300},
    "coupon":              {"label": "win-back coupon",
                            "uplift": 0.15, "cost": 150},
    # an automated email costs almost nothing, so it pays off at far lower
    # risk than anything involving money or a human being
    "email_nudge":         {"label": "automated we-miss-you email",
                            "uplift": 0.05, "cost": 5},
    "none":                {"label": "no action", "uplift": 0.0, "cost": 0},
}

# which complaint category calls for which fix
CATEGORY_FIX = {
    "REFUND": "resolve_open_ticket",
    "PAYMENT": "resolve_open_ticket",
    "DELIVERY_DELAY": "delivery_credit",
    "ORDER_ISSUE": "delivery_credit",
    "PRODUCT_QUALITY": "replace_item",
}


def choose_intervention(verdict: dict, open_categories=()) -> str:
    """Match the fix to the problem, not to the risk level.

    An unresolved complaint is fixed first - a coupon on top of an unrefunded
    payment reads as an insult. Disengagement without a complaint is what a
    coupon is actually for. LOW risk gets nothing.
    """
    if verdict["risk_level"] == "LOW":
        return "none"
    for category in open_categories:                  # first open complaint wins
        if category in CATEGORY_FIX:
            return CATEGORY_FIX[category]
    if verdict["dissatisfaction"]:                    # unhappy, but not a ticket
        return "replace_item"
    return "coupon"                                   # quiet but content


def monthly_margin(avg_order_value: float, orders_per_month: float) -> float:
    """What this customer is worth per month, in margin."""
    return (avg_order_value or 0.0) * (orders_per_month or 0.0) * MARGIN_RATE


def margin_present_value(monthly: float, survival: float = MONTHLY_SURVIVAL,
                         discount: float = MONTHLY_DISCOUNT,
                         horizon: int = VALUE_HORIZON_MONTHS) -> float:
    """Present value of a monthly margin stream that decays and is discounted.

    sum over k of  monthly * survival^k / (1 + discount)^k

    A save is worth less than "six months of margin": the customer can leave
    again, and future money is worth less than money now. At the defaults this
    is ~7.0 months of margin over a 12-month horizon rather than a flat 6 -
    close by coincidence, but it now moves correctly when the assumptions do,
    and it stops pretending a rescue is permanent.
    """
    factor = survival / (1 + discount)
    return sum(monthly * factor ** k for k in range(1, horizon + 1))


def expected_value(churn_probability: float, avg_order_value: float,
                   orders_per_month: float, intervention: str) -> dict:
    """Money at risk, whether acting pays for itself, and how sure that is.

    expected save = P(churn) x present value of the margin x uplift
    The cost is paid for EVERY customer contacted, including the ones who were
    never going to leave - which is why a cheap intervention wins here.
    """
    spec = INTERVENTIONS[intervention]
    margin_at_risk = margin_present_value(monthly_margin(avg_order_value, orders_per_month))
    expected_save = churn_probability * margin_at_risk * spec["uplift"]
    value = expected_save - spec["cost"]
    # the same sum with the uplift assumption at its pessimistic and optimistic ends
    low = churn_probability * margin_at_risk * spec["uplift"] * (1 - UPLIFT_UNCERTAINTY) - spec["cost"]
    high = churn_probability * margin_at_risk * spec["uplift"] * (1 + UPLIFT_UNCERTAINTY) - spec["cost"]
    return {
        "intervention": intervention,
        "intervention_label": spec["label"],
        "margin_at_risk": round(margin_at_risk, 2),
        "cost": spec["cost"],
        "expected_save": round(expected_save, 2),
        "expected_value": round(value, 2),
        "value_range": (round(low, 2), round(high, 2)),
        "robust": low > 0,          # still pays if the uplift is half what we assume
        "worth_doing": expected_save > spec["cost"],
    }


def break_even_probability(margin_at_risk: float, intervention: str) -> float:
    """How likely churn must be before this intervention pays for itself.

    The mirror of break_even_margin: with the customer's value fixed, this is
    the probability that makes the sum work. Printing both turns "not worth
    it" into two specific numbers that would change the answer.
    """
    spec = INTERVENTIONS[intervention]
    if margin_at_risk <= 0 or spec["uplift"] <= 0:
        return float("inf")
    return spec["cost"] / (margin_at_risk * spec["uplift"])


def break_even_margin(churn_probability: float, intervention: str) -> float:
    """How much margin must be at risk before this intervention pays for itself.

    cost = p x margin x uplift  ->  margin = cost / (p x uplift). Printing this
    next to a negative expected value turns "not worth it" into "not worth it
    YET, and here is the number that would change that".
    """
    spec = INTERVENTIONS[intervention]
    if churn_probability <= 0 or spec["uplift"] <= 0:
        return float("inf")
    return spec["cost"] / (churn_probability * spec["uplift"])


def plan(verdict: dict, churn_probability: float, avg_order_value: float,
         orders_per_month: float, open_categories=()) -> dict:
    """The whole recommendation for one customer.

    If the matched intervention loses money, fall back to the cheapest thing
    that does pay - usually the automated email - rather than recommending a
    spend the numbers do not support.
    """
    intervention = choose_intervention(verdict, open_categories)
    result = expected_value(churn_probability, avg_order_value,
                            orders_per_month, intervention)
    if not result["worth_doing"] and intervention != "none":
        fallback = expected_value(churn_probability, avg_order_value,
                                  orders_per_month, "email_nudge")
        if fallback["worth_doing"]:
            fallback["downgraded_from"] = intervention
            result = fallback
    # break-even for the intervention the problem actually calls for: when we
    # downgrade, this is the number that would justify the real fix
    result["break_even_margin"] = round(
        break_even_margin(churn_probability, intervention), 2)
    result["break_even_probability"] = round(
        break_even_probability(result["margin_at_risk"], intervention), 4)
    return result


# --- what the customer is worth, and what is broken for them (as of the cutoff) ---
RECENT_DAYS = 90


def customer_money(conn, user_id: int, as_of: str) -> dict:
    """Average order value and orders per month, from before `as_of`.

    The rate comes from the last 90 days: a customer who ordered weekly two
    years ago and monthly since is worth the monthly number today.
    """
    recent = conn.execute(
        """SELECT AVG(total_amount), COUNT(*) FROM orders
           WHERE user_id=? AND placed_at < ? AND placed_at >= datetime(?, '-90 days')""",
        (user_id, as_of, as_of),
    ).fetchone()
    lifetime_aov = conn.execute(
        "SELECT AVG(total_amount) FROM orders WHERE user_id=? AND placed_at < ?",
        (user_id, as_of),
    ).fetchone()[0]
    aov = recent[0] if recent[0] is not None else lifetime_aov
    return {
        "avg_order_value": float(aov or 0.0),
        "orders_per_month": (recent[1] or 0) / (RECENT_DAYS / 30),
    }


def open_complaint_categories(conn, user_id: int, as_of: str) -> list[str]:
    """Categories of the customer's still-unresolved serious complaints."""
    rows = conn.execute(
        f"""SELECT category FROM support_tickets
            WHERE user_id=? AND created_at < ?
              AND (resolved_at IS NULL OR resolved_at >= ?)
              AND category IN ({','.join('?' * len(SERIOUS_CATEGORIES))})
            GROUP BY category ORDER BY MAX(created_at) DESC""",
        (user_id, as_of, as_of, *SERIOUS_CATEGORIES),
    ).fetchall()
    return [r[0] for r in rows]
