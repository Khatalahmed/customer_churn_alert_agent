"""
pii.py

WHAT : A safety net that removes PII (emails, phone numbers) from tool
       outputs before the LLM sees them. It is wired into the sub-agents as
       middleware.
WHY  : The tools already avoid returning phone/email (data minimisation is
       the main defence). This is defense-in-depth: even if a tool ever
       returned PII by mistake, it is scrubbed before reaching the model.
       A production system would use Microsoft Presidio's NER for broader
       PII (names, addresses); here a light regex covers the obvious cases.
FLOW : wrap_tool_call runs the tool, then redacts its text result.
"""
import re

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\b[6-9]\d{9}\b")   # Indian mobile: 10 digits, starts 6-9


def redact(text: str) -> str:
    """Replace emails and phone numbers with placeholders."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    return text


class PIIRedactionMiddleware(AgentMiddleware):
    """Scrub PII from every tool result before the LLM sees it."""

    def wrap_tool_call(self, request, handler):
        result = handler(request)
        if isinstance(result, ToolMessage) and isinstance(result.content, str):
            cleaned = redact(result.content)
            if cleaned != result.content:
                result = result.model_copy(update={"content": cleaned})
        return result