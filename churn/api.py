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

from .actions import CURRENCY, customer_money, open_complaint_categories, plan
from .config import analysis_time, connect_readonly, reference_now
from .memory import mark_contacted, recently_contacted_ids
from .rubric import assess
from .scoring import score_customers
from .verifier import real_facts

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
    customers = [_customer_view(conn, row, as_of) for _, row in shortlist.iterrows()]
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
