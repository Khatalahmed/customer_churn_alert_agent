"""
api.py

WHAT : A small HTTP service over the scoring pipeline: health, the worklist,
       one customer's risk with its recommended intervention, and marking
       customers as contacted.
WHY   : A batch script produces a file once a day. A retention team works in
       a CRM and asks "why is this customer flagged?" while the customer is
       on the phone. That needs an endpoint, and it needs to answer in
       milliseconds - so the LLM is NOT in this path. Everything served here
       is the model plus the code rubric, both deterministic.
FLOW  : the scored table is built once per analysis time and cached; each
        request reads facts for the customers it needs, applies the rubric,
        and prices the intervention.
RUN   : uv run uvicorn churn.api:app --reload
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .actions import (CURRENCY, customer_money, customer_money_batch,
                       open_complaint_categories, open_complaint_categories_batch, plan)
from .config import analysis_time, connect_readonly, reference_now
from .memory import mark_contacted, recently_contacted_ids
from . import reporting
from .rubric import assess
from .scoring import score_customers
from .verifier import real_facts, real_facts_batch

app = FastAPI(
    title="Churn early-warning",
    summary="Who is about to leave, why, and what it is worth doing about it.",
    version="1.0",
)

_cache: dict = {}


def _scored():
    """The scored table for the current analysis time, built once."""
    conn = connect_readonly()
    as_of = analysis_time(conn)
    conn.close()
    if _cache.get("as_of") != as_of:
        _cache.clear()
        _cache["as_of"] = as_of
        _cache["df"] = score_customers(as_of)
    return _cache["as_of"], _cache["df"]


def _customer_view(conn, row, as_of: str) -> dict:
    """Risk, evidence and the priced intervention for one scored customer."""
    uid = int(row["user_id"])
    facts = real_facts(conn, uid, as_of)
    verdict = assess(facts)
    money = customer_money(conn, uid, as_of)
    action = plan(verdict, float(row["churn_probability"]), money["avg_order_value"],
                  money["orders_per_month"], open_complaint_categories(conn, uid, as_of))
    return {
        "user_id": uid,
        "full_name": row["full_name"],
        "churn_probability": round(float(row["churn_probability"]), 4),
        **verdict,
        "evidence": facts,
        **money,
        **action,
        "currency": CURRENCY,
    }


def _customer_views_batch(conn, shortlist, as_of: str) -> list[dict]:
    """Build the risk+evidence+action view for every customer in shortlist.

    Replaces the per-customer loop that called _customer_view() N times
    (45 queries for top_n=15) with 7 queries regardless of shortlist size:
      1-4  real_facts_batch  (logins, orders, tickets, serious+worst)
      5-6  customer_money_batch  (recent AOV + count, lifetime AOV fallback)
      7    open_complaint_categories_batch
    """
    user_ids = [int(row["user_id"]) for _, row in shortlist.iterrows()]
    all_facts      = real_facts_batch(conn, user_ids, as_of)
    all_money      = customer_money_batch(conn, user_ids, as_of)
    all_categories = open_complaint_categories_batch(conn, user_ids, as_of)

    result = []
    for _, row in shortlist.iterrows():
        uid = int(row["user_id"])
        facts      = all_facts.get(uid, {})
        money      = all_money.get(uid, {"avg_order_value": 0.0, "orders_per_month": 0.0})
        categories = all_categories.get(uid, [])
        verdict    = assess(facts)
        action     = plan(verdict, float(row["churn_probability"]),
                          money["avg_order_value"], money["orders_per_month"], categories)
        result.append({
            "user_id": uid,
            "full_name": row["full_name"],
            "churn_probability": round(float(row["churn_probability"]), 4),
            **verdict,
            "evidence": facts,
            **money,
            **action,
            "currency": CURRENCY,
        })
    return result


class ContactedRequest(BaseModel):
    user_ids: list[int] = Field(description="Customers the team has just contacted")


@app.get("/health", summary="Is the service ready, and what is it looking at?")
def health() -> dict:
    conn = connect_readonly()
    reference, as_of = reference_now(conn), analysis_time(conn)
    conn.close()
    _, df = _scored()
    return {
        "status": "ok",
        "dataset_reference_time": reference,
        "analysis_time": as_of,
        "active_customers": len(df),
        "recently_contacted": len(recently_contacted_ids(days=30)),
    }


@app.get("/worklist", summary="Who to act on today, most valuable first")
def worklist(top_n: int = 15) -> dict:
    as_of, df = _scored()
    skip = recently_contacted_ids(days=30)
    shortlist = df[~df["user_id"].isin(skip)].nlargest(top_n, "churn_probability")

    conn = connect_readonly()
    # Batch path: 7 queries total regardless of shortlist size.
    # The single-customer path (/customers/{id}) still uses _customer_view().
    customers = _customer_views_batch(conn, shortlist, as_of)
    conn.close()

    customers.sort(key=lambda c: c["expected_value"], reverse=True)
    worth = [c for c in customers if c["worth_doing"]]
    return {
        "analysis_time": as_of,
        "customers": customers,
        "worth_doing": len(worth),
        "expected_value_total": round(sum(c["expected_value"] for c in worth), 2),
        "note": "expected values are illustrative - uplift and margin are assumptions",
    }


@app.get("/customers/{user_id}", summary="Why is this customer flagged?")
def customer(user_id: int) -> dict:
    as_of, df = _scored()
    rows = df[df["user_id"] == user_id]
    if rows.empty:
        raise HTTPException(
            status_code=404,
            detail=f"user {user_id} is not an active customer at {as_of} "
                   "(no login in the 28 days before it), so there is nothing to score",
        )
    conn = connect_readonly()
    view = _customer_view(conn, rows.iloc[0], as_of)
    conn.close()
    view["contacted_recently"] = user_id in recently_contacted_ids(days=30)
    return view


@app.post("/contacted", summary="Record outreach so the next run does not re-flag them")
def contacted(request: ContactedRequest) -> dict:
    marked = mark_contacted(request.user_ids)
    return {"marked": marked, "skipped_for_days": 30}


# --- read-only views for the UI ----------------------------------------------
# Everything below serves a computation that already existed. None of it
# changes a model, a rubric or an economic assumption; where an artefact has
# not been produced yet, the payload says so and names the command, so the
# interface can show "not measured" instead of a zero.


@app.get("/overview", summary="What needs attention right now")
def overview(top_n: int = 15) -> dict:
    as_of, df = _scored()
    work = worklist(top_n=top_n)
    mix = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for c in work["customers"]:
        mix[c["risk_level"]] += 1
    return {
        "analysis_time": as_of,
        "scored_customers": len(df),
        "shortlist_size": len(work["customers"]),
        "risk_mix": mix,
        "risk_mix_scope": f"the {len(work['customers'])}-customer shortlist, not the whole base",
        "margin_at_risk": round(sum(c["margin_at_risk"] for c in work["customers"]), 2),
        "intervention_cost": round(sum(c["cost"] for c in work["customers"]), 2),
        "expected_value_total": work["expected_value_total"],
        "worth_doing": work["worth_doing"],
        "probability_distribution": reporting.probability_distribution(df["churn_probability"]),
        "currency": CURRENCY,
        "note": work["note"],
    }


@app.get("/customers", summary="Search scored customers")
def customers(q: str = "", limit: int = 50, offset: int = 0) -> dict:
    as_of, df = _scored()
    return {"analysis_time": as_of, **reporting.customer_search(df, q, limit, offset)}


def _require_scored(user_id: int) -> str:
    """The analysis time, or a 404 that explains why this customer has none."""
    as_of, df = _scored()
    if df[df["user_id"] == user_id].empty:
        raise HTTPException(
            status_code=404,
            detail=f"user {user_id} is not an active customer at {as_of}, "
                   "so there is nothing to show")
    return as_of


@app.get("/customers/{user_id}/timeline", summary="Everything this customer did, in order")
def customer_timeline(user_id: int) -> dict:
    as_of = _require_scored(user_id)
    conn = connect_readonly()
    result = reporting.customer_timeline(conn, user_id, as_of)
    conn.close()
    return result


@app.get("/customers/{user_id}/explanation", summary="Why the model scored them this way")
def customer_explanation(user_id: int) -> dict:
    return reporting.feature_contributions(user_id, _require_scored(user_id))


@app.get("/investigations", summary="The last agent run")
def investigations() -> dict:
    return reporting.investigations()


@app.get("/investigations/{user_id}", summary="One investigation and its tool calls")
def investigation(user_id: int) -> dict:
    return reporting.investigation(user_id)


@app.get("/evaluations", summary="What the last training run measured")
def evaluations() -> dict:
    return reporting.evaluations()


@app.get("/reliability", summary="Evidence, prose and trajectory checks on the agent run")
def reliability() -> dict:
    return reporting.reliability()


@app.get("/outcomes", summary="The hold-out experiment and what it concludes")
def outcomes() -> dict:
    return reporting.outcomes()


@app.get("/economics", summary="Intervention menu and the assumptions behind every figure")
def economics() -> dict:
    return reporting.economics()
