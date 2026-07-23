"""
explain.py

WHAT : Explains the XGBoost model with SHAP. As a script it prints the global
       picture and a few per-customer examples. It also gives a function
       top_factor_per_user() that report.py uses to show WHY each customer
       was flagged.
WHY  : A churn probability alone is a black box. SHAP shows WHY. This proves
       the model uses sensible signals and gives the retention team a plain
       reason, e.g. "flagged mainly for unresolved tickets".
FLOW : load model + features -> build a SHAP explainer -> for each customer
       find the feature that pushed churn UP the most -> turn it into a
       friendly phrase.
LOGIC: a positive SHAP value pushes the churn score UP (more likely to
       leave); a negative value pushes it DOWN (more likely to stay).
"""
import joblib
import numpy as np
import shap

from .features import build_features

# plain-English name for each feature, for the report
FRIENDLY = {
    "avg_review_rating": "low review ratings",
    "pct_low_reviews": "many low reviews",
    "cancellation_rate": "high cancellation rate",
    "unresolved_ticket_rate": "unresolved support tickets",
    "tickets_per_order": "frequent complaints",
    "avg_order_value": "order value pattern",
}


def _load_and_explain():
    """Load the model and compute SHAP values for every customer."""
    bundle = joblib.load("churn_model.pkl")
    model, cols = bundle["model"], bundle["features"]
    df, _ = build_features()
    X = df[cols]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    return model, df, X, cols, shap_values


def top_factor_per_user() -> dict:
    """Return {user_id: reason} - the feature that pushes each customer's
    churn score UP the most, as a plain-English phrase."""
    model, df, X, cols, shap_values = _load_and_explain()
    result = {}
    for i, uid in enumerate(df["user_id"]):
        pushes = list(zip(cols, shap_values[i]))
        name, push = max(pushes, key=lambda x: x[1])   # biggest push toward churn
        result[int(uid)] = FRIENDLY.get(name, name) if push > 0 else "no strong signal"
    return result


if __name__ == "__main__":
    model, df, X, cols, shap_values = _load_and_explain()

    mean_abs = np.abs(shap_values).mean(axis=0)
    print("=" * 60)
    print("GLOBAL FEATURE IMPORTANCE (mean |SHAP|, higher = more used)")
    print("=" * 60)
    for name, val in sorted(zip(cols, mean_abs), key=lambda x: -x[1]):
        print(f"  {name:<26} {val:.3f}")

    df["churn_probability"] = model.predict_proba(X)[:, 1]
    top = df.sort_values("churn_probability", ascending=False).head(3)

    print("\n" + "=" * 60)
    print("WHY THESE CUSTOMERS ARE FLAGGED (top push factors)")
    print("=" * 60)
    for idx in top.index:
        uid = int(df.loc[idx, "user_id"])
        prob = df.loc[idx, "churn_probability"]
        pushes = sorted(zip(cols, shap_values[idx]), key=lambda x: -abs(x[1]))
        print(f"\nuser {uid}  (churn probability {prob:.0%})")
        for name, push in pushes[:4]:
            direction = "UP  " if push > 0 else "DOWN"
            print(f"    {name:<26} pushes churn {direction} ({push:+.3f})")