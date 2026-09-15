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

from churn.features import add_labels, build_features, FEATURE_COLS
from churn.config import MODEL_PATH
from churn.tools import get_inactive_users
from churn.drift import psi


def test_features_shape():
    df, cols = build_features()
    assert cols == FEATURE_COLS
    assert len(df) == 300
    assert "churned" not in df.columns          # scoring must not need the answer key
    df = add_labels(df)
    assert df["churned"].isin([0, 1]).all()


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
    assert len(df) == 300
    assert df["churn_probability"].between(0, 1).all()


def test_tool_returns_valid_json():
    out = get_inactive_users.invoke({"days": 14, "top_n": 5})
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) <= 5


def test_churn_candidates_tool_returns_ranked_json(tmp_path, monkeypatch):
    import churn.memory as memory
    from churn.scoring import get_churn_candidates
    # empty contact log, so no customer is skipped
    monkeypatch.setattr(memory, "STORE_PATH", tmp_path / "contacted.json")
    data = json.loads(get_churn_candidates.invoke({"top_n": 5}))
    assert len(data) == 5
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
    for name in ["eval", "verifier", "critic", "report", "uplift",
                 "mark_contacted", "archetype_eval", "train_model", "main"]:
        importlib.import_module(f"churn.{name}")


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
    assert result["total_fields"] == 10
    assert result["matched_fields"] == 9
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


def test_oof_probabilities_cover_every_customer():
    from churn.archetype_eval import oof_probabilities
    df, cols = build_features()
    df = add_labels(df)
    oof = oof_probabilities(df[cols], df["churned"])
    assert len(oof) == len(df)
    assert ((oof > 0) & (oof < 1)).all()


def test_pii_redaction():
    from churn.pii import redact
    dirty = "Contact Sameer at 9876543210 or sameer@example.com today"
    clean = redact(dirty)
    assert "9876543210" not in clean          # phone gone
    assert "sameer@example.com" not in clean   # email gone
    assert "[PHONE]" in clean and "[EMAIL]" in clean
