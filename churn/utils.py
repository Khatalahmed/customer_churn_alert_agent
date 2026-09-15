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


def _require(name: str) -> str:
    """Read a required setting, with a clear message instead of a vague SDK error."""
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is not set - add it to .env (see .env.example)")
    return value


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

    if provider == "azure":
        # Azure OpenAI with KEYLESS auth (Microsoft Entra ID). There is no API
        # key to leak: DefaultAzureCredential uses your `az login` session
        # locally, and a managed identity when deployed on Azure. The identity
        # needs the "Cognitive Services OpenAI User" role on the resource.
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        endpoint = _require("AZURE_OPENAI_ENDPOINT")
        deployment = _require("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "v1"
        # no temperature: newer (reasoning) deployments reject anything but the default
        if api_version == "v1":
            # v1 API: OpenAI-compatible URL (/openai/v1/), no dated api-version,
            # and the deployment name is passed as the model
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                base_url=endpoint.rstrip("/") + "/openai/v1/",
                api_key=token_provider,
                model=deployment,
            )
        # older dated API versions, e.g. 2024-10-21
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_version=api_version,
            azure_ad_token_provider=token_provider,
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
