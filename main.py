"""
main.py

WHAT : This is the main program. It builds the deep agent (the manager) and
       its sub-agents, then runs one churn analysis and reports the run cost.
WHY  : The ML model scores all customers cheaply and ranks them by priority
       (churn risk x value). The agent then investigates only the top ones.
       This is the full hybrid: ML predicts, the agent investigates, and
       both feed the final decision. We also track token cost per run.
FLOW : build model -> define the sub-agents (risk-ranker, ticket, review) ->
       build the deep agent -> run the task -> print report -> save
       predictions -> print the token cost of the run.
LOGIC: a sub-agent's "description" tells the MANAGER when to call it. A
       sub-agent's "system_prompt" tells the SUB-AGENT how to do its job.
"""
import json

from deepagents import create_deep_agent
from langchain_core.callbacks import UsageMetadataCallbackHandler

from utils import get_model
from scoring import get_churn_candidates
from tools import get_user_tickets, get_user_reviews
from prompts import (
    RISK_RANKER_PROMPT,
    TICKET_PROMPT,
    REVIEW_PROMPT,
    SUPERVISOR_PROMPT,
)
from schemas import ChurnReport

model = get_model()

# The three sub-agents. Each is a simple dictionary. The manager calls them
# by name through its built-in "task" tool.
subagents = [
    {
        "name": "risk-ranker",
        "description": (
            "Runs the ML model and returns the top churn-risk customers, "
            "ranked by priority (risk x value), with churn probability, login "
            "trend, and orders. Call this FIRST to choose who to investigate."
        ),
        "system_prompt": RISK_RANKER_PROMPT,
        "tools": [get_churn_candidates],
    },
    {
        "name": "ticket-analyst",
        "description": (
            "Checks one customer's support tickets for negative signals. "
            "Needs a user_id."
        ),
        "system_prompt": TICKET_PROMPT,
        "tools": [get_user_tickets],
    },
    {
        "name": "review-analyst",
        "description": (
            "Checks one customer's reviews for low ratings or silence. "
            "Needs a user_id."
        ),
        "system_prompt": REVIEW_PROMPT,
        "tools": [get_user_reviews],
    },
]

# The deep agent. It gets NO database tools of its own (tools=[]). It only
# plans and delegates to the sub-agents above.
agent = create_deep_agent(
    model=model,
    tools=[],
    system_prompt=SUPERVISOR_PROMPT,
    subagents=subagents,
    response_format=ChurnReport,          # forces structured output
)


def extract_text(message) -> str:
    """Get plain text from a message.

    Gemini can return the content as a string or as a list of blocks, so we
    handle both cases here.
    """
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
        else:
            parts.append(str(block))
    return "\n".join(parts)


if __name__ == "__main__":
    task = (
        "Find the customers most likely to churn. First get the top 15 "
        "priority candidates from the ML risk-ranker, then investigate each "
        "one's tickets and reviews, decide a final risk level using both the "
        "ML probability and the evidence, and give one assessment per customer."
    )

    # a callback that records how many tokens every model call used
    usage_cb = UsageMetadataCallbackHandler()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"callbacks": [usage_cb]},
    )

    # The structured output lives in result["structured_response"].
    report: ChurnReport = result["structured_response"]

    # Print a readable summary.
    print("\n" + "=" * 70)
    print("CHURN ASSESSMENTS")
    print("=" * 70)
    for a in report.assessments:
        print(f"[{a.risk_level:<6}] user {a.user_id:>3} {a.full_name:<18} "
              f"prob={a.churn_probability:.2f} -> {a.suggested_action}")
        print(f"         reason: {a.reason}")

    # Save the machine-readable predictions for the eval and verifier scripts.
    predictions = [a.model_dump() for a in report.assessments]
    with open("churn_predictions.json", "w") as f:
        json.dump(predictions, f, indent=2)
    print(f"\nSaved {len(predictions)} predictions to churn_predictions.json")

    # --- cost of this run (token usage x approximate Gemini Flash pricing) ---
    # NOTE: rates are approximate - adjust to your provider's current pricing.
    PRICE_IN_PER_M = 0.15    # USD per 1M input tokens
    PRICE_OUT_PER_M = 0.60   # USD per 1M output tokens
    USD_TO_INR = 83

    in_tok = sum(u.get("input_tokens", 0) for u in usage_cb.usage_metadata.values())
    out_tok = sum(u.get("output_tokens", 0) for u in usage_cb.usage_metadata.values())
    cost_usd = (in_tok / 1_000_000) * PRICE_IN_PER_M + (out_tok / 1_000_000) * PRICE_OUT_PER_M

    print("\n" + "=" * 70)
    print("RUN COST")
    print("=" * 70)
    print(f"Input tokens:  {in_tok:>8,}")
    print(f"Output tokens: {out_tok:>8,}")
    print(f"Total tokens:  {in_tok + out_tok:>8,}")
    print(f"Estimated cost: ${cost_usd:.4f}  (~Rs {cost_usd * USD_TO_INR:.2f}) per scan")