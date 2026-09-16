"""
pipeline.py

WHAT : The scheduled job. Scores every active customer, writes the worklist,
       checks the model's inputs for drift, and exits non-zero when something
       needs a human.
WHY   : "Run these six commands in order" is not an operation. A scheduled
       job needs one entry point, a machine-readable output, and a failure
       signal a scheduler can see - otherwise a broken model just quietly
       produces an empty worklist every morning.
FLOW  : score -> shortlist with priced interventions -> write worklist.json
        -> drift check against the training snapshots -> print a summary and
        exit 0 (fine) or 2 (alert).
NOTE  : no LLM here. This is the cheap, deterministic path that can run every
        day; the agent's investigation is a separate, slower step.
"""
import json
import sys

from .actions import CURRENCY, customer_money, open_complaint_categories, plan
from .config import (TRAIN_CUTOFFS_DAYS, WORKLIST_PATH, analysis_time,
                     connect_readonly, reference_now)
from .drift import psi
from .features import build_features, build_snapshots
from .memory import recently_contacted_ids
from .rubric import assess
from .scoring import score_customers
from .verifier import real_facts

DRIFT_THRESHOLD = 0.2


def build_worklist(top_n: int = 15) -> dict:
    """Score everyone, then price an intervention for the riskiest few."""
    conn = connect_readonly()
    as_of = analysis_time(conn)
    df = score_customers(as_of)
    skip = recently_contacted_ids(days=30)
    shortlist = df[~df["user_id"].isin(skip)].nlargest(top_n, "churn_probability")

    customers = []
    for _, row in shortlist.iterrows():
        uid = int(row["user_id"])
        verdict = assess(real_facts(conn, uid, as_of))
        money = customer_money(conn, uid, as_of)
        action = plan(verdict, float(row["churn_probability"]), money["avg_order_value"],
                      money["orders_per_month"], open_complaint_categories(conn, uid, as_of))
        customers.append({"user_id": uid, "full_name": row["full_name"],
                          "churn_probability": round(float(row["churn_probability"]), 4),
                          **verdict, **money, **action})
    conn.close()

    customers.sort(key=lambda c: c["expected_value"], reverse=True)
    worth = [c for c in customers if c["worth_doing"]]
    return {
        "analysis_time": as_of,
        "scored": len(df),
        "skipped_recently_contacted": len(skip),
        "customers": customers,
        "worth_doing": len(worth),
        "expected_value_total": round(sum(c["expected_value"] for c in worth), 2),
    }


def drift_alerts(threshold: float = DRIFT_THRESHOLD) -> list[str]:
    """Compare today's feature distributions with the model's training data.

    The baseline is the MOST RECENT training snapshot, not all of them pooled:
    customers accumulate orders as time passes, so comparing today against
    months-old snapshots flags that growth as drift every single day.
    """
    train, cols = build_snapshots([min(TRAIN_CUTOFFS_DAYS)])
    today, _ = build_features()
    alerts = []
    for col in cols:
        value = psi(train[col], today[col])
        if value > threshold:
            alerts.append(f"{col} drifted (PSI {value:.2f} > {threshold}) - retrain")
    return alerts


def main():
    conn = connect_readonly()
    reference = reference_now(conn)
    conn.close()

    work = build_worklist()
    with open(WORKLIST_PATH, "w") as f:
        json.dump(work, f, indent=2)

    alerts = drift_alerts()
    if not work["customers"]:
        alerts.append("worklist is empty - is the model scoring anyone?")

    print("=" * 70)
    print(f"DAILY CHURN SCAN  (data reference {reference}, analysis time {work['analysis_time']})")
    print("=" * 70)
    print(f"Scored {work['scored']} active customers, "
          f"skipped {work['skipped_recently_contacted']} contacted in the last 30 days")
    print(f"Worklist: {len(work['customers'])} customers, {work['worth_doing']} worth acting on, "
          f"{CURRENCY}{work['expected_value_total']:,.0f} expected value")
    for c in work["customers"][:5]:
        print(f"  {c['full_name'][:18]:<20}{c['risk_level']:<8}"
              f"{c['churn_probability']:>5.0%}  {c['intervention_label']:<34}"
              f"{CURRENCY}{c['expected_value']:>7,.0f}")
    if len(work["customers"]) > 5:
        print(f"  ... and {len(work['customers']) - 5} more in {WORKLIST_PATH}")

    print("-" * 70)
    if alerts:
        print(f"ALERTS ({len(alerts)}):")
        for a in alerts:
            print(f"  ! {a}")
    else:
        print("No alerts: inputs look like the training data.")
    print("=" * 70)
    sys.exit(2 if alerts else 0)


if __name__ == "__main__":
    main()
