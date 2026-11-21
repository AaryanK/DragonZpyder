"""Private Hatchet worker entrypoint; opt-in and intentionally separate from API."""
import os

from hatchet_sdk import Hatchet

from .jobs import make_agent_task, make_ping_task


def main() -> None:
    if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
        raise RuntimeError("Agent runtime is not enabled")
    if os.getenv("DRAGONZPYDER_AGENT_WORKER_ALLOWED") != "1":
        raise RuntimeError("Dedicated agent worker not approved for this environment")
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise RuntimeError("Hatchet client token missing")
    hatchet = Hatchet()
    task = make_agent_task(hatchet)
    workflows = [make_ping_task(hatchet), task]
    if (os.getenv("DRAGONZPYDER_AGENT_HARNESS_V2") == "1"
            and os.getenv("DRAGONZPYDER_WEB_MONITOR_ENABLED") == "1"
            and os.getenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED") == "1"):
        from .monitor import make_monitor_task
        workflows.append(make_monitor_task(hatchet))
    if os.getenv("DRAGONZPYDER_LOCAL_MONITOR_ENABLED") == "1":
        # Staging-only, explicit operator-scheduled local monitor.
        # Worker registration does NOT create or modify a Hatchet cron.
        from .local_monitor import make_local_monitor_task, require_monitor_gate
        require_monitor_gate()
        workflows.append(make_local_monitor_task(hatchet))
    if os.getenv("DRAGONZPYDER_PERSONAL_MCP_SCHEDULED_ENABLED") == "1":
        # Register only. Creating a cron or accepting a user job is a separate
        # explicit authorization; credentials are rechecked at every wake.
        from .personal_wake import make_personal_mcp_wake_task, require_wake_gate
        require_wake_gate()
        workflows.append(make_personal_mcp_wake_task(hatchet))
    if os.getenv("DRAGONZPYDER_EXECUTION_GRAPH_ENABLED") == "1":
        # User-created bounded read DAGs; registration never creates a schedule.
        from .persistent_graph import make_graph_hatchet_task
        workflows.append(make_graph_hatchet_task(hatchet))
    if os.getenv("DRAGONZPYDER_NATIVE_CANARY_ENABLED") == "1":
        # Native-only scheduling smoke test. No Operly/MCP/user token/model.
        from .native_canary import make_native_canary_hatchet_task
        workflows.append(make_native_canary_hatchet_task(hatchet))
    if os.getenv("DRAGONZPYDER_PERSONAL_GOAL_CONTROLLER_ENABLED") == "1":
        # Operator-opt-in registration only. Explicit trusted dispatch is
        # required to start a Personal goal; no default cron or user trigger.
        from .personal_wake import make_personal_goal_controller_task
        workflows.append(make_personal_goal_controller_task(hatchet))
    worker = hatchet.worker("dragonzpyder-agent-worker", slots=2, workflows=workflows)
    worker.start()


if __name__ == "__main__":
    main()
