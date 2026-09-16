"""
scoring.py

WHAT : Loads the trained XGBoost model, scores every customer active at the
       analysis time for churn in the next 14 days, and returns the riskiest
       few for the agent to investigate.
WHY  : The model is cheap and scores every active customer. The agent is slow
       and costly, so it should only investigate the top slice.
LOGIC: WHO is chosen by churn risk alone. We used to rank by risk x order
       value; measured over 10 snapshots that cost ~40% of the shortlist's
       precision (0.073 vs 0.120), because order value carries no churn signal
       here - value only decides the ORDER of the chosen few, so the team
       calls the biggest loss first.
FLOW : point-in-time features -> churn probability -> drop recently contacted
       -> take the top N by risk -> order by value at risk -> return with
       their key numbers.
"""
import json

import joblib
import pandas as pd
from langchain.tools import tool

from .config import MODEL_PATH, analysis_time, connect_readonly
from .features import build_features
from .logins import login_counts
from .memory import recently_contacted_ids


def _login_trend(user_id: int, as_of: str):
    """Return (logins in the previous window, logins in the recent window).

    The windows come from config so this matches the model's features exactly.
    Both are half-open, [start, end): the old version used SQL BETWEEN for the
    earlier window, which is inclusive at both ends, so a login landing exactly
    on the boundary was counted in BOTH windows.
    """
    conn = connect_readonly()
    prev, recent = login_counts(conn, user_id, as_of)
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
    # value at risk = how likely to leave x how valuable. NOT used to choose who to
    # investigate: measured over 10 snapshots, ranking by probability x value costs
    # ~40% of shortlist precision (0.073 vs 0.120), because order value carries no
    # churn signal here. It orders the shortlist once risk has chosen it.
    df["priority_score"] = df["churn_probability"] * df["avg_order_value"]
    df = df.merge(names, on="user_id", how="left")

    return df.sort_values("churn_probability", ascending=False)


@tool
def get_churn_candidates(top_n: int = 15) -> str:
    """Get the top churn-risk customers to investigate, ranked by priority.

    The ML model predicts each active customer's chance of churning in the
    next 14 days. The riskiest customers are shortlisted, then ordered by
    value at risk (churn probability x average order value) so the most
    valuable at-risk customer comes first. Call this FIRST to decide which
    customers to investigate. For each customer it also returns the login
    trend and total orders, all as of the analysis time.

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
    # WHO to investigate: highest churn risk. Then order that shortlist by value at
    # risk, so the team calls the most valuable at-risk customer first.
    df = df.nlargest(top_n, "churn_probability").sort_values("priority_score", ascending=False)

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
            "logins_prev_14_28d": prev,
            "logins_last_14d": recent,
            "total_orders": int(r["total_orders"]),
        })
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    # quick standalone check: print the top 15 priority customers
    print(get_churn_candidates.invoke({"top_n": 15}))
