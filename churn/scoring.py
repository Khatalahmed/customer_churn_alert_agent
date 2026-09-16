"""
scoring.py

WHAT : Loads the trained XGBoost model and scores every customer who is active
       at the analysis time for churn in the next 14 days, then combines risk
       with customer value to build a priority list. Exposes it as a tool the
       agent calls to pick who to investigate.
WHY  : The model is cheap and scores every active customer. The agent is slow
       and costly, so it should only investigate the top-priority ones.
       Priority = churn risk x customer value, so we focus on the valuable
       customers we are about to lose.
FLOW : point-in-time features at the analysis time -> model predicts churn
       probability -> priority = probability x average order value -> drop
       recently contacted -> rank -> return the top N with their key numbers.
"""
import json

import joblib
import pandas as pd
from langchain.tools import tool

from .config import MODEL_PATH, analysis_time, connect_readonly
from .features import build_features
from .memory import recently_contacted_ids


def _login_trend(user_id: int, as_of: str):
    """Return (logins 30-60 days before as_of, logins in the 30 days before as_of)."""
    conn = connect_readonly()
    cur = conn.cursor()
    prev = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp BETWEEN datetime(?,'-60 days')
                                     AND datetime(?,'-30 days')""",
        (user_id, as_of, as_of),
    ).fetchone()[0]
    recent = cur.execute(
        """SELECT COUNT(*) FROM auth_audit_log
           WHERE user_id=? AND event_type='LOGIN'
             AND event_timestamp >= datetime(?,'-30 days')
             AND event_timestamp < ?""",
        (user_id, as_of, as_of),
    ).fetchone()[0]
    conn.close()
    return prev, recent


def score_customers(as_of=None) -> pd.DataFrame:
    """Score customers active at `as_of` and rank them by churn priority (highest first)."""
    bundle = joblib.load(MODEL_PATH)
    model, cols = bundle["model"], bundle["features"]

    conn = connect_readonly()
    as_of = as_of or analysis_time(conn)
    names = pd.read_sql(
        "SELECT user_id, full_name FROM users WHERE user_type='CUSTOMER'", conn
    )
    conn.close()

    df, _ = build_features(as_of=as_of)
    df["churn_probability"] = model.predict_proba(df[cols])[:, 1]
    # priority = "expected value at risk" = how likely to leave x how valuable
    df["priority_score"] = df["churn_probability"] * df["avg_order_value"]
    df = df.merge(names, on="user_id", how="left")

    return df.sort_values("priority_score", ascending=False)


@tool
def get_churn_candidates(top_n: int = 15) -> str:
    """Get the top churn-risk customers to investigate, ranked by priority.

    The ML model predicts each active customer's chance of churning in the
    next 14 days. Priority combines that probability with the customer's
    value (average order value), so high-value customers at risk come first.
    Call this FIRST to decide which customers to investigate. For each
    customer it also returns the login trend and total orders, all as of the
    analysis time.

    Args:
        top_n: how many top-priority customers to return (default 15).
    """
    conn = connect_readonly()
    as_of = analysis_time(conn)
    conn.close()

    df = score_customers(as_of)
    # skip customers we already contacted in the last 30 days (no nagging)
    skip = recently_contacted_ids(days=30)
    df = df[~df["user_id"].isin(skip)]
    df = df.head(top_n)

    result = []
    for _, r in df.iterrows():
        uid = int(r["user_id"])
        prev, recent = _login_trend(uid, as_of)
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
