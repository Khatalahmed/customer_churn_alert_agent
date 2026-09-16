"""
test_churn.py

WHAT : Unit tests for the deterministic parts of the system (no LLM). They
       run fast and free, so a broken feature, tool, or model is caught
       automatically - locally and in CI.
WHY  : The agent needs an LLM + API key, but the data, features, tools,
       model, memory, and drift maths are all deterministic and testable.
       Testing these guards against regressions when the code changes.
"""
import json

import numpy as np
import pandas as pd
import pytest

from churn.features import add_labels, build_features, FEATURE_COLS
from churn.config import MODEL_PATH
from churn.drift import psi


def test_features_shape():
    df, cols = build_features()
    assert cols == FEATURE_COLS
    assert 0 < len(df) < 3000                    # only customers active at the analysis time
    assert df["user_id"].is_unique
    assert "churned" not in df.columns          # scoring must not need the answer key
    labelled = add_labels(df)
    assert labelled["churned"].isin([0, 1]).all()
    assert len(labelled) <= len(df)             # already-churned customers are dropped


def test_features_ignore_everything_after_the_cutoff(tmp_path):
    # point-in-time guarantee: deleting all data from after the cutoff must not
    # change a single feature value
    import shutil
    import sqlite3
    from churn.config import DB_PATH, analysis_time, connect_readonly
    conn = connect_readonly()
    as_of = analysis_time(conn)
    conn.close()
    past = tmp_path / "past.db"
    shutil.copy(DB_PATH, past)
    c = sqlite3.connect(past)
    c.execute("DELETE FROM auth_audit_log WHERE event_timestamp >= ?", (as_of,))
    c.execute("DELETE FROM orders WHERE placed_at >= ?", (as_of,))
    c.execute("DELETE FROM support_tickets WHERE created_at >= ?", (as_of,))
    c.execute("DELETE FROM reviews WHERE created_at >= ?", (as_of,))
    # a ticket resolved after the cutoff was still open at the cutoff
    c.execute("UPDATE support_tickets SET status='OPEN', resolved_at=NULL "
              "WHERE resolved_at >= ?", (as_of,))
    c.commit()
    c.close()
    full, _ = build_features(as_of=as_of)
    trimmed, _ = build_features(as_of=as_of, db_path=past)
    pd.testing.assert_frame_equal(full, trimmed)


def test_labels_are_strictly_future_and_each_churn_counted_once():
    from datetime import datetime, timedelta
    from churn.config import HORIZON_DAYS, TEST_CUTOFF_DAYS, TRAIN_CUTOFFS_DAYS, TRUTH_PATH
    from churn.features import build_snapshots
    # training label windows end where the test window starts
    assert min(TRAIN_CUTOFFS_DAYS) - HORIZON_DAYS >= TEST_CUTOFF_DAYS
    snaps, _ = build_snapshots(list(TRAIN_CUTOFFS_DAYS) + [TEST_CUTOFF_DAYS])
    truth = {r["user_id"]: r for r in json.load(open(TRUTH_PATH))}
    positives = snaps[snaps["churned"] == 1]
    assert len(positives) > 0
    assert positives["user_id"].is_unique        # one churn event -> exactly one snapshot
    for row in snaps.itertuples():
        t = datetime.fromisoformat(row.as_of)
        r = truth[row.user_id]
        if r["churned"]:
            until = datetime.fromisoformat(r["active_until"])
            assert until > t                     # already-churned customers are never scored
            assert row.churned == int(until <= t + timedelta(days=HORIZON_DAYS))


def test_scoring_works_without_answer_key_from_any_directory(tmp_path, monkeypatch):
    import pytest
    import churn.features as features
    from churn.scoring import score_customers
    # hide the answer key, and run from an unrelated directory
    monkeypatch.setattr(features, "TRUTH_PATH", tmp_path / "missing.json")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):       # proves the answer key is really hidden
        add_labels(build_features()[0])
    df = score_customers()
    assert len(df) == len(build_features()[0])
    assert df["churn_probability"].between(0, 1).all()


def test_churn_candidates_tool_returns_ranked_json(tmp_path, monkeypatch):
    import churn.memory as memory
    from churn.scoring import get_churn_candidates
    # empty contact log, so no customer is skipped
    monkeypatch.setattr(memory, "STORE_PATH", tmp_path / "contacted.json")
    data = json.loads(get_churn_candidates.invoke({"top_n": 5}))
    assert len(data) == 5
    # the shortlist is CHOSEN by churn risk...
    from churn.scoring import score_customers
    riskiest = set(score_customers().nlargest(5, "churn_probability")["user_id"])
    assert {c["user_id"] for c in data} == riskiest
    # ...and ORDERED by value at risk, so the team calls the biggest loss first
    scores = [c["priority_score"] for c in data]
    assert scores == sorted(scores, reverse=True)


def test_token_prices_come_from_env(monkeypatch):
    from churn.utils import token_prices
    monkeypatch.delenv("MODEL_PRICE_IN_PER_M", raising=False)
    monkeypatch.delenv("MODEL_PRICE_OUT_PER_M", raising=False)
    assert token_prices() is None                 # unknown, not a wrong guess
    monkeypatch.setenv("MODEL_PRICE_IN_PER_M", "0.5")
    monkeypatch.setenv("MODEL_PRICE_OUT_PER_M", "1.5")
    assert token_prices() == (0.5, 1.5)


def test_azure_provider_is_keyless_and_configured_from_env(monkeypatch):
    import pytest
    from langchain_openai import AzureChatOpenAI, ChatOpenAI
    from churn.utils import get_model
    monkeypatch.setenv("MODEL_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    # v1 API (the default): OpenAI-compatible URL, deployment as the model name
    monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
    model = get_model()                          # builds offline; token fetched lazily
    assert type(model) is ChatOpenAI
    assert model.openai_api_base == "https://example.openai.azure.com/openai/v1/"
    assert model.model_name == "test-deployment"
    assert model.use_responses_api is True       # tools + reasoning need /responses

    # a dated API version uses the classic Azure client, still keyless
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    model = get_model()
    assert isinstance(model, AzureChatOpenAI)
    assert model.deployment_name == "test-deployment"
    assert model.azure_ad_token_provider is not None   # Entra ID, not an API key

    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT")
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        get_model()


def _good_trace(user_ids):
    """The trace a correct run produces: rank once, then tickets+reviews each."""
    calls = [{"tool": "get_churn_candidates", "args": {"top_n": len(user_ids)}, "ok": True, "ms": 40}]
    for uid in user_ids:
        calls.append({"tool": "get_user_tickets", "args": {"user_id": uid}, "ok": True, "ms": 5})
        calls.append({"tool": "get_user_reviews", "args": {"user_id": uid}, "ok": True, "ms": 5})
    return calls


def _failing_rules(calls, preds):
    from churn.trace_eval import check_trajectory
    return {r["rule"] for r in check_trajectory(calls, preds) if not r["passed"]}


def test_trajectory_passes_on_a_correct_run():
    ids = [1, 2, 3]
    preds = [_pred(uid, "HIGH") for uid in ids]
    assert _failing_rules(_good_trace(ids), preds) == set()


def test_trajectory_catches_each_kind_of_bug():
    ids = [1, 2, 3]
    preds = [_pred(uid, "HIGH") for uid in ids]

    # skipped the review check for user 3
    calls = [c for c in _good_trace(ids)
             if not (c["tool"] == "get_user_reviews" and c["args"].get("user_id") == 3)]
    assert "checked reviews for every customer" in _failing_rules(calls, preds)

    # investigated someone who was never shortlisted
    calls = _good_trace(ids) + [{"tool": "get_user_tickets", "args": {"user_id": 99}, "ok": True}]
    assert "investigated nobody off the shortlist" in _failing_rules(calls, preds)

    # looped on the same customer
    calls = _good_trace(ids) + [{"tool": "get_user_tickets", "args": {"user_id": 1}, "ok": True}]
    assert "no customer investigated twice" in _failing_rules(calls, preds)

    # investigated before ranking
    ranker, *rest = _good_trace(ids)
    calls = rest + [ranker]
    assert "ranks before investigating" in _failing_rules(calls, preds)

    # ranked twice
    calls = _good_trace(ids) + [{"tool": "get_churn_candidates", "args": {"top_n": 3}, "ok": True}]
    assert "ranks exactly once" in _failing_rules(calls, preds)

    # reached for a tool it was never given
    calls = _good_trace(ids) + [{"tool": "run_sql", "args": {}, "ok": True}]
    assert "used only the tools it was given" in _failing_rules(calls, preds)

    # a tool call errored
    calls = _good_trace(ids)
    calls[1] = {**calls[1], "ok": False}
    assert "no tool call errored" in _failing_rules(calls, preds)


def test_rubric_verdicts_do_not_drift():
    # regression eval: these fact patterns must always produce these verdicts
    from churn.rubric import assess
    golden = {
        ("complaint + fading", 2, 0, 10, 1): "HIGH",
        ("low review + silent", 0, 1, 0, 0): "HIGH",
        ("complaint + engaged", 1, 0, 2, 9): "MEDIUM",
        ("happy + fading", 0, 5, 10, 1): "MEDIUM",
        ("happy + engaged", 0, 5, 2, 9): "LOW",
        ("silent reviews + engaged", 0, 0, 2, 9): "LOW",
        ("3-star + engaged", 0, 3, 2, 9): "LOW",
    }
    for (label, serious, worst, prev, recent), expected in golden.items():
        facts = {"unresolved_serious_tickets": serious, "worst_review_rating": worst,
                 "logins_prev_30_60d": prev, "logins_recent_30d": recent}
        assert assess(facts)["risk_level"] == expected, label


def test_promotion_never_overwrites_the_evaluated_model(tmp_path):
    import joblib
    from churn.config import MODEL_PATH
    from churn.retrain import promote
    before = MODEL_PATH.read_bytes()
    out = tmp_path / "production.pkl"
    info = promote(cutoffs=[70, 56, 42], path=out)
    assert out.exists() and info["churn"] > 0
    # the evaluated model is untouched, and production is flagged unsafe to report on
    assert MODEL_PATH.read_bytes() == before
    assert joblib.load(out)["evaluation_safe"] is False


def test_control_group_is_random_and_reproducible():
    from churn.outcomes import assign_control
    ids = list(range(1, 21))
    control = assign_control(ids, fraction=0.3, seed=42)
    assert len(control) == 6                      # 30% held back
    assert control == assign_control(ids, fraction=0.3, seed=42)   # reproducible
    assert control != assign_control(ids, fraction=0.3, seed=7)    # not fixed
    assert control < set(ids)


def test_uplift_measures_what_happened(tmp_path):
    from churn.outcomes import log_actions, measure_uplift
    worklist = {"analysis_time": "2026-08-04 06:30:00", "customers": [
        {"user_id": i, "churn_probability": 0.2, "expected_value": 10,
         "intervention": "coupon"} for i in range(1, 21)]}
    log = log_actions(worklist, path=tmp_path / "log.json", seed=42)
    treated = {e["user_id"] for e in log["entries"] if e["group"] == "treated"}
    control = {e["user_id"] for e in log["entries"] if e["group"] == "control"}
    assert treated and control and not (treated & control)

    # nobody churns in either group -> no uplift, and we say so
    flat = measure_uplift(log, churned_ids=set())
    assert flat["uplift"] == 0.0

    # every control churns, no treated does -> the maximum possible uplift
    perfect = measure_uplift(log, churned_ids=control)
    assert perfect["uplift"] == 1.0
    assert perfect["treated"]["churn_rate"] == 0.0
    assert perfect["control"]["churn_rate"] == 1.0


def test_horizon_gate_blocks_early_measurement(tmp_path):
    from churn.outcomes import horizon_passed
    log = {"analysis_time": "2026-08-04 06:30:00", "horizon_days": 14}
    assert not horizon_passed(log, "2026-08-10 06:30:00")   # too early to know
    assert horizon_passed(log, "2026-08-18 06:30:00")


def test_api_serves_health_worklist_and_one_customer(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import churn.memory as memory
    from churn.api import app
    monkeypatch.setattr(memory, "STORE_PATH", tmp_path / "contacted.json")
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["status"] == "ok" and health["active_customers"] > 0
    assert health["analysis_time"] == health["analysis_time"]

    work = client.get("/worklist", params={"top_n": 5}).json()
    assert len(work["customers"]) == 5
    values = [c["expected_value"] for c in work["customers"]]
    assert values == sorted(values, reverse=True)       # most valuable first
    first = work["customers"][0]
    assert first["risk_level"] in ("HIGH", "MEDIUM", "LOW")
    assert 0 <= first["churn_probability"] <= 1
    assert "intervention_label" in first and "evidence" in first

    # one customer, with the reason a CRM would show
    detail = client.get(f"/customers/{first['user_id']}").json()
    assert detail["user_id"] == first["user_id"]
    assert detail["evidence"]["logins_recent_30d"] >= 0

    # a customer who is not active gets a 404 that explains itself
    missing = client.get("/customers/999999")
    assert missing.status_code == 404
    assert "not an active customer" in missing.json()["detail"]


def test_api_records_outreach(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import churn.memory as memory
    from churn.api import app
    monkeypatch.setattr(memory, "STORE_PATH", tmp_path / "contacted.json")
    client = TestClient(app)
    assert client.post("/contacted", json={"user_ids": [1, 2, 3]}).json()["marked"] == 3
    assert memory.recently_contacted_ids() == {1, 2, 3}


def test_pipeline_builds_a_priced_worklist(tmp_path, monkeypatch):
    import churn.memory as memory
    from churn.pipeline import build_worklist
    monkeypatch.setattr(memory, "STORE_PATH", tmp_path / "contacted.json")
    work = build_worklist(top_n=5)
    assert len(work["customers"]) == 5
    assert work["scored"] > 100
    assert all("expected_value" in c for c in work["customers"])
    # the summary adds up
    worth = [c for c in work["customers"] if c["worth_doing"]]
    assert work["worth_doing"] == len(worth)
    assert work["expected_value_total"] == pytest.approx(
        round(sum(c["expected_value"] for c in worth), 2))


def test_intervention_matches_the_problem():
    from churn.actions import choose_intervention
    unhappy = {"risk_level": "HIGH", "dissatisfaction": True, "disengagement": True}
    quiet = {"risk_level": "MEDIUM", "dissatisfaction": False, "disengagement": True}
    fine = {"risk_level": "LOW", "dissatisfaction": False, "disengagement": False}
    # fix the actual complaint, do not paper over it with a coupon
    assert choose_intervention(unhappy, ["REFUND"]) == "resolve_open_ticket"
    assert choose_intervention(unhappy, ["DELIVERY_DELAY"]) == "delivery_credit"
    assert choose_intervention(unhappy, ["PRODUCT_QUALITY"]) == "replace_item"
    # unhappy without an open ticket (a bad review) -> make it right
    assert choose_intervention(unhappy, []) == "replace_item"
    # quiet but content -> a coupon is exactly what this is for
    assert choose_intervention(quiet, []) == "coupon"
    # nothing wrong -> spend nothing
    assert choose_intervention(fine, ["REFUND"]) == "none"


def test_expected_value_pays_only_when_it_pays():
    from churn.actions import expected_value
    # valuable customer, high risk: worth acting on
    rich = expected_value(0.30, avg_order_value=800, orders_per_month=6,
                          intervention="coupon")
    assert rich["worth_doing"] and rich["expected_value"] > 0
    # same risk, tiny spend: the coupon costs more than it saves
    poor = expected_value(0.30, avg_order_value=80, orders_per_month=0.5,
                          intervention="coupon")
    assert not poor["worth_doing"] and poor["expected_value"] < 0
    # no action costs nothing and saves nothing
    nothing = expected_value(0.9, 800, 6, "none")
    assert nothing["cost"] == 0 and nothing["expected_save"] == 0
    # expected value rises with churn probability
    low, high = (expected_value(p, 800, 6, "coupon")["expected_value"] for p in (0.1, 0.5))
    assert high > low


def test_plan_downgrades_to_something_that_pays():
    from churn.actions import break_even_margin, plan
    unhappy = {"risk_level": "MEDIUM", "dissatisfaction": True, "disengagement": False}
    # modest customer: a Rs 300 replacement cannot pay for itself at 14% risk,
    # so the plan falls back to the near-free email instead of burning money
    modest = plan(unhappy, 0.14, avg_order_value=300, orders_per_month=3,
                  open_categories=["PRODUCT_QUALITY"])
    assert modest["intervention"] == "email_nudge"
    assert modest["downgraded_from"] == "replace_item"
    assert modest["worth_doing"]
    # valuable customer: the real fix pays, so keep it
    valuable = plan(unhappy, 0.14, avg_order_value=2000, orders_per_month=8,
                    open_categories=["PRODUCT_QUALITY"])
    assert valuable["intervention"] == "replace_item" and valuable["worth_doing"]
    # the break-even number says what would change a "no"
    assert break_even_margin(0.14, "coupon") == pytest.approx(150 / (0.14 * 0.15))
    assert break_even_margin(0.0, "coupon") == float("inf")


def test_metrics_precision_recall_and_pr_auc():
    from churn.metrics import calibration_table, pr_auc, precision_at_k, recall_at_k
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])          # base rate 0.2
    perfect = np.array([9, 8, 1, 1, 1, 1, 1, 1, 1, 1])
    assert precision_at_k(y, perfect, 2) == 1.0
    assert recall_at_k(y, perfect, 2) == 1.0
    assert recall_at_k(y, perfect, 1) == 0.5
    # PR-AUC floor is the base rate, not 0.5 - that is why we report it
    assert pr_auc(y, perfect) == 1.0
    import pytest
    assert pr_auc(y, np.zeros(10)) == pytest.approx(0.2)
    # a calibrated model predicts what actually happens
    rows = calibration_table(y, np.array([0.9, 0.9] + [0.1] * 8), bins=5, strategy="width")
    top = [r for r in rows if r["bucket"].startswith("0.800")][0]
    assert top["observed"] == 1.0 and top["n"] == 2


def test_rubric_truth_table():
    # the whole risk decision, in code: two signals -> three levels
    from churn.rubric import assess
    complaint = {"unresolved_serious_tickets": 1, "worst_review_rating": 0}
    low_review = {"unresolved_serious_tickets": 0, "worst_review_rating": 2}
    happy = {"unresolved_serious_tickets": 0, "worst_review_rating": 5}
    fading = {"logins_prev_30_60d": 10, "logins_recent_30d": 2}
    silent = {"logins_prev_30_60d": 0, "logins_recent_30d": 0}
    active = {"logins_prev_30_60d": 2, "logins_recent_30d": 9}

    assert assess(complaint | fading)["risk_level"] == "HIGH"
    assert assess(low_review | silent)["risk_level"] == "HIGH"
    assert assess(complaint | active)["risk_level"] == "MEDIUM"   # unhappy but engaged
    assert assess(happy | fading)["risk_level"] == "MEDIUM"       # quiet but content
    assert assess(happy | active)["risk_level"] == "LOW"
    # things that must NOT count as dissatisfaction
    no_reviews = {"unresolved_serious_tickets": 0, "worst_review_rating": 0}
    three_star = {"unresolved_serious_tickets": 0, "worst_review_rating": 3}
    assert assess(no_reviews | active)["risk_level"] == "LOW"     # silence is not unhappiness
    assert assess(three_star | active)["risk_level"] == "LOW"
    # the action follows the level
    assert assess(complaint | fading)["suggested_action"] == "retention call"
    assert assess(happy | active)["suggested_action"] == "ignore"


def test_agent_schema_cannot_set_the_risk_level():
    # the LLM reports evidence and reasoning; the verdict is code's job
    from churn.schemas import ChurnAssessment
    fields = ChurnAssessment.model_fields
    assert "risk_level" not in fields and "suggested_action" not in fields
    assert "evidence" in fields and "reason" in fields


def test_baseline_evaluate_scores_a_perfect_ranking():
    from churn.baselines import evaluate
    y = np.array([1, 1] + [0] * 8)                  # base rate 0.2
    perfect = np.array([9, 8] + [1] * 8)
    r = evaluate(y, perfect, k=2)
    assert r["auc"] == 1.0
    assert r["precision@2"] == 1.0 and r["recall@2"] == 1.0
    assert r["lift"] == 5.0                         # 1.0 / 0.2
    worst = np.array([1, 1] + [9] * 8)
    assert evaluate(y, worst, k=2)["precision@2"] == 0.0


def test_psi_stable_is_near_zero():
    x = pd.Series(np.random.RandomState(0).normal(size=500))
    assert psi(x, x) < 0.01


def test_psi_detects_a_shift():
    rng = np.random.RandomState(0)
    x = pd.Series(rng.normal(0, 1, size=500))
    y = pd.Series(rng.normal(2, 1, size=500))   # shifted mean -> should drift
    assert psi(x, y) > 0.2


def test_model_predicts_probabilities():
    import joblib
    bundle = joblib.load(MODEL_PATH)
    model, cols = bundle["model"], bundle["features"]
    df, _ = build_features()
    proba = model.predict_proba(df[cols])[:, 1]
    assert ((proba >= 0) & (proba <= 1)).all()


def test_memory_roundtrip(tmp_path, monkeypatch):
    import churn.memory as memory
    # point the store at a temp file so we don't touch the real contacted.json
    monkeypatch.setattr(memory, "STORE_PATH", str(tmp_path / "contacted.json"))
    assert memory.recently_contacted_ids() == set()
    memory.mark_contacted([1, 2, 3])
    assert memory.recently_contacted_ids() == {1, 2, 3}

def _pred(uid, risk, evidence=None, action="coupon", prob=0.5):
    return {"user_id": uid, "full_name": f"User {uid}", "risk_level": risk,
            "churn_probability": prob, "suggested_action": action,
            "reason": "test", "evidence": evidence or {}}


def test_modules_import_without_side_effects():
    # importing must not run the pipeline, need an API key, or need output files
    import importlib
    for name in ["eval", "verifier", "critic", "report", "uplift", "baselines",
                 "mark_contacted", "archetype_eval", "train_model", "main"]:
        importlib.import_module(f"churn.{name}")


def test_tool_summaries_match_verifier_facts():
    # the numbers the agent copies into its evidence must equal what the
    # verifier independently computes - for users with and without reviews
    from churn.config import connect_readonly
    from churn.tools import get_user_reviews, get_user_tickets
    from churn.verifier import real_facts
    conn = connect_readonly()
    no_reviews = conn.execute(
        """SELECT user_id FROM users WHERE user_type='CUSTOMER'
           AND user_id NOT IN (SELECT user_id FROM reviews) LIMIT 1"""
    ).fetchone()
    user_ids = [10, 99] + ([no_reviews[0]] if no_reviews else [])
    for uid in user_ids:
        facts = real_facts(conn, uid)
        tickets = json.loads(get_user_tickets.invoke({"user_id": uid}))
        reviews = json.loads(get_user_reviews.invoke({"user_id": uid}))
        assert tickets["total_tickets"] == facts["total_tickets"] == len(tickets["tickets"])
        assert reviews["worst_review_rating"] == facts["worst_review_rating"]
    conn.close()


def test_eval_score():
    from churn.eval import score
    preds = [_pred(1, "HIGH"), _pred(2, "MEDIUM"), _pred(3, "LOW")]
    s = score(preds, truly_churned={1, 3})
    assert s["true_positives"] == {1}
    assert s["false_positives"] == {2}
    assert s["false_negatives"] == {3}
    assert s["precision"] == 0.5 and s["recall"] == 0.5


def test_verifier_accepts_true_facts_and_flags_wrong_ones():
    from churn.config import connect_readonly
    from churn.verifier import real_facts, verify
    conn = connect_readonly()
    uid = 10
    good = real_facts(conn, uid)
    bad = {**good, "total_orders": good["total_orders"] + 1}
    result = verify(conn, [_pred(uid, "HIGH", good), _pred(uid, "HIGH", bad)])
    conn.close()
    assert result["total_fields"] == 12          # 6 checked facts x 2 predictions
    assert result["matched_fields"] == 11
    assert list(result["mismatches"]) == [uid]


def test_report_sorts_and_groups():
    from datetime import datetime
    from churn.report import build_report
    preds = [_pred(1, "MEDIUM", prob=0.3, action="coupon"),
             _pred(2, "HIGH", prob=0.9, action="retention call")]
    text = build_report(preds, {2: "unresolved support tickets"}, datetime(2026, 1, 1))
    assert text.index("(#2)") < text.index("(#1)")        # highest prob first
    assert "### Retention calls (1)" in text and "### Coupons (1)" in text
    assert "unresolved support tickets" in text


def test_uplift_is_reproducible_and_bounded():
    from churn.uplift import run_uplift, winnability
    assert winnability({"support_pain": 1, "delivery_pain": 1, "pickiness": 0}) == 0.6
    assert winnability({"support_pain": 0, "delivery_pain": 0, "pickiness": 1}) == 0.0
    truth = [{"user_id": i, "churned": True, "support_pain": 0.5,
              "delivery_pain": 0.5, "pickiness": 0.5} for i in range(50)]
    assert run_uplift(truth) == run_uplift(truth)


def test_uplift_method_recovers_planted_effect():
    import random
    from churn.uplift import planted_effect, uplift_spread
    rng = random.Random(0)
    truth = [{"user_id": i, "churned": True, "support_pain": rng.random(),
              "delivery_pain": rng.random(), "pickiness": rng.random()}
             for i in range(200)]
    spread = uplift_spread(truth, n_runs=300)
    assert abs(spread["mean"] - planted_effect(truth)) < 0.03   # unbiased
    assert spread["low"] < planted_effect(truth) < spread["high"]


def test_grouped_cv_keeps_each_customer_in_one_fold():
    from churn.config import TRAIN_CUTOFFS_DAYS
    from churn.features import build_snapshots
    from churn.train_model import grouped_cv_aucs
    train, cols = build_snapshots(TRAIN_CUTOFFS_DAYS)
    aucs = grouped_cv_aucs(train[cols], train["churned"], train["user_id"])
    assert len(aucs) == 5
    assert all(0 <= a <= 1 for a in aucs)


def test_no_timestamps_after_reference_time():
    # timestamps must be UTC (like the stored reference time) and never later
    # than it - otherwise the login windows in the tools are shifted
    from churn.config import connect_readonly, reference_now
    conn = connect_readonly()
    ref = reference_now(conn)
    checks = {
        "auth_audit_log": "event_timestamp",
        "orders": "placed_at",
        "support_tickets": "created_at",
        "reviews": "created_at",
    }
    for table, col in checks.items():
        future = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} > ?", (ref,)
        ).fetchone()[0]
        assert future == 0, f"{future} rows in {table}.{col} are after the reference time"
    conn.close()


def test_simulator_is_reproducible(tmp_path, monkeypatch):
    # same seed + frozen reference time -> identical data on every run
    import sqlite3
    import churn.quick_commerce_sim as sim

    def dump(db):
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        rows = {t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tables}
        conn.close()
        return rows

    monkeypatch.setattr(sim, "NUM_CUSTOMERS", 200)   # small: this test builds twice
    for name in ["a", "b"]:
        sim.cmd_init(tmp_path / f"{name}.db", sim.DEFAULT_HISTORY_DAYS,
                     truth_path=tmp_path / f"{name}.json")
    assert dump(tmp_path / "a.db") == dump(tmp_path / "b.db")
    assert (tmp_path / "a.json").read_text() == (tmp_path / "b.json").read_text()


def test_iso_converts_ist_to_utc_and_caps_at_now(monkeypatch):
    from datetime import datetime
    import churn.quick_commerce_sim as sim
    monkeypatch.setattr(sim, "SIM_NOW", datetime(2026, 9, 15, 10, 0, 0))
    assert sim.iso(datetime(2026, 9, 15, 9, 0, 0)) == "2026-09-15 03:30:00"   # IST -> UTC
    assert sim.iso(datetime(2026, 9, 15, 22, 0, 0)) == "2026-09-15 04:30:00"  # capped at now


def test_pii_redaction():
    from churn.pii import redact
    dirty = "Contact Sameer at 9876543210 or sameer@example.com today"
    clean = redact(dirty)
    assert "9876543210" not in clean          # phone gone
    assert "sameer@example.com" not in clean   # email gone
    assert "[PHONE]" in clean and "[EMAIL]" in clean