"""Smoke-test DragonZpyder's existing image endpoint without incurring provider charges.

Production must remain disabled until a key-level OpenRouter spending cap is
verified. These tests exercise the actual FastAPI Mesh router with a mocked
Personal session and mocked central provider gateway, without a real API key.
"""
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient

from main import app


IMAGE = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YbRO5UAAAAASUVORK5CYII="
    )
).decode("ascii")
PROMPT = "Create an image of a dragon flying above Kathmandu"
HEADERS = {
    "host": "localhost",
    "origin": "http://localhost",
    "cookie": "operly_csrf=test",
    "x-csrf-token": "test",
}


def test_image_mode_disabled_by_default_and_enabled_path_sends_one_bounded_request(monkeypatch):
    requests = []

    def fake_services(request):
        path = request.url.path
        if path == "/api/auth/sessions":
            return httpx.Response(200, json=[
                {"id": "smoke-test-session", "scope": "personal", "current": True}
            ])
        if path == "/internal/provider/models":
            return httpx.Response(200, json={"data": []})
        if path == "/internal/provider/images/models":
            return httpx.Response(200, json={"data": [
                {"id": "test/image-model", "name": "Mock image model"}
            ]})
        if path == "/internal/provider/videos/models":
            return httpx.Response(200, json={"data": []})
        if path == "/internal/provider/images":
            requests.append(request)
            return httpx.Response(200, json={
                "data": [{"b64_json": IMAGE}],
                "usage": {"cost": 0.01},
            })
        return httpx.Response(404)

    monkeypatch.setenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN", "m" * 48)
    monkeypatch.delenv("MESH_ENABLE_IMAGE", raising=False)

    with TestClient(app) as client:
        original_http = client.app.state.http
        client.app.state.http = httpx.AsyncClient(
            transport=httpx.MockTransport(fake_services)
        )
        try:
            catalogue = client.get("http://localhost/mesh/models", headers=HEADERS)
            assert catalogue.status_code == 200, catalogue.text
            assert catalogue.json()["imageEnabled"] is False
            assert catalogue.json()["image"] == [
                {"id": "test/image-model", "name": "Mock image model"}
            ]

            payload = {"model": "test/image-model", "prompt": PROMPT, "confirmed": True}
            disabled = client.post(
                "http://localhost/mesh/image", headers=HEADERS, json=payload
            )
            assert disabled.status_code == 403, disabled.text
            assert not requests

            # Enabling in the isolated test process does not alter Railway.
            monkeypatch.setenv("MESH_ENABLE_IMAGE", "true")
            assert client.get(
                "http://localhost/mesh/models", headers=HEADERS
            ).json()["imageEnabled"] is True

            confirmation_required = client.post(
                "http://localhost/mesh/image", headers=HEADERS,
                json={**payload, "confirmed": False},
            )
            assert confirmation_required.status_code == 400
            assert not requests

            generated = client.post(
                "http://localhost/mesh/image", headers=HEADERS, json=payload
            )
            assert generated.status_code == 200, generated.text
            result = generated.json()
            assert result["model"] == "test/image-model"
            assert result["image"].startswith("data:image/png;base64,")
            assert base64.b64decode(result["image"].split(",", 1)[1]) == base64.b64decode(IMAGE)
            assert result["usage"]["cost"] == 0.01
            assert len(requests) == 1
            assert requests[0].json() == {
                "model": "test/image-model", "prompt": PROMPT, "n": 1
            }
        finally:
            client.app.state.http = original_http


def test_image_generation_requires_personal_csrf_even_when_enabled(monkeypatch):
    monkeypatch.setenv("MESH_ENABLE_IMAGE", "true")
    monkeypatch.setenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN", "m" * 48)
    with TestClient(app) as client:
        result = client.post("/mesh/image", json={
            "model": "test/image-model", "prompt": PROMPT, "confirmed": True
        })
        assert result.status_code == 403
