"""Opt-in, bounded Deep Agents harness for the DragonZpyder core.

No network, computer, MCP, or workspace tools are granted here.
The virtual StateBackend is checkpointed by LangGraph; it does not touch
the Railway container's host filesystem.
"""
from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware
from langchain.agents.middleware import TodoListMiddleware, ModelCallLimitMiddleware

VIRTUAL_TOOLS = ("ls", "read_file", "write_file", "edit_file", "glob", "grep")

SUPERVISOR_PROMPT = """You are DragonZpyder's general-purpose autonomous agent.

Primary mission: accomplish the requested objective, not merely describe
how it might be accomplished. Use the least necessary computation.

Operating discipline:
- For a simple task, answer directly; avoid unnecessary plans and subagents.
- For nontrivial objectives, explicitly define acceptance criteria, maintain
  a concise todo plan, and update it as evidence changes.
- You may use the virtual /workspace/ filesystem to draft, inspect, and revise
  working artifacts; it is not the user's real computer. Do not claim that
  virtual files were deployed, emailed, or saved to external accounts.
- Delegate independent *analysis or verification* tasks to the respective
  specialist only if it materially improves quality. Delegate distinct,
  independent subtasks concurrently when possible, never duplicate work.
- Treat subagent reports as claims, not ground truth. Reconcile contradictory
  findings against the provided evidence.
- Validate results against acceptance criteria and identify what could not be
  verified. Do not fabricate citations, tool executions, or successful actions.
- External web, OS, browser, and business tools are NOT available in this
  harness. Say so if the objective genuinely requires them.
- Do not request user passwords, keys, or unneeded personal information.
- Stop on a genuine blocker, exhausted budget, or fulfilled objective.
- Return the actual result and verification status succinctly.
"""

ANALYST_PROMPT = """You are DragonZpyder's specialist analyst.
Work solely on the specific research, design, decomposition or reasoning
question delegated to you, using only supplied material and authorized tools.
Identify assumptions, compare competing explanations and cite supplied
evidence precisely; do not invent external research. Return a concise
evidence-backed report, not hidden intermediate reasoning.
"""

REVIEWER_PROMPT = """You are DragonZpyder's independent critical verifier.
Review a proposed outcome against its stated acceptance criteria and
available evidence. Look for contradictions, missing steps, invalid reasoning
and unverified claims. Be precise about what is proven and what is merely
plausible; do not claim to have executed code or visited a website without
tool evidence. Return actionable corrections and a clear pass/fail/unknown.
"""


def specialist_specs() -> list[dict]:
    """Delegation profiles. No external user/account tools are inherited."""
    return [
        {
            "name": "analyst",
            "description": (
                "Independently analyze a complicated subproblem or compare "
                "approaches when a concise specialized report helps the goal."
            ),
            "system_prompt": ANALYST_PROMPT,
            "tools": [],
        },
        {
            "name": "verifier",
            "description": (
                "Critically review a result, argument or artifact against "
                "explicit acceptance criteria; report unverified claims."
            ),
            "system_prompt": REVIEWER_PROMPT,
            "tools": [],
        },
    ]


def build_frontier_agent(model, checkpointer):
    """Compose real LangChain primitives without making a provider request."""
    virtual_state = StateBackend()
    return create_deep_agent(
        model=model,
        backend=virtual_state,
        checkpointer=checkpointer,
        middleware=[
            FilesystemMiddleware(
                backend=virtual_state,
                tools=list(VIRTUAL_TOOLS),
                tool_token_limit_before_evict=8000,
            ),
            TodoListMiddleware(),
            # This is *per agent*; global/account cost ceilings remain a
            # separate responsibility of the metered gateway.
            ModelCallLimitMiddleware(run_limit=8),
        ],
        subagents=specialist_specs(),
        system_prompt=SUPERVISOR_PROMPT,
    )
