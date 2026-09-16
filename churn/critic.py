"""
critic.py

STATUS: NOT PART OF THE PIPELINE. This is a kept experiment, not a component.
        Nothing in the scan, the API, the agent run or the evals imports it,
        and a test enforces that. It is here because deleting a measured
        negative result loses the measurement.

WHAT : A skeptical fourth agent that re-judged each verdict from the evidence
       and could lower it, to see whether multi-agent debate catches false
       alarms. Run it with `python -m churn.critic` if you want to reproduce
       the finding.
WHY IT IS NOT USED : it was measured, and it made the shortlist worse. It
       lowered real churners out of the flagged set - on a list where the
       flagged set is already tiny, removing a true positive costs more
       precision than removing several false ones gains. The skeptical prompt
       below is doing what it was asked to do: "keep HIGH only if the evidence
       clearly supports it" is exactly the wrong instruction when the base
       rate is 1.4% and the evidence is always thin.
ALSO : it predates the division of labour. Risk levels are now assigned by
       churn/rubric.py in plain code, from facts re-queried from the database,
       so a critic that edits risk_level would be overwriting a deterministic
       verdict with an LLM opinion - the change this project made deliberately,
       run backwards.
FLOW : load predictions + answer key -> ask the critic LLM to re-judge each
       verdict from the evidence -> compare precision before vs after.
"""
import json
from typing import Literal

from pydantic import BaseModel, Field

from .config import PREDICTIONS_PATH, REVIEWED_PATH


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


def critic_message(p: dict) -> str:
    """The prompt the critic sees for one prediction."""
    return (f"{CRITIC_PROMPT}\n\n"
            f"Customer: {p['full_name']} (#{p['user_id']})\n"
            f"Current risk: {p['risk_level']}\n"
            f"ML churn probability: {p['churn_probability']}\n"
            f"Evidence: {json.dumps(p['evidence'])}\n"
            f"Analyst reason: {p['reason']}")


def precision(pred_list, churned: set):
    """Return (precision, true positives, flagged count) for HIGH/MEDIUM flags."""
    flagged = {p["user_id"] for p in pred_list if p["risk_level"] in ("HIGH", "MEDIUM")}
    if not flagged:
        return 0.0, 0, 0
    tp = len(flagged & churned)
    return tp / len(flagged), tp, len(flagged)


def main():
    from .utils import get_model

    critic = get_model().with_structured_output(CriticVerdict)

    from .eval import future_churners

    with open(PREDICTIONS_PATH) as f:
        preds = json.load(f)
    churned = future_churners()

    reviewed = []
    print("Critic reviewing each verdict...\n")
    for p in preds:
        v = critic.invoke(critic_message(p))
        if v.risk_level != p["risk_level"]:
            print(f"  CHANGED user {p['user_id']:>3} {p['full_name']:<18} "
                  f"{p['risk_level']} -> {v.risk_level}  ({v.critique})")
        reviewed.append({**p, "risk_level": v.risk_level, "critique": v.critique})

    p_before, tp_b, n_b = precision(preds, churned)
    p_after, tp_a, n_a = precision(reviewed, churned)

    print("\n" + "=" * 55)
    print("CRITIC IMPACT (precision = flagged that truly churned)")
    print("=" * 55)
    print(f"Before critic: precision {p_before:.2f}  ({tp_b}/{n_b} flagged)")
    print(f"After  critic: precision {p_after:.2f}  ({tp_a}/{n_a} flagged)")

    with open(REVIEWED_PATH, "w") as f:
        json.dump(reviewed, f, indent=2)
    print(f"\nSaved reviewed verdicts to {REVIEWED_PATH}")


if __name__ == "__main__":
    main()
