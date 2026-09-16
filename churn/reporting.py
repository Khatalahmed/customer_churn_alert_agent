"""
reporting.py

WHAT : Read-only views over things the project already computes, shaped for a
       UI: the population's risk profile, a customer's event timeline, the
       model's per-customer feature contributions, the last agent run and its
       trace, the evaluation metrics, the agent-reliability checks, the
       intervention economics and the outcome experiment.
WHY  : Every number here already existed - in a printed table, a JSON file on
       disk, or a function nobody had called from a request. A frontend that
       cannot reach them would have to hard-code them, which is how a
       dashboard ends up showing figures the code stopped producing months
       ago. Nothing in this module computes a new result or changes a model.
FLOW : api.py calls these; each returns plain dicts, and each says when the
       thing it reports on has not been produced yet rather than inventing it.
LOGIC: "unavailable" is a real answer. Every loader returns
       {"available": False, "reason": ..., "how": ...} when its artefact is
       missing, so the UI can say "run this command" instead of rendering a
       zero that looks like a measurement.
"""
import json
from pathlib import Path

from .actions import (CURRENCY, INTERVENTIONS, MARGIN_RATE, MONTHLY_DISCOUNT,
                      MONTHLY_SURVIVAL, UPLIFT_UNCERTAINTY, VALUE_HORIZON_MONTHS,
                      break_even_margin, margin_present_value)
from .config import (ACTION_LOG_PATH, METRICS_PATH, PREDICTIONS_PATH, TRACE_PATH,
                     analysis_time, connect_readonly, reference_now)

# Which command produces each artefact. Passed in by the caller rather than
# looked up by file name: the hint is about the pipeline step, not the path,
# and a renamed or relocated file should not silently lose its instructions.
TRAIN = "uv run python -m churn.train_model"
AGENT = "uv run python -m churn.main"
LOOP = "uv run python -m churn.outcomes"


def _load(path: Path, how: str = ""):
    """Read a JSON artefact, or say which command produces it."""
    path = Path(path)
    if not path.exists():
        return None, {"available": False,
                      "reason": f"{path.name} has not been produced yet",
                      "how": how}
    with open(path) as f:
        return json.load(f), None


# --- population ---------------------------------------------------------------

def probability_distribution(scores, bins: int = 20) -> list[dict]:
    """Histogram of churn probability across everyone scored.

    The worklist shows fifteen customers. This is the shape of the other two
    and a half thousand, which is what makes the fifteen meaningful.
    """
    values = sorted(float(s) for s in scores)
    if not values:
        return []
    lo, hi = values[0], values[-1]
    width = (hi - lo) / bins or 1e-9
    counts = [0] * bins
    for v in values:
        counts[min(int((v - lo) / width), bins - 1)] += 1
    return [{"from": round(lo + i * width, 4),
             "to": round(lo + (i + 1) * width, 4),
             "count": c} for i, c in enumerate(counts)]


def customer_search(df, query: str = "", limit: int = 50, offset: int = 0) -> dict:
    """Scored customers, newest risk first, filtered by name or id."""
    rows = df
    if query:
        q = query.strip().lower()
        mask = rows["full_name"].str.lower().str.contains(q, regex=False)
        if q.isdigit():
            mask = mask | (rows["user_id"] == int(q))
        rows = rows[mask]
    total = len(rows)
    page = rows.nlargest(offset + limit, "churn_probability").iloc[offset:offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "customers": [{"user_id": int(r.user_id), "full_name": r.full_name,
                       "churn_probability": round(float(r.churn_probability), 4)}
                      for r in page.itertuples()],
    }


# --- one customer -------------------------------------------------------------

def customer_timeline(conn, user_id: int, as_of: str) -> dict:
    """Every observable event for one customer, before the analysis time.

    Orders, logins, reviews and tickets on one axis: this is the trajectory a
    retention person reconstructs by hand today, and the thing the model is
    reacting to.
    """
    cur = conn.cursor()
    events = []
    for row in cur.execute(
            """SELECT placed_at, order_status, total_amount FROM orders
               WHERE user_id = ? AND placed_at < ? ORDER BY placed_at""",
            (user_id, as_of)):
        events.append({"at": row[0], "type": "order", "label": row[1].title().replace("_", " "),
                       "amount": round(float(row[2] or 0), 2),
                       "tone": "bad" if row[1] == "CANCELLED" else "neutral"})
    for row in cur.execute(
            """SELECT created_at, category, status, subject, resolved_at
               FROM support_tickets WHERE user_id = ? AND created_at < ?
               ORDER BY created_at""", (user_id, as_of)):
        unresolved = row[4] is None or row[4] >= as_of
        events.append({"at": row[0], "type": "ticket",
                       "label": row[3], "category": row[1],
                       "status": row[2].replace("_", " ").title(),
                       "unresolved": unresolved,
                       "tone": "bad" if unresolved else "neutral"})
    for row in cur.execute(
            """SELECT created_at, rating, review_title, review_text FROM reviews
               WHERE user_id = ? AND created_at < ? ORDER BY created_at""",
            (user_id, as_of)):
        events.append({"at": row[0], "type": "review", "rating": int(row[1]),
                       "label": row[2], "text": row[3],
                       "tone": "bad" if row[1] <= 2 else "good" if row[1] >= 4 else "neutral"})
    logins = [{"at": r[0], "count": r[1]} for r in cur.execute(
        """SELECT date(event_timestamp) AS day, COUNT(*) FROM auth_audit_log
           WHERE user_id = ? AND event_type = 'LOGIN' AND event_timestamp < ?
           GROUP BY day ORDER BY day""", (user_id, as_of))]
    events.sort(key=lambda e: e["at"])
    return {"as_of": as_of, "events": events, "logins_by_day": logins}


def feature_contributions(user_id: int, as_of: str, top_n: int = 6) -> dict:
    """What pushed THIS customer's score up, from the model itself (SHAP).

    Signed contributions on the raw booster, which is what SHAP can explain -
    the shipped model is a calibrated ensemble on top of it, so these explain
    the ranking, not the calibrated probability. They are a statement about
    the model's arithmetic, never about what caused the customer's behaviour.
    """
    import joblib
    import shap

    from .config import MODEL_PATH
    from .explain import FRIENDLY
    from .features import build_features

    bundle = joblib.load(MODEL_PATH)
    model, cols = bundle.get("tree_model", bundle["model"]), bundle["features"]
    df, _ = build_features(as_of=as_of)
    row = df[df["user_id"] == user_id]
    if row.empty:
        return {"available": False, "reason": "not an active customer at this time"}

    values = shap.TreeExplainer(model).shap_values(row[cols])[0]
    ranked = sorted(zip(cols, values, row[cols].iloc[0]), key=lambda x: -abs(x[1]))[:top_n]
    return {
        "available": True,
        "basis": "SHAP values on the raw booster (explains the ranking, not causality)",
        "factors": [{"feature": name,
                     "label": FRIENDLY.get(name, name.replace("_", " ")),
                     "value": None if value != value else round(float(value), 3),
                     "contribution": round(float(shap_value), 4),
                     "direction": "raises risk" if shap_value > 0 else "lowers risk"}
                    for name, shap_value, value in ranked],
    }


# --- the agent run ------------------------------------------------------------

def investigations() -> dict:
    """The last agent run: one entry per customer, plus the run's tool calls."""
    predictions, missing = _load(PREDICTIONS_PATH, AGENT)
    if missing:
        return missing
    trace, trace_missing = _load(TRACE_PATH, AGENT)
    calls = [] if trace_missing else trace.get("calls", [])
    return {
        "available": True,
        "customers": predictions,
        "tool_calls": len(calls),
        "trace_available": not trace_missing,
    }


def investigation(user_id: int) -> dict:
    """One customer's investigation: the verdict, and the calls that produced it."""
    predictions, missing = _load(PREDICTIONS_PATH, AGENT)
    if missing:
        return missing
    match = [p for p in predictions if p["user_id"] == user_id]
    if not match:
        return {"available": False,
                "reason": f"user {user_id} was not in the last agent run",
                "how": AGENT}
    trace, trace_missing = _load(TRACE_PATH, AGENT)
    calls = [] if trace_missing else trace.get("calls", [])
    mine = [c for c in calls if c.get("args", {}).get("user_id") == user_id]
    shared = [c for c in calls if "user_id" not in c.get("args", {})]
    return {"available": True, "customer": match[0],
            "steps": shared + mine, "trace_available": not trace_missing}


# --- evaluation ---------------------------------------------------------------

def evaluations() -> dict:
    """What the last training run measured, exactly as it measured it."""
    metrics, missing = _load(METRICS_PATH, TRAIN)
    return missing or {"available": True, **metrics}


def reliability() -> dict:
    """The three agent checks, recomputed from the saved run.

    Evidence fidelity (are the schema numbers true?), prose fidelity (are the
    sentences true?), and the trajectory rules (did it work properly?). These
    run against the database on request rather than being cached, so the page
    cannot show a pass that no longer holds.
    """
    predictions, missing = _load(PREDICTIONS_PATH, AGENT)
    if missing:
        return missing
    from .prose_eval import verify_prose
    from .trace_eval import check_trajectory
    from .verifier import verify

    conn = connect_readonly()
    evidence = verify(conn, predictions)
    prose = verify_prose(conn, predictions)
    conn.close()

    trace, trace_missing = _load(TRACE_PATH, AGENT)
    rules = [] if trace_missing else check_trajectory(trace.get("calls", []), predictions)
    calls = [] if trace_missing else trace.get("calls", [])
    return {
        "available": True,
        "customers": len(predictions),
        "evidence": {"checked": evidence["total_fields"], "matched": evidence["matched_fields"],
                     "fidelity": round(evidence["fidelity"], 4),
                     "failures": evidence["mismatches"]},
        "prose": {"claims": prose["total_claims"], "supported": prose["passed_claims"],
                  "fidelity": round(prose["fidelity"], 4),
                  "coverage": round(prose["coverage"], 4),
                  "unchecked_clauses": prose["unchecked_clauses"],
                  "failures": {str(k): [c["claim"] for c in v]
                               for k, v in prose["failures"].items()}},
        "trajectory": {"rules": rules,
                       "passed": sum(1 for r in rules if r["passed"]),
                       "total": len(rules),
                       "tool_calls": len(calls),
                       "errors": sum(1 for c in calls if not c.get("ok", True))},
    }


def outcomes() -> dict:
    """The intervention experiment: what happened, and what it proves."""
    log, missing = _load(ACTION_LOG_PATH, LOOP)
    if missing:
        return missing
    from .eval import future_churners
    from .outcomes import horizon_passed, measure_uplift

    conn = connect_readonly()
    now = reference_now(conn)
    conn.close()
    if not horizon_passed(log, now):
        return {"available": False,
                "reason": "the horizon has not passed yet - nothing to measure",
                "how": "wait for the outcome window to close"}
    result = measure_uplift(log, future_churners(log["analysis_time"]))
    return {"available": True, "analysis_time": log["analysis_time"],
            "horizon_days": log["horizon_days"], **result}


# --- economics ----------------------------------------------------------------

def economics(example_probability: float = 0.14) -> dict:
    """The intervention menu and the assumptions behind every rupee figure.

    The spec for this project calls these illustrative, and so does this
    payload: they are a decision model with numbers filled in, not a measured
    business result. Hiding them in a constants block is what makes an
    expected value look like a fact.
    """
    monthly = 1000.0
    return {
        "available": True,
        "currency": CURRENCY,
        "illustrative": True,
        "note": ("risk is predicted over 14 days; saved margin is valued over 12 months. "
                 "Costs and intervention uplifts are assumptions, not measured business results."),
        "assumptions": {
            "margin_rate": MARGIN_RATE,
            "monthly_survival": MONTHLY_SURVIVAL,
            "monthly_discount": MONTHLY_DISCOUNT,
            "value_horizon_months": VALUE_HORIZON_MONTHS,
            "uplift_uncertainty": UPLIFT_UNCERTAINTY,
            "present_value_of_1000_per_month": round(margin_present_value(monthly), 2),
            "months_equivalent": round(margin_present_value(monthly) / monthly, 2),
        },
        "example_probability": example_probability,
        "interventions": [
            {"key": key,
             "label": spec["label"],
             "assumed_uplift": spec["assumed_uplift"],
             "uplift_source": "assumed",
             "cost": spec["cost"],
             "break_even_margin": (None if spec["assumed_uplift"] <= 0 else
                                   round(break_even_margin(example_probability, key), 2))}
            for key, spec in INTERVENTIONS.items()
        ],
    }


def analysis_times(conn) -> dict:
    """What point in time everything on the screen is talking about."""
    return {"analysis_time": analysis_time(conn), "dataset_reference_time": reference_now(conn)}
