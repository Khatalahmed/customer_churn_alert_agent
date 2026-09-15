"""
utils.py

WHAT : This file has one job: get_model(). It is the single place where
       the LLM is built.
WHY  : Every agent and sub-agent uses this one factory. So we can switch
       the whole provider (Vertex, Groq, Gemini) by editing the .env file
       only. We never change the agent code. This is the rule from both
       classes.
FLOW : read MODEL_PROVIDER and MODEL_NAME from .env -> build the matching
       chat model -> return it.
LOGIC: temperature=0 makes the model steady and repeatable. For a churn
       analysis we want the same input to give the same answer.
"""
import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

load_dotenv()


def get_model() -> BaseChatModel:
    """Return the LLM chosen by MODEL_PROVIDER in the .env file."""
    provider = os.getenv("MODEL_PROVIDER", "groq").lower()
    model_name = os.getenv("MODEL_NAME")

    if provider == "vertex":
        # Vertex AI: runs on Google Cloud, paid by our free-trial credits.
        # It uses ADC (gcloud login), so it needs no API key here.
        from langchain_google_vertexai import ChatVertexAI
        return ChatVertexAI(
            model=model_name,
            project=os.getenv("GCP_PROJECT"),
            location=os.getenv("GCP_LOCATION", "us-central1"),
            temperature=0,
        )

    if provider == "groq":
        # Groq: fast and free. A good fallback if Vertex has trouble.
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

    if provider == "google":
        # Gemini via AI Studio key: free tier, but a low rate limit.
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

    raise ValueError(f"Unknown MODEL_PROVIDER: {provider}")


def token_prices() -> tuple[float, float] | None:
    """(USD per 1M input tokens, USD per 1M output tokens) from .env, or None.

    Prices differ per provider and model and change over time, so they are
    configuration, not code - the same rule as MODEL_PROVIDER. Set
    MODEL_PRICE_IN_PER_M and MODEL_PRICE_OUT_PER_M from your provider's
    current pricing page.
    """
    price_in = os.getenv("MODEL_PRICE_IN_PER_M")
    price_out = os.getenv("MODEL_PRICE_OUT_PER_M")
    if not price_in or not price_out:
        return None
    return float(price_in), float(price_out)
