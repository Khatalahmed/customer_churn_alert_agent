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
from typing import Literal

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
    worst_review_rating: int = Field(
        description="The lowest review rating (1 to 5). Use 0 if the customer has no reviews."
    )


class ChurnAssessment(BaseModel):
    """One customer's churn assessment."""
    user_id: int = Field(description="The customer's user_id")
    full_name: str = Field(description="The customer's name")
    risk_level: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="HIGH or MEDIUM means likely to churn. LOW means safe."
    )
    churn_probability: float = Field(
        description="The ML model's churn probability (0 to 1), from get_churn_candidates"
    )
    evidence: Evidence = Field(description="The exact numbers behind the risk level")
    reason: str = Field(description="Short, evidence-based reason for the risk level")
    suggested_action: str = Field(description="coupon, retention call, or ignore")

    
class ChurnReport(BaseModel):
    """The full report: one assessment for every customer investigated."""
    assessments: list[ChurnAssessment] = Field(
        description="One item per customer investigated"
    )