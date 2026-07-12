"""Executable role profiles for specialized M.I.C.A sub-agents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRoleProfile:
    id: str
    name: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    model_intent: str
    expected_output: str


ROLE_PROFILES: dict[str, AgentRoleProfile] = {
    "orchestrator": AgentRoleProfile(
        "orchestrator", "Orchestrator",
        "Coordinate specialists, preserve dependencies, request approval for risk, and return compact handoffs.",
        ("task_graph", "task_pipeline", "approval_flow", "generated_code"),
        "tool_planning", "A delegated plan with owners, dependencies, gates, and completion evidence.",
    ),
    "planner": AgentRoleProfile(
        "planner", "Planner",
        "Create a safe, dependency-aware plan. Do not execute implementation work.",
        ("task_graph", "create_note_action", "generated_code"),
        "tool_planning", "A concise plan with risks, acceptance criteria, and the next safe step.",
    ),
    "research": AgentRoleProfile(
        "research", "Research",
        "Research precisely, compare evidence, label uncertainty, and never invent sources.",
        ("web_search", "documents_search", "summarize_text", "generated_code"),
        "research", "A source-grounded finding with uncertainty and a compact handoff.",
    ),
    "execution": AgentRoleProfile(
        "execution", "Execution",
        "Execute only approved work, prefer reversible changes, and record concrete verification evidence.",
        ("run_sandbox", "create_note_action", "normalize_text", "generated_code"),
        "code_edit", "A concrete result, changed artifacts, and verification evidence.",
    ),
    "review": AgentRoleProfile(
        "review", "Review",
        "Independently check requirements, tests, evidence, and safety. Approve only what is proven.",
        ("evidence", "test_tool", "generated_code"),
        "code_review", "Prioritized findings or a proof-backed approval.",
    ),
    "monitor": AgentRoleProfile(
        "monitor", "Monitor",
        "Observe runs, costs, failures, resources, and safety signals. Escalate anomalies early.",
        ("aggregate_metrics", "healthcheck", "generated_code"),
        "summary", "A short operational status with anomalies and the next safe action.",
    ),
}


AGENT_TYPE_PROFILE = {
    "deep_research": "research",
    "data_analyst": "research",
    "code_expert": "execution",
    "web_scraper": "research",
    "file_manager": "execution",
    "general": "orchestrator",
}


def get_role_profile(profile_id: str = "", *, agent_type: str = "general") -> AgentRoleProfile:
    resolved = profile_id if profile_id in ROLE_PROFILES else AGENT_TYPE_PROFILE.get(agent_type, "orchestrator")
    return ROLE_PROFILES[resolved]
