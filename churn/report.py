"""
report.py

WHAT : Turns the agent's predictions into a human-readable retention report
       (markdown). Now it also shows the top ML factor (from SHAP) for each
       customer, so the team can see WHY the model flagged them.
WHY  : The JSON predictions are for machines. A manager needs a clear report:
       who is at risk, how likely, why (SHAP factor + evidence), and what to do.
FLOW : load predictions -> get the top SHAP factor per customer -> sort by
       churn probability -> write a markdown file with a summary, a priority
       table, and action groups.
"""
import json
from datetime import datetime

from .config import PREDICTIONS_PATH, REPORT_PATH


def build_report(preds: list[dict], factors: dict, generated: datetime) -> str:
    """Return the retention report as markdown text."""
    preds = sorted(preds, key=lambda p: p.get("churn_probability", 0), reverse=True)

    n = len(preds)
    high = [p for p in preds if p["risk_level"] == "HIGH"]
    medium = [p for p in preds if p["risk_level"] == "MEDIUM"]
    calls = [p for p in preds if "call" in p["suggested_action"].lower()]

    lines = []
    lines.append("# Customer Retention Report")
    lines.append("")
    lines.append(f"_Generated {generated:%Y-%m-%d %H:%M}_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Customers investigated: **{n}**")
    lines.append(f"- HIGH risk: **{len(high)}**  |  MEDIUM risk: **{len(medium)}**")
    lines.append(f"- Recommended retention calls: **{len(calls)}**")
    lines.append("")
    lines.append("## Priority list (highest churn probability first)")
    lines.append("")
    lines.append("| # | Customer | Risk | Churn prob | Top ML factor | Action | Why |")
    lines.append("|---|----------|------|-----------|---------------|--------|-----|")
    for i, p in enumerate(preds, 1):
        factor = factors.get(p["user_id"], "-")
        lines.append(
            f"| {i} | {p['full_name']} (#{p['user_id']}) | {p['risk_level']} | "
            f"{p['churn_probability']:.0%} | {factor} | {p['suggested_action']} | {p['reason']} |"
        )
    lines.append("")

    lines.append("## Action groups")
    lines.append("")
    for action_label, keyword in [("Retention calls", "call"), ("Coupons", "coupon")]:
        group = [p for p in preds if keyword in p["suggested_action"].lower()]
        if group:
            lines.append(f"### {action_label} ({len(group)})")
            for p in group:
                factor = factors.get(p["user_id"], "-")
                lines.append(f"- **{p['full_name']}** (#{p['user_id']}) "
                             f"- {p['churn_probability']:.0%} risk - {factor}")
            lines.append("")

    return "\n".join(lines)


def main():
    # SHAP is slow to import; only needed when actually writing a report
    from .explain import top_factor_per_user

    with open(PREDICTIONS_PATH) as f:
        preds = json.load(f)

    # SHAP top factor per customer (why the model flagged them)
    factors = top_factor_per_user()
    text = build_report(preds, factors, datetime.now())

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    high = sum(1 for p in preds if p["risk_level"] == "HIGH")
    medium = sum(1 for p in preds if p["risk_level"] == "MEDIUM")
    calls = sum(1 for p in preds if "call" in p["suggested_action"].lower())
    print(f"Wrote retention_report.md with {len(preds)} customers "
          f"({high} HIGH, {medium} MEDIUM, {calls} calls).")


if __name__ == "__main__":
    main()
