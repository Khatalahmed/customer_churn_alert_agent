"""
critic.py

WHAT : A skeptical reviewer (a 4th agent) that re-checks each churn verdict
       and can lower it if the evidence is weak. This is multi-agent debate:
       one agent decides, another challenges. We measure precision before
       and after the critic.
WHY  : The first agent can be over-confident. A critic that catches false
       alarms (e.g., a customer who still logs in often) makes the final
       list more trustworthy.
FLOW : load predictions + answer key -> ask the critic LLM to re-judge each
       verdict from the evidence -> compare precision before vs after.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field

from utils import get_model


class CriticVerdict(BaseModel):
    """The critic's revised judgement for one customer."""
    risk_level: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="the final risk level after review"
    )
    critique: str = Field(description="one short line explaining the decision")


CRITIC_PROMPT = """You are a skeptical churn reviewer. Another analyst labelled
this customer's churn risk. Your job is to challenge it and catch false alarms.

False-alarm patterns to watch for:
- The customer still logs in often (recent logins are close to the earlier
  period) -> they may just use the app a little less, not leave. Lower the risk.
- No support tickets AND positive reviews -> probably fine. Lower the risk.
- Weak evidence that does not clearly support a HIGH label.

Keep HIGH only if the evidence clearly supports it. Otherwise lower it."""

critic = get_model().with_structured_output(CriticVerdict)

with open("churn_predictions.json") as f:
    preds = json.load(f)
with open("churn_truth.json") as f:
    truth = json.load(f)
churned = {r["user_id"] for r in truth if r["churned"]}

reviewed = []
print("Critic reviewing each verdict...\n")
for p in preds:
    msg = (f"{CRITIC_PROMPT}\n\n"
           f"Customer: {p['full_name']} (#{p['user_id']})\n"
           f"Current risk: {p['risk_level']}\n"
           f"ML churn probability: {p['churn_probability']}\n"
           f"Evidence: {json.dumps(p['evidence'])}\n"
           f"Analyst reason: {p['reason']}")
    v = critic.invoke(msg)
    if v.risk_level != p["risk_level"]:
        print(f"  CHANGED user {p['user_id']:>3} {p['full_name']:<18} "
              f"{p['risk_level']} -> {v.risk_level}  ({v.critique})")
    reviewed.append({**p, "risk_level": v.risk_level, "critique": v.critique})


def precision(pred_list):
    flagged = {p["user_id"] for p in pred_list if p["risk_level"] in ("HIGH", "MEDIUM")}
    if not flagged:
        return 0.0, 0, 0
    tp = len(flagged & churned)
    return tp / len(flagged), tp, len(flagged)


p_before, tp_b, n_b = precision(preds)
p_after, tp_a, n_a = precision(reviewed)

print("\n" + "=" * 55)
print("CRITIC IMPACT (precision = flagged that truly churned)")
print("=" * 55)
print(f"Before critic: precision {p_before:.2f}  ({tp_b}/{n_b} flagged)")
print(f"After  critic: precision {p_after:.2f}  ({tp_a}/{n_a} flagged)")

with open("churn_predictions_reviewed.json", "w") as f:
    json.dump(reviewed, f, indent=2)
print("\nSaved reviewed verdicts to churn_predictions_reviewed.json")