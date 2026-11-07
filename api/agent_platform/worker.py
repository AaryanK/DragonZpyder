"""Private Hatchet worker entrypoint; opt-in and intentionally separate from API."""
import os

from hatchet_sdk import Hatchet

from .jobs import make_agent_task


def main() -> None:
    if os.getenv("DRAGONZPYDER_AGENTS_ENABLED") != "1":
        raise RuntimeError("Agent runtime is not enabled")
    if os.getenv("DRAGONZPYDER_AGENT_WORKER_ALLOWED") != "1":
        raise RuntimeError("Dedicated agent worker not approved for this environment")
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        raise RuntimeError("Hatchet client token missing")
    hatchet = Hatchet()
    task = make_agent_task(hatchet)
    worker = hatchet.worker("dragonzpyder-agent-worker", slots=2, workflows=[task])
    worker.start()


if __name__ == "__main__":
    main()
