"""
features.py

WHAT : Builds a point-in-time snapshot: for a cutoff time T, one row per
       customer who is active at T, with features computed ONLY from data
       before T. add_labels() then marks who stops being active in the next
       HORIZON_DAYS - a genuinely future outcome.
WHY  : The first version labelled customers who had ALREADY churned and used
       their whole history, so it detected past churn rather than predicting
       it. With the label strictly after T, recency and login-trend features
       are no longer leakage: they are exactly the early-warning signals a
       real retention team would see.
FLOW : active customers at T -> order / ticket / review / login aggregates
       before T -> rates and recency features -> (training / eval only)
       add_labels() from the answer key. build_snapshots() stacks several
       cutoffs into one training table.
LOGIC: a ticket counts as unresolved at T if it was not resolved before T,
       whatever its final status. Averages stay NaN when there is no data
       (XGBoost handles NaN); counts become 0.
"""
import json
from datetime import datetime, timedelta

import pandas as pd

from .config import (ACTIVE_WINDOW_DAYS, DB_PATH, HORIZON_DAYS, TRUTH_PATH,
                     analysis_time, connect_readonly, cutoff_time)

FEATURE_COLS = [
    # experience quality - the cause of churn
    "avg_review_rating",
    "pct_low_reviews",
    "cancellation_rate",
    "unresolved_ticket_rate",
    "tickets_per_order",
    "avg_order_value",
    # engagement before the cutoff - legitimate now that the label is in the future
    "logins_last_14d",
    "logins_prev_14_28d",
    "days_since_last_login",
    "orders_last_28d",
    "days_since_last_order",
    # how much evidence each rate above is based on: 1 cancellation out of 4 orders
    # is a guess, 10 out of 40 is a fact - the model cannot tell without these
    "total_orders",
    "total_tickets",
    "total_reviews",
]


def build_features(as_of=None, db_path=None):
    """Return (dataframe, feature_columns) for customers active at `as_of`.

    `as_of` is a UTC 'YYYY-MM-DD HH:MM:SS' string; default: analysis_time().
    Every query only reads rows from before `as_of`.
    """
    conn = connect_readonly(db_path or DB_PATH)
    as_of = as_of or analysis_time(conn)
    p = {"t": as_of, "window": f"-{ACTIVE_WINDOW_DAYS} days"}

    customers = pd.read_sql(
        """SELECT u.user_id FROM users u
           WHERE u.user_type = 'CUSTOMER' AND EXISTS (
               SELECT 1 FROM auth_audit_log a
               WHERE a.user_id = u.user_id AND a.event_type = 'LOGIN'
                 AND a.event_timestamp >= datetime(:t, :window)
                 AND a.event_timestamp < :t)""",
        conn, params=p,
    )
    orders = pd.read_sql(
        """SELECT user_id,
                  COUNT(*)                                   AS total_orders,
                  AVG(total_amount)                          AS avg_order_value,
                  SUM(order_status = 'CANCELLED')            AS cancelled,
                  SUM(placed_at >= datetime(:t, '-28 days')) AS orders_last_28d,
                  julianday(:t) - julianday(MAX(placed_at))  AS days_since_last_order
           FROM orders WHERE placed_at < :t GROUP BY user_id""",
        conn, params=p,
    )
    tickets = pd.read_sql(
        """SELECT user_id,
                  COUNT(*)                                     AS total_tickets,
                  SUM(resolved_at IS NULL OR resolved_at >= :t) AS unresolved
           FROM support_tickets WHERE created_at < :t GROUP BY user_id""",
        conn, params=p,
    )
    reviews = pd.read_sql(
        """SELECT user_id,
                  AVG(rating)      AS avg_review_rating,
                  COUNT(*)         AS total_reviews,
                  SUM(rating <= 2) AS low_reviews
           FROM reviews WHERE created_at < :t GROUP BY user_id""",
        conn, params=p,
    )
    logins = pd.read_sql(
        """SELECT user_id,
                  SUM(event_timestamp >= datetime(:t, '-14 days'))        AS logins_last_14d,
                  SUM(event_timestamp <  datetime(:t, '-14 days')
                      AND event_timestamp >= datetime(:t, '-28 days'))    AS logins_prev_14_28d,
                  julianday(:t) - julianday(MAX(event_timestamp))         AS days_since_last_login
           FROM auth_audit_log
           WHERE event_type = 'LOGIN' AND event_timestamp < :t GROUP BY user_id""",
        conn, params=p,
    )
    conn.close()

    df = customers
    for part in (orders, tickets, reviews, logins):
        df = df.merge(part, on="user_id", how="left")

    # count columns: missing means "none happened" -> 0
    for c in ["total_orders", "cancelled", "orders_last_28d", "total_tickets",
              "unresolved", "total_reviews", "low_reviews",
              "logins_last_14d", "logins_prev_14_28d"]:
        df[c] = df[c].fillna(0)
    # averages and "days since" stay NaN when there is no data

    # rate features: 0 denominator -> rate 0 (no bad events observed)
    df["cancellation_rate"]      = df["cancelled"]     / df["total_orders"].replace(0, 1)
    df["unresolved_ticket_rate"] = df["unresolved"]    / df["total_tickets"].replace(0, 1)
    df["tickets_per_order"]      = df["total_tickets"] / df["total_orders"].replace(0, 1)
    df["pct_low_reviews"]        = df["low_reviews"]   / df["total_reviews"].replace(0, 1)

    df["as_of"] = as_of
    return df.sort_values("user_id").reset_index(drop=True), FEATURE_COLS


def add_labels(df: pd.DataFrame, truth_path=None) -> pd.DataFrame:
    """Label each row: 1 if the customer stops being active in (as_of, as_of + HORIZON].

    Rows for customers who had ALREADY churned by as_of are dropped - they are
    not "at risk", they are gone. Training / eval only: scoring must never
    need the answer key.
    """
    with open(truth_path or TRUTH_PATH) as f:
        truth = {r["user_id"]: r for r in json.load(f)}

    def label(row) -> int:
        r = truth.get(row.user_id)
        if not r or not r["churned"]:
            return 0
        until = datetime.fromisoformat(r["active_until"])
        cutoff = datetime.fromisoformat(row.as_of)
        if until <= cutoff:
            return -1                                  # already churned: drop
        return int(until <= cutoff + timedelta(days=HORIZON_DAYS))

    labels = pd.Series([label(r) for r in df.itertuples()], index=df.index)
    out = df[labels >= 0].copy()
    out["churned"] = labels[labels >= 0].astype(int)   # "churns within the horizon"
    return out.reset_index(drop=True)


def build_snapshots(days_before_reference, db_path=None):
    """Labelled snapshots at several cutoffs, stacked into one table."""
    conn = connect_readonly(db_path or DB_PATH)
    cutoffs = [cutoff_time(conn, d) for d in days_before_reference]
    conn.close()
    frames = [add_labels(build_features(as_of=c, db_path=db_path)[0]) for c in cutoffs]
    return pd.concat(frames, ignore_index=True), FEATURE_COLS


if __name__ == "__main__":
    from .config import TEST_CUTOFF_DAYS, TRAIN_CUTOFFS_DAYS
    snaps, cols = build_snapshots(list(TRAIN_CUTOFFS_DAYS) + [TEST_CUTOFF_DAYS])
    print("Feature columns:", cols)
    print(snaps.groupby("as_of")["churned"].agg(active="size", churn_in_horizon="sum"))
    print("\nMean feature value by label (0 = stays, 1 = churns within the horizon):")
    print(snaps.groupby("churned")[cols].mean().T.round(3))
