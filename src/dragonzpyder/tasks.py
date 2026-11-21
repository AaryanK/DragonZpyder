from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote
from uuid import uuid4

from .client import DragonZpyderClient, DragonZpyderClientError


def _mapping(payload: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise DragonZpyderClientError(
            f"Operly {label} returned an invalid response.",
            code="INVALID_SERVER_RESPONSE",
        )
    return payload


def submit_durable_task(
    client: DragonZpyderClient,
    message: str,
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    max_steps: int = 8,
    max_mutations: int = 4,
) -> Mapping[str, Any]:
    clean_message = str(message or "").strip()
    if not clean_message:
        raise DragonZpyderClientError("Task text is required.", code="TASK_REQUIRED")
    stable_request_id = str(request_id or uuid4()).strip()
    payload: dict[str, Any] = {
        "message": clean_message,
        "request_id": stable_request_id,
        "max_steps": int(max_steps),
        "max_mutations": int(max_mutations),
    }
    if conversation_id:
        payload["conversation_id"] = str(conversation_id).strip()
    result = client.transport.request_json(
        "POST",
        "/api/personal-tools/client/tasks",
        payload,
        csrf=True,
        authenticated=True,
    ).payload
    return _mapping(result, label="durable task submission")


def durable_task_status(client: DragonZpyderClient, task_id: str) -> Mapping[str, Any]:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        raise DragonZpyderClientError("Task ID is required.", code="TASK_ID_REQUIRED")
    result = client.transport.request_json(
        "GET",
        f"/api/personal-tools/client/tasks/{quote(clean_id, safe='')}",
        authenticated=True,
    ).payload
    return _mapping(result, label="durable task status")


def cancel_durable_task(client: DragonZpyderClient, task_id: str) -> Mapping[str, Any]:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        raise DragonZpyderClientError("Task ID is required.", code="TASK_ID_REQUIRED")
    result = client.transport.request_json(
        "POST",
        f"/api/personal-tools/client/tasks/{quote(clean_id, safe='')}/cancel",
        {},
        csrf=True,
        authenticated=True,
    ).payload
    return _mapping(result, label="durable task cancellation")


def resume_durable_task(
    client: DragonZpyderClient,
    task_id: str,
    *,
    approval_id: str | None = None,
) -> Mapping[str, Any]:
    clean_id = str(task_id or "").strip()
    if not clean_id:
        raise DragonZpyderClientError("Task ID is required.", code="TASK_ID_REQUIRED")
    payload: dict[str, Any] = {}
    if approval_id:
        payload["approval_id"] = str(approval_id).strip()
    result = client.transport.request_json(
        "POST",
        f"/api/personal-tools/client/tasks/{quote(clean_id, safe='')}/resume",
        payload,
        csrf=True,
        authenticated=True,
    ).payload
    return _mapping(result, label="durable task resume")


def approve_and_resume_durable_task(
    client: DragonZpyderClient,
    task_id: str,
    approval_id: str,
) -> Mapping[str, Any]:
    """Approve a waiting durable step, then hand it back to Operly's worker.

    Unlike the immediate P6 `approve` flow, this deliberately does not execute the
    capability from DragonZpyder. The task worker must resume the persisted plan so its
    lease/checkpoint/cancellation semantics remain authoritative.
    """

    approval = client.decide_approval(approval_id, approved=True)
    if str(approval.get("status") or "") != "approved":
        raise DragonZpyderClientError(
            "Operly did not record the task approval as approved.",
            code="APPROVAL_NOT_EXECUTABLE",
        )
    return resume_durable_task(client, task_id, approval_id=approval_id)
