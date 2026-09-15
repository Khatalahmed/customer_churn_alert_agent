"""
features.py

WHAT : Turns the database into a table of features, one row per customer,
       plus the churn label. This is the input for the XGBoost model.
WHY  : We use QUALITY / RATE features, not raw counts (counts leak the label).
       For the two "average" features (order value, review rating) we use NaN
       when there is no data, instead of 0. A 0 would falsely mean "worth
       nothing" or "rated zero". XGBoost handles NaN natively.
FLOW : query per-customer aggregates from each table -> merge them -> fill
       count columns with 0 but leave the averages as NaN -> build rate
       features. add_labels() attaches the churn label from the answer key
       separately, so scoring works without it.
LOGIC: rates measure the QUALITY of a customer's experience (the real cause
       of churn). We dropped tenure_days: it had no real group difference but
       the model was overfitting to noise in it (SHAP revealed this).
"""
import json

import pandas as pd

from .config import DB_PATH, TRUTH_PATH, connect_readonly

# Final features the model trains on. tenure_days removed (overfit noise).

FEATURE_COLS = [
    "avg_review_rating",
    "pct_low_reviews",
    "cancellation_rate",
    "unresolved_ticket_rate",
    "tickets_per_order",
    "avg_order_value",
]


def build_features(db_path=None):
    """Return (dataframe, feature_columns). One row per customer, no label."""
    conn = connect_readonly(db_path or DB_PATH)

    customers = pd.read_sql(
        "SELECT user_id FROM users WHERE user_type='CUSTOMER'", conn
    )
    orders = pd.read_sql(
        """SELECT user_id,
                  COUNT(*)                                              AS total_orders,
                  AVG(total_amount)                                     AS avg_order_value,
                  SUM(CASE WHEN order_status='CANCELLED' THEN 1 ELSE 0 END) AS cancelled
           FROM orders GROUP BY user_id""",
        conn,
    )
    tickets = pd.read_sql(
        """SELECT user_id,
                  COUNT(*) AS total_tickets,
                  SUM(CASE WHEN status IN ('OPEN','IN_PROGRESS','WAITING_ON_CUSTOMER')
                           THEN 1 ELSE 0 END) AS unresolved
           FROM support_tickets GROUP BY user_id""",
        conn,
    )
    reviews = pd.read_sql(
        """SELECT user_id,
                  AVG(rating) AS avg_review_rating,
                  COUNT(*)    AS total_reviews,
                  SUM(CASE WHEN rating<=2 THEN 1 ELSE 0 END) AS low_reviews
           FROM reviews GROUP BY user_id""",
        conn,
    )
    conn.close()

    df = (customers
          .merge(orders, on="user_id", how="left")
          .merge(tickets, on="user_id", how="left")
          .merge(reviews, on="user_id", how="left"))

    # count columns: missing means "none happened" -> fill with 0
    for c in ["total_orders", "cancelled", "total_tickets",
              "unresolved", "total_reviews", "low_reviews"]:
        df[c] = df[c].fillna(0)

    # average columns: missing means "no data" -> leave as NaN (XGBoost handles it)
    # (avg_order_value and avg_review_rating stay NaN when there are no orders/reviews)

    # rate features: 0 denominator -> rate 0 (no bad events observed)
    df["cancellation_rate"]      = df["cancelled"]    / df["total_orders"].replace(0, 1)
    df["unresolved_ticket_rate"] = df["unresolved"]   / df["total_tickets"].replace(0, 1)
    df["tickets_per_order"]      = df["total_tickets"] / df["total_orders"].replace(0, 1)
    df["pct_low_reviews"]        = df["low_reviews"]  / df["total_reviews"].replace(0, 1)

    return df, FEATURE_COLS


def add_labels(df: pd.DataFrame, truth_path=None) -> pd.DataFrame:
    """Attach the churn label from the answer key. Training / eval only -
    scoring must never need this file (in production there is no answer key)."""
    with open(truth_path or TRUTH_PATH) as f:
        truth = json.load(f)
    churn_map = {r["user_id"]: int(r["churned"]) for r in truth}
    df["churned"] = df["user_id"].map(churn_map).fillna(0).astype(int)
    return df


if __name__ == "__main__":
    df, cols = build_features()
    df = add_labels(df)
    print("Feature columns:", cols)
    print(f"Rows: {len(df)}   churned: {df['churned'].sum()}")
    print("\nMean feature value by group (0 = active, 1 = churned):")
    print(df.groupby("churned")[cols].mean().T.round(3))