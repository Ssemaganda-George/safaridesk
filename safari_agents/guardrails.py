"""Guardrails that live OUTSIDE the model, so a clever prompt cannot talk its way past them."""
import json
import re
import time
import pathlib
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

AUDIT_FILE = pathlib.Path("audit.jsonl")
MAX_AGENT_DISCOUNT_PCT = 10

INJECTION_PATTERNS = [
    r"ignore (all |any |your )?(previous|prior|above|earlier) (instructions|rules|policies)",
    r"(reveal|show|print).{0,30}(system prompt|instructions|api key)",
    r"you are now",
    r"developer mode",
    r"override.{0,20}(policy|policies|limit|rules)",
]


def _log(event: dict) -> None:
    event["ts"] = round(time.time(), 2)
    with AUDIT_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")


def _user_text(content: Optional[types.Content]) -> str:
    if not content or not content.parts:
        return ""
    return " ".join(p.text for p in content.parts if getattr(p, "text", None))


def input_guard(callback_context: CallbackContext) -> Optional[types.Content]:
    """Runs before the whole pipeline. Returning Content skips every agent."""
    text = _user_text(callback_context.user_content)
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            _log({"event": "BLOCKED_INPUT", "pattern": pattern, "text": text[:200]})
            return types.Content(role="model", parts=[types.Part(text=(
                "I can only help with safari and tour enquiries, and I can't follow instructions "
                "that change how I work. Tell me where you'd like to go, when, and for how many people."))])
    _log({"event": "INPUT_OK", "text": text[:200]})
    return None


def tool_policy(tool: BaseTool, args: dict, tool_context: ToolContext) -> Optional[dict]:
    """Runs before every tool call. Returning a dict skips the tool and feeds that dict to the model."""
    _log({"event": "TOOL_CALL", "agent": tool_context.agent_name, "tool": tool.name, "args": args})
    if tool.name == "apply_discount" and float(args.get("percent", 0)) > MAX_AGENT_DISCOUNT_PCT:
        _log({"event": "BLOCKED_TOOL", "tool": tool.name, "args": args})
        return {"status": "blocked",
                "message": f"Agents may not give more than {MAX_AGENT_DISCOUNT_PCT}% discount. "
                           "Escalate to a human manager."}
    return None


def tool_audit(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response: dict) -> Optional[dict]:
    """Runs after every tool call, for the audit trail."""
    _log({"event": "TOOL_RESULT", "agent": tool_context.agent_name, "tool": tool.name,
          "result": str(tool_response)[:300]})
    return None
