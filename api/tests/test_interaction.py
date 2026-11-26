"""Offline contract tests; no provider calls."""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from agent_platform.interaction import InteractionInput


def test_normalization():
    artifact = uuid4()
    request = uuid4()
    payload = InteractionInput(request_id=request, content=[
        {"kind": "text", "text": "Inspect this"},
        {"kind": "image", "artifact_id": artifact},
    ])
    fields = payload.chat_fields()
    assert fields["request_id"] == request
    assert fields["attachment_ids"] == [artifact]
    assert fields["message"] == "Inspect this"
    assert fields["allow_media"] is False


@pytest.mark.parametrize("content", [
    [{"kind": "text", "text": " "}],
    [{"kind": "audio", "artifact_id": str(uuid4())}],
    [{"kind": "text", "text": "ok", "owner_id": "forged"}],
    [{"kind": "file", "url": "https://example.org/file"}],
])
def test_invalid_content(content):
    with pytest.raises(ValidationError):
        InteractionInput(request_id=uuid4(), content=content)


def test_duplicate_artifacts():
    artifact = uuid4()
    with pytest.raises(ValidationError):
        InteractionInput(request_id=uuid4(), content=[
            {"kind": "text", "text": "inspect"},
            {"kind": "file", "artifact_id": artifact},
            {"kind": "image", "artifact_id": artifact},
        ])
