"""
scoring.py

WHAT : Loads the trained XGBoost model and scores every customer for churn
       risk, then combines risk with customer value to build a priority list.
       Exposes it as a tool the agent calls to pick who to investigate.
WHY  : The model is cheap and scores ALL 300 customers. The agent is slow
       and costly, so it should only investigate the top-priority ones.
       Priority = churn risk x customer value, so we focus on the valuable
       customers we are about to lose (this fixes missing high-value churn).
FLOW : build features -> model predicts churn probability -> priority =
       probability x average order value -> drop recently contacted -> rank
       -> return the top N with their key numbers.
"""
import json
import sqlite3

import joblib
import pandas as pd
from langchain.tools import tool

from features import build_features
from memory import recently_contacted_ids

DB_PATH = "qcommerce.db"


def _login_trend(user_id: int):
    """Return (logins 30-60 days ago, logins in the last 30 days) for one user."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()
    prev = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp BETWEEN datetime('now','-60 days')
                                     AND datetime('now','-30 days')""",
        (user_id,),
    ).fetchone()[0]
    recent = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp >= datetime('now','-30 days')""",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return prev, recent


def score_customers() -> pd.DataFrame:
    """Score all customers and return them ranked by churn priority (highest first)."""
    bundle = joblib.load("churn_model.pkl")
    model, cols = bundle["model"], bundle["features"]

    df, _ = build_features()
    df["churn_probability"] = model.predict_proba(df[cols])[:, 1]
    # priority = "expected value at risk" = how likely to leave x how valuable
    df["priority_score"] = df["churn_probability"] * df["avg_order_value"]

    # attach names for readability
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    names = pd.read_sql(
        "SELECT user_id, full_name FROM users WHERE user_type='CUSTOMER'", conn
    )
    conn.close()
    df = df.merge(names, on="user_id", how="left")

    return df.sort_values("priority_score", ascending=False)


@tool
def get_churn_candidates(top_n: int = 15) -> str:
    """Get the top churn-risk customers to investigate, ranked by priority.

    Priority combines the ML model's churn probability with the customer's
    value (average order value), so high-value customers at risk come first.
    Call this FIRST to decide which customers to investigate. For each
    customer it also returns the login trend and total orders.

    Args:
        top_n: how many top-priority customers to return (default 15).
    """
    df = score_customers()
    # NEW: skip customers we already contacted in the last 30 days (no nagging)
    skip = recently_contacted_ids(days=30)
    df = df[~df["user_id"].isin(skip)]
    df = df.head(top_n)

    result = []
    for _, r in df.iterrows():
        uid = int(r["user_id"])
        prev, recent = _login_trend(uid)
        result.append({
            "user_id": uid,
            "full_name": r["full_name"],
            "churn_probability": round(float(r["churn_probability"]), 3),
            "avg_order_value": round(float(r["avg_order_value"]), 2),
            "priority_score": round(float(r["priority_score"]), 2),
            "logins_prev_30_60d": prev,
            "logins_recent_30d": recent,
            "total_orders": int(r["total_orders"]),
        })
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # quick standalone check: print the top 15 priority customers
    print(get_churn_candidates.invoke({"top_n": 15}))