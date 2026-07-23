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

from features import build_features, FEATURE_COLS
from tools import get_inactive_users
from drift import psi


def test_features_shape():
    df, cols = build_features()
    assert cols == FEATURE_COLS
    assert len(df) == 300
    assert "churned" in df.columns
    assert df["churned"].isin([0, 1]).all()


def test_tool_returns_valid_json():
    out = get_inactive_users.invoke({"days": 14, "top_n": 5})
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) <= 5


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
    bundle = joblib.load("churn_model.pkl")
    model, cols = bundle["model"], bundle["features"]
    df, _ = build_features()
    proba = model.predict_proba(df[cols])[:, 1]
    assert ((proba >= 0) & (proba <= 1)).all()


def test_memory_roundtrip(tmp_path, monkeypatch):
    import memory
    # point the store at a temp file so we don't touch the real contacted.json
    monkeypatch.setattr(memory, "STORE_PATH", str(tmp_path / "contacted.json"))
    assert memory.recently_contacted_ids() == set()
    memory.mark_contacted([1, 2, 3])
    assert memory.recently_contacted_ids() == {1, 2, 3}