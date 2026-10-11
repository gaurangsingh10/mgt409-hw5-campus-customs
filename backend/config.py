"""Paths, model and limits shared by the whole backend."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
HW5 = BACKEND.parent
load_dotenv(HW5 / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PROMPTS_DIR = BACKEND / "prompts"
AUDIT_PATH = HW5 / "output" / "audit_trail.json"
MCP_CONFIG_PATH = HW5 / ".mcp.json"
MCP_SERVER_NAME = "campus-customs"

# Assignment rule: every agent uses gpt-6-luna via Portkey. Not overridable on purpose.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# --- Token / loop guardrails -------------------------------------------------
# One budget is shared by the boss and every agent it delegates to for a ticket
# (child runs reuse the parent's usage counter), so these cap the whole team run.
TEAM_REQUEST_LIMIT = 30         # model calls per ticket, across all agents
TEAM_TOOL_CALLS_LIMIT = 45      # tool calls per ticket, across all agents
TEAM_TOTAL_TOKENS_LIMIT = 150_000
MAX_OUTPUT_TOKENS = 1_500       # per model response
MAX_DELEGATION_DEPTH = 3        # boss -> A -> B -> C, no deeper
MAX_DELEGATIONS_BOSS = 3        # per boss run
MAX_DELEGATIONS_SPECIALIST = 1  # per specialist run (the boss does the routing)
AUDIT_TEXT_LIMIT = 3_000        # chars kept per tool result / text part in the audit


def mcp_server_config() -> dict:
    """The campus-customs entry from HW5/.mcp.json, the same config Claude Code uses.

    Paths in .mcp.json are relative to the project root so the repo works on any
    machine; resolve them here and run the server from the project root. If the
    configured interpreter isn't there (e.g. Windows venv layout), use this one.
    """
    cfg = dict(json.loads(MCP_CONFIG_PATH.read_text())["mcpServers"][MCP_SERVER_NAME])
    command = HW5 / cfg["command"]
    cfg["command"] = str(command) if command.exists() else sys.executable
    cfg["args"] = [str(HW5 / a) if (HW5 / a).exists() else a for a in cfg.get("args", [])]
    cfg.setdefault("cwd", str(HW5))
    return cfg
