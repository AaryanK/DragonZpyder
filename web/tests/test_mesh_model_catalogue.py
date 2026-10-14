"""All OpenRouter chat models must be discoverable regardless of their price.

Mocked provider catalogue: no network calls or real paid completions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient
from main import app
from backend import mesh


EXPENSIVE = {
    "id": "google/illustrative-premium-model",
    "name": "Google Illustrative Premium",
    "architecture": {"input_modalities": ["text", "image"],
                     "output_modalities": ["text"]},
    "pricing": {"prompt": "0.000010", "completion": "0.000025"},
}
UNPRICED = {
    "id": "moonshotai/illustrative-new-model",
    "name": "MoonshotAI Illustrative New",
    "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
    "pricing": {},
}
NOT_CHAT = {
    "id": "illustrative/embedding-only",
    "name": "Embedding Only",
    "architecture": {"input_modalities": ["text"], "output_modalities": ["embedding"]},
    "pricing": {},
}
CATALOGUE = [
    *({"id": f"illustrative/model-{i:03}",
       "name": f"Illustrative Model {i:03}",
       "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
       "pricing": {"prompt": "0.00000001", "completion": "0.00000003"}}
      for i in range(650)),
    EXPENSIVE, UNPRICED, NOT_CHAT,
]


def test_full_model_catalogue_and_any_price_chat(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_MESH_GATEWAY_TOKEN", "m" * 48)
    mesh._cache.clear()
    requests = []

    def mock(request):
        path = request.url.path
        if path == "/api/auth/sessions":
            return httpx.Response(200, json=[{"id": "session", "scope": "personal", "current": True}])
        if path == "/internal/provider/models":
            return httpx.Response(200, json={"data": CATALOGUE})
        if path in ("/internal/provider/images/models", "/internal/provider/videos/models"):
            return httpx.Response(200, json={"data": [
                {"id": f"illustrative/other-{i:03}", "name": f"Other Model {i:03}"}
                for i in range(100)]})
        if path == "/internal/provider/chat/completions":
            payload = request.read()
            import json
            parsed = json.loads(payload)
            requests.append(parsed)
            return httpx.Response(200, json={"id": "generation-test",
                "model": parsed["model"],
                "choices": [{"message": {"content": "Mock completion"}}],
                "usage": {"prompt_tokens": 28, "completion_tokens": 11, "total_tokens": 39}})
        return httpx.Response(404)

    with TestClient(app) as client:
        previous = client.app.state.http
        client.app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(mock))
        try:
            catalogue = client.get("/mesh/models")
            assert catalogue.status_code == 200, catalogue.text
            payload = catalogue.json()
            returned = {model["id"]: model for model in payload["chat"]}
            assert len(returned) == 652  # over the previous 500-model cutoff
            assert EXPENSIVE["id"] in returned
            assert UNPRICED["id"] in returned
            assert NOT_CHAT["id"] not in returned
            assert returned[EXPENSIVE["id"]]["promptPrice"] == "0.000010"
            assert returned[UNPRICED["id"]]["promptPrice"] is None
            assert len(payload["image"]) == 100
            assert len(payload["video"]) == 100
            assert [m["name"] for m in payload["chat"]] == sorted(
                [m["name"] for m in payload["chat"]], key=str.casefold)

            headers = {"origin": "http://localhost", "host": "localhost",
                       "cookie": "operly_csrf=good", "x-csrf-token": "good"}
            for model_id in (EXPENSIVE["id"], UNPRICED["id"]):
                response = client.post("http://localhost/mesh/chat",
                    headers=headers,
                    json={"model": model_id, "messages": [
                        {"role": "user", "content": "Hello"}]})
                assert response.status_code == 200, response.text
                assert response.json()["text"] == "Mock completion"
                assert response.json()["model"] == model_id
            assert [body["model"] for body in requests] == [EXPENSIVE["id"], UNPRICED["id"]]

            denied = client.post("http://localhost/mesh/chat",
                headers=headers, json={"model": "nonexistent/model",
                                       "messages": [{"role": "user", "content": "Hello"}]})
            assert denied.status_code == 400
        finally:
            client.app.state.http = previous
            mesh._cache.clear()


def test_frontend_full_catalogue_contract():
    root = Path(__file__).resolve().parents[1]
    script = (root / "mesh.js").read_text()
    picker = (root / "mesh-picker.js").read_text()
    assert "pricePerMillion" in script
    assert "model.replaceChildren(options)" in script
    assert "cheap.slice(0,80)" not in script
    assert "0.0000015" not in script
    assert "matching.slice(0, visibleLimit)" in picker
    assert "for (const option of matching.slice(0, visibleLimit))" in picker
    assert "Show more models" in picker
    assert "option.value.toLocaleLowerCase().includes(query)" in picker
