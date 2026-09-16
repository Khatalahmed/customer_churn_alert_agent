"""
schemas.py

WHAT : This file holds the response format for the deep agent. It is a set
       of Pydantic models. The agent must fill them in with its final answer.
WHY  : A free-text report is hard for a program to read or check. A fixed
       schema gives us clean data. The Evidence block holds the exact
       numbers the agent used, so a separate verifier can check them against
       the database and catch any made-up facts.
LOGIC: The agent returns one assessment per customer it investigated. Each
       assessment carries an Evidence block with plain numbers, so nothing
       is hidden inside prose.
"""
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """The exact numbers the agent used to judge one customer.

    These come from the sub-agent tools. A verifier re-computes the same
    numbers from the database and checks that they match.
    """
    logins_prev_30_60d: int = Field(description="Login count 30 to 60 days ago")
    logins_recent_30d: int = Field(description="Login count in the last 30 days")
    total_orders: int = Field(description="Total orders the customer has ever placed")
    total_tickets: int = Field(description="Total support tickets the customer raised")
    unresolved_serious_tickets: int = Field(
        description="Unresolved tickets about delivery, payment, refund, quality or a wrong order"
    )
    worst_review_rating: int = Field(
        description="The lowest review rating (1 to 5). Use 0 if the customer has no reviews."
    )


class ChurnAssessment(BaseModel):
    """One customer's findings. The RISK LEVEL is not here on purpose: it is
    computed in code by churn.rubric from the verified facts, so it is
    reproducible. The agent supplies the evidence and the explanation."""
    user_id: int = Field(description="The customer's user_id")
    full_name: str = Field(description="The customer's name")
    churn_probability: float = Field(
        description="The ML model's churn probability (0 to 1), from get_churn_candidates"
    )
    evidence: Evidence = Field(description="The exact numbers found for this customer")
    reason: str = Field(
        description="Short, evidence-based summary of what the tickets and reviews show. "
                    "Do NOT state a risk level - that is decided in code."
    )

    
class ChurnReport(BaseModel):
    """The full report: one assessment for every customer investigated."""
    assessments: list[ChurnAssessment] = Field(
        description="One item per customer investigated"
    )