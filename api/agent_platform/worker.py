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
    # Hatchet manages task assignment; the PostgreSQL ledger owns occurrence
    # state, replay protection and evidence. No client-driven cron creation.
    if os.getenv("DRAGONZPYDER_GOAL_TICK_ENABLED") == "1":
        from .goal_tick import make_goal_tick_task, require_synthetic_gate
        require_synthetic_gate()
        workflows.append(make_goal_tick_task(hatchet))
    worker = hatchet.worker("dragonzpyder-agent-worker", slots=2, workflows=workflows)
    worker.start()


if __name__ == "__main__":
    main()
