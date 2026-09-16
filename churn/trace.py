"""
trace.py

WHAT : Records every tool call an agent run makes - which tool, with what
       arguments, in what order, and how long it took - and saves it as JSON.
WHY   : Accuracy tells you whether the answer was right. It does NOT tell you
       whether the agent got there properly: did it skip the review check for
       some customers, investigate someone who was never on the shortlist, or
       call the same tool eleven times? Those are trajectory bugs, and they
       stay invisible until you record the path. churn.trace_eval checks the
       recorded path against rules.
FLOW  : attach ToolTraceMiddleware to the sub-agents -> it wraps every tool
        call -> save() writes the trace for trace_eval to grade.
"""
import json
import time

from langchain.agents.middleware.types import AgentMiddleware


def _describe(request) -> tuple[str, dict]:
    """Pull (tool name, arguments) out of a tool-call request, defensively.

    The request shape belongs to the agent framework, so this never raises:
    an unrecognised shape is recorded as "unknown" rather than losing the run.
    """
    call = getattr(request, "tool_call", None) or {}
    if isinstance(call, dict):
        name = call.get("name")
        args = call.get("args")
    else:  # object-style tool call
        name = getattr(call, "name", None)
        args = getattr(call, "args", None)
    if name is None:
        tool = getattr(request, "tool", None)
        name = getattr(tool, "name", None) or "unknown"
    return str(name), dict(args or {})


class ToolTraceMiddleware(AgentMiddleware):
    """Append one record per tool call. Shared by every sub-agent, so the
    trace is the whole run in call order."""

    def __init__(self):
        super().__init__()
        self.calls: list[dict] = []

    def wrap_tool_call(self, request, handler):
        name, args = _describe(request)
        started = time.perf_counter()
        try:
            result = handler(request)
        except Exception:
            self.calls.append({"tool": name, "args": args, "ok": False, "ms": 0})
            raise
        self.calls.append({
            "tool": name,
            "args": args,
            "ok": True,
            "ms": round((time.perf_counter() - started) * 1000),
        })
        return result

    def save(self, path) -> int:
        """Write the trace; returns how many calls were recorded."""
        with open(path, "w") as f:
            json.dump({"calls": self.calls}, f, indent=2)
        return len(self.calls)
