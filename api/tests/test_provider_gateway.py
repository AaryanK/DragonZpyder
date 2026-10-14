"""Central AI Mesh/Chat Lab OpenRouter gateway contract tests."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from main import app
from usage_ledger import ledger

MESH_TOKEN = "m" * 48
LAB_TOKEN = "c" * 48
Q_TOKEN = "q" * 48
OPERLY_TOKEN = "o" * 48
PAYLOAD = {"model": "google/gemini-2.5-flash",
           "messages": [{"role": "user", "content": "Hey"}],
           "max_tokens": 80, "stream": False}


def config(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_RUNTIME_TOKEN", "a" * 48)
    monkeypatch.setenv("DRAGONZPYDER_APP_KEYS_JSON",
                       json.dumps({"ai-mesh": MESH_TOKEN, "chat-lab": LAB_TOKEN,
                                   "querypedia": Q_TOKEN, "operly": OPERLY_TOKEN}))
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")
    monkeypatch.setenv("DRAGONZPYDER_IMAGE_OPENROUTER_API_KEY", "mock-capped-image-key")


def test_provider_catalog_scope_and_isolation(monkeypatch):
    config(monkeypatch)
    paths = []
    def transport(request):
        paths.append((request.url.path, request.headers["authorization"]))
        return httpx.Response(200, json={"data": [{"id": "example/model"}]})
    with TestClient(app) as client:
        real_http = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            mesh = {"Authorization": "Bearer " + MESH_TOKEN}
            chat = {"Authorization": "Bearer " + LAB_TOKEN}
            querypedia = {"Authorization": "Bearer " + Q_TOKEN}
            operly = {"Authorization": "Bearer " + OPERLY_TOKEN}
            assert client.get("/internal/provider/models", headers=mesh).status_code == 200
            assert client.get("/internal/provider/images/models", headers=mesh).status_code == 200
            assert client.get("/internal/provider/videos/models", headers=mesh).status_code == 200
            assert client.get("/internal/provider/models", headers=chat).status_code == 403
            assert client.get("/internal/provider/models", headers=querypedia).status_code == 403
            assert client.get("/internal/provider/models", headers=operly).status_code == 403
            assert client.get("/internal/provider/models").status_code == 401
            assert client.get("/internal/provider/unapproved-path", headers=mesh).status_code == 404
            assert all(token == ("Bearer mock-capped-image-key" if path == "/api/v1/images/models" else "Bearer mock-openrouter-key") for path, token in paths)
        finally:
            client.app.state.http = real_http


def test_provider_model_call_audited_per_app(monkeypatch):
    config(monkeypatch)
    events = []
    async def record(**data):
        events.append(data)
        return True
    monkeypatch.setattr(ledger, "record", record)

    def transport(request):
        body = json.loads(request.content)
        assert body["messages"][0]["content"] == "Hey"
        return httpx.Response(200, json={"id": "gen42", "model": body["model"],
            "choices": [{"message": {"content": "Hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 8, "total_tokens": 19,
                      "cost": 0.00004}})
    with TestClient(app) as client:
        real_http = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            for token, expected in ((MESH_TOKEN, "ai-mesh"), (LAB_TOKEN, "chat-lab"), (OPERLY_TOKEN, "operly")):
                response = client.post("/internal/provider/chat/completions", json=PAYLOAD,
                                       headers={"Authorization": "Bearer " + token})
                assert response.status_code == 200, response.text
                assert response.json()["choices"][0]["message"]["content"] == "Hello"
                assert len(response.headers["x-dragonzpyder-trace-id"]) == 32
                assert events[-1]["app_id"] == expected
                assert events[-1]["response"]["usage"]["total_tokens"] == 19
            assert client.post("/internal/provider/chat/completions", json=PAYLOAD,
                               headers={"Authorization": "Bearer " + Q_TOKEN}).status_code == 403
            assert client.post("/internal/provider/images", json={"model":"test/model","prompt":"cat"},
                               headers={"Authorization": "Bearer " + LAB_TOKEN}).status_code == 403
            assert client.post("/internal/provider/images", json={"model":"test/model","prompt":"cat"},
                               headers={"Authorization": "Bearer " + OPERLY_TOKEN}).status_code == 403
            assert client.post("/internal/provider/audio/speech", json={"model":"test/speech","input":"Hi"},
                               headers={"Authorization": "Bearer " + OPERLY_TOKEN}).status_code == 403
        finally:
            client.app.state.http = real_http


def test_stream_usage_recorded_and_usage_frame_passed(monkeypatch):
    config(monkeypatch)
    events = []
    async def record(**data):
        events.append(data)
        return True
    monkeypatch.setattr(ledger, "record", record)
    def transport(request):
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["stream_options"] == {"include_usage": True}
        chunks = [
          {"id":"gen-stream","model":body["model"],
           "choices":[{"delta":{"content":"Hello"}}]},
          {"id":"gen-stream","model":body["model"],
           "choices":[], "usage":{"prompt_tokens":20,"completion_tokens":5,"total_tokens":25}},
        ]
        sse = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            response = client.post("/internal/provider/chat/completions",
                                   json={**PAYLOAD, "stream": True},
                                   headers={"Authorization": "Bearer " + MESH_TOKEN})
            assert response.status_code == 200, response.text
            assert "data: [DONE]" in response.text
            assert events and events[-1]["status"] == "ok"
            assert events[-1]["response"]["usage"]["total_tokens"] == 25
            assert events[-1]["app_id"] == "ai-mesh"
        finally:
            client.app.state.http = old


def test_binary_media_ledger_metadata_and_video_fetch(monkeypatch):
    config(monkeypatch)
    events = []
    async def record(**data):
        events.append(data)
        return True
    monkeypatch.setattr(ledger, "record", record)
    def transport(request):
        if request.url.path.endswith("/audio/speech"):
            return httpx.Response(200, content=b"ID3mockMP3", headers={"content-type":"audio/mpeg"})
        if request.url.path.endswith("/videos/job123/content"):
            return httpx.Response(200, content=b"fake-mp4", headers={"content-type":"video/mp4"})
        return httpx.Response(404)
    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            h={"Authorization": "Bearer " + MESH_TOKEN}
            r=client.post("/internal/provider/audio/speech", headers=h,
                          json={"model":"openai/tts-model","input":"hello","response_format":"mp3"})
            assert r.status_code == 200
            assert r.content == b"ID3mockMP3"
            assert events[-1]["response"]["media_bytes"] == 10
            r=client.get("/internal/provider/videos/job123/content",headers=h)
            assert r.status_code == 200
            assert r.content == b"fake-mp4"
        finally:
            client.app.state.http = old


def test_image_operations_fail_closed_without_dedicated_test_key(monkeypatch):
    config(monkeypatch)
    monkeypatch.delenv("DRAGONZPYDER_IMAGE_OPENROUTER_API_KEY")
    seen = []

    def transport(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={"data": []})

    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            headers = {"Authorization": "Bearer " + MESH_TOKEN}
            assert client.get("/internal/provider/images/models", headers=headers).status_code == 503
            assert client.post("/internal/provider/images", headers=headers, json={
                "model": "test/image-model", "prompt": "a blue bird", "n": 1,
            }).status_code == 503
            assert seen == []
            # Ordinary chat catalogues still work with the existing default key.
            assert client.get("/internal/provider/models", headers=headers).status_code == 200
            assert seen == ["/api/v1/models"]
        finally:
            client.app.state.http = old


def test_image_generation_uses_only_dedicated_key_and_is_audited(monkeypatch):
    config(monkeypatch)
    events = []
    seen = []

    async def record(**data):
        events.append(data)
        return True

    monkeypatch.setattr(ledger, "record", record)

    def transport(request):
        seen.append((request.url.path, request.headers["authorization"], json.loads(request.content)))
        return httpx.Response(200, json={
            "data": [{"b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YbRO5UAAAAASUVORK5CYII="}],
            "usage": {"cost": 0.02},
        })

    with TestClient(app) as client:
        old = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        try:
            headers = {"Authorization": "Bearer " + MESH_TOKEN}
            params = {"model": "test/image-model", "prompt": "A dragon above Kathmandu"}
            rejected = client.post("/internal/provider/images", headers=headers, json={
                **params, "n": 2,
            })
            assert rejected.status_code == 400
            assert seen == []
            response = client.post("/internal/provider/images", headers=headers, json=params)
            assert response.status_code == 200, response.text
            assert response.json()["data"][0]["b64_json"].startswith("iVBOR")
            assert seen == [("/api/v1/images", "Bearer mock-capped-image-key", {**params, "n": 1})]
            assert len(events) == 1
            assert events[0]["app_id"] == "ai-mesh"
            assert events[0]["requested_model"] == "test/image-model"
            assert events[0]["response"]["usage"]["cost"] == 0.02
        finally:
            client.app.state.http = old
