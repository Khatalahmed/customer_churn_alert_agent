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
