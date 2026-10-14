"""Network-free tests for Chat Lab. Never make paid OpenRouter calls in CI."""
import base64
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from backend.chat_demo import Attachment, ChatBody, ChatTurn, _payload, _attachment_parts, REQUEST_TIMES


class ChatLabTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "OPENROUTER_API_KEY":"example-provider-key",
            "DRAGONZPYDER_CHAT_PASSWORD":"super-long-example-demo-password",
            "DRAGONZPYDER_CHAT_MODELS":"google/gemini-2.5-flash,openai/gpt-4o-mini"
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        REQUEST_TIMES.clear()
        self.client = TestClient(app, base_url="https://chat.dragonspire.xyz")
        self.addCleanup(self.client.close)
        self.headers = {"x-dragonzpyder-chat":"1"}

    def sign_in(self):
        response = self.client.post("/demo/login", json={"password":"super-long-example-demo-password"}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("HttpOnly", response.headers.get("set-cookie", ""))
        self.assertIn("Secure", response.headers.get("set-cookie", ""))
        return response

    def test_host_separation(self):
        with TestClient(app, base_url="https://chat.dragonspire.xyz") as client:
            response = client.get("/", follow_redirects=False)
            self.assertEqual(response.status_code, 307)
            self.assertEqual(response.headers["location"], "/chat")
            self.assertEqual(client.get("/app.html").status_code, 404)
            self.assertEqual(client.get("/api/auth/sessions").status_code, 404)
        with TestClient(app, base_url="https://dragonzpyder.xyz") as main_client:
            self.assertEqual(main_client.get("/chat").status_code, 404)
            self.assertEqual(main_client.post("/demo/login", json={}, headers=self.headers).status_code, 404)

    def test_page_and_assets_are_available(self):
        self.assertEqual(self.client.get("/chat").status_code, 200)
        self.assertIn("DragonZpyder", self.client.get("/chat").text)
        self.assertEqual(self.client.get("/chat/app.js").status_code, 200)
        self.assertIn("default-src 'none'", self.client.get("/chat").headers["content-security-policy"])

    def test_protected_chat_and_cross_site_rejection(self):
        chat = {"model":"google/gemini-2.5-flash", "messages":[{"role":"user","content":"Hi"}]}
        self.assertEqual(self.client.post("/demo/chat", json=chat, headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post("/demo/login", json={"password":"wrong"}, headers=self.headers).status_code, 401)
        self.assertEqual(self.client.post("/demo/login", json={"password":"super-long-example-demo-password"}).status_code, 403)
        self.assertEqual(self.client.post("/demo/login", json={"password":"super-long-example-demo-password"}, headers={**self.headers,"origin":"https://evil.example"}).status_code, 403)

    def test_login_and_mocked_inference(self):
        self.sign_in()
        class MockUpstream:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return None
            async def post(self, url, *, json, headers):
                assert url == "https://openrouter.ai/api/v1/chat/completions"
                assert json["model"] == "google/gemini-2.5-flash"
                assert json["messages"][-1] == {"role":"user","content":"Hi"}
                assert headers["Authorization"].startswith("Bearer ")
                class Result:
                    status_code = 200
                    def json(self):
                        return {"choices":[{"message":{"content":"Hello from mock"}}], "usage":{"total_tokens":3}, "model":"google/gemini-2.5-flash"}
                return Result()
        with patch("backend.chat_demo.httpx.AsyncClient", return_value=MockUpstream()):
            result = self.client.post("/demo/chat", json={"model":"google/gemini-2.5-flash","messages":[{"role":"user","content":"Hi"}]}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["reply"], "Hello from mock")
        self.assertEqual(result.json()["usage"]["total_tokens"], 3)

    def test_allowlist_and_bad_inputs(self):
        self.sign_in()
        invalid = {"model":"evil/model","messages":[{"role":"user","content":"Hi"}]}
        result = self.client.post("/demo/chat", json=invalid, headers=self.headers)
        self.assertEqual(result.status_code, 403)
        invalid["model"] = "google/gemini-2.5-flash"
        invalid["attachments"] = [{"name":"script.exe","data":base64.b64encode(b"malware").decode()}]
        self.assertEqual(self.client.post("/demo/chat", json=invalid, headers=self.headers).status_code, 415)
        invalid["attachments"] = [{"name":"fake.pdf","data":base64.b64encode(b"not pdf").decode()}]
        self.assertEqual(self.client.post("/demo/chat", json=invalid, headers=self.headers).status_code, 422)

    def test_pdf_and_image_openrouter_wire_format(self):
        sample = base64.b64encode(b"%PDF-1.4\nhello").decode()
        img = base64.b64encode(b"\x89PNG\r\n\x1a\nmore").decode()
        body = ChatBody(
            model="google/gemini-2.5-flash",
            messages=[ChatTurn(role="user",content="Describe these")],
            attachments=[Attachment(name="report.pdf",data=sample),Attachment(name="figure.png",data=img)]
        )
        payload = _payload(body)
        self.assertEqual(payload["plugins"][0]["pdf"]["engine"], "cloudflare-ai")
        parts = payload["messages"][-1]["content"]
        self.assertEqual(parts[1]["type"], "file")
        self.assertTrue(parts[1]["file"]["file_data"].startswith("data:application/pdf;base64,"))
        self.assertEqual(parts[2]["type"], "image_url")

    def test_over_budget_rejected_before_external_request(self):
        self.sign_in()
        too_big = {"model":"google/gemini-2.5-flash","messages":[{"role":"user","content":"hello"}],"attachments":[{"name":"notes.txt","data":"a" * (4_300_001)}]}
        self.assertEqual(self.client.post("/demo/chat",json=too_big,headers=self.headers).status_code,422)

    def test_session_logout(self):
        self.sign_in()
        self.assertTrue(self.client.get("/demo/session").json()["authenticated"])
        self.client.post("/demo/logout",json={},headers=self.headers)
        self.assertFalse(self.client.get("/demo/session").json()["authenticated"])


if __name__ == "__main__":
    unittest.main()
