from __future__ import annotations

import http.cookiejar
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    Request,
    build_opener,
)
from uuid import uuid4

from .config import DragonZpyderConfig


class DragonZpyderClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "CLIENT_ERROR",
        status: int | None = None,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable
        self.details = dict(details or {})


class DragonZpyderAuthError(DragonZpyderClientError):
    pass


@dataclass(frozen=True, slots=True)
class ClientResponse:
    status: int
    payload: Any


class ClientTransport(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        csrf: bool = False,
        authenticated: bool = False,
    ) -> ClientResponse: ...

    def clear(self) -> None: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    """API calls never need cross-origin redirects; fail closed instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        del req, fp, code, msg, headers, newurl
        return None


def default_session_file() -> Path:
    configured = os.getenv("DRAGONZPYDER_SESSION_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    root = os.getenv("XDG_CONFIG_HOME", "").strip()
    base = Path(root).expanduser() if root else Path.home() / ".config"
    return base / "dragonzpyder" / "session.cookies"


class CookieSessionTransport:
    """Small HTTPS JSON transport using Operly's existing session-cookie contract."""

    _SESSION_CSRF_NAMES = ("__Host-operly_csrf", "operly_csrf")
    _PREAUTH_CSRF_NAME = "operly_preauth_csrf"

    def __init__(
        self,
        config: DragonZpyderConfig,
        *,
        session_file: Path | None = None,
    ) -> None:
        self.config = config
        self.session_file = session_file or default_session_file()
        self.cookies = http.cookiejar.MozillaCookieJar(str(self.session_file))
        self._load_existing_cookies()
        self.opener = build_opener(
            HTTPCookieProcessor(self.cookies),
            _NoRedirectHandler(),
        )

    def _load_existing_cookies(self) -> None:
        if not self.session_file.exists():
            return
        try:
            self.cookies.load(ignore_discard=True, ignore_expires=False)
        except (OSError, http.cookiejar.LoadError) as exc:
            raise DragonZpyderClientError(
                "Saved DragonZpyder session is unreadable. Run logout to clear it.",
                code="SESSION_FILE_INVALID",
            ) from exc

    def _save(self) -> None:
        parent = self.session_file.parent
        parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                parent.chmod(0o700)
            except OSError:
                pass
        self.cookies.save(ignore_discard=True, ignore_expires=False)
        if os.name != "nt":
            try:
                self.session_file.chmod(0o600)
            except OSError:
                pass

    def clear(self) -> None:
        self.cookies.clear()
        try:
            self.session_file.unlink()
        except FileNotFoundError:
            pass

    def _csrf_token(self, *, preauth: bool = False) -> str | None:
        names = (
            (self._PREAUTH_CSRF_NAME,)
            if preauth
            else self._SESSION_CSRF_NAMES + (self._PREAUTH_CSRF_NAME,)
        )
        by_name = {cookie.name: cookie.value for cookie in self.cookies}
        for name in names:
            value = by_name.get(name)
            if value:
                return value
        return None

    @staticmethod
    def _decode_payload(raw: bytes) -> Any:
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DragonZpyderClientError(
                "Operly returned a response that was not valid JSON.",
                code="INVALID_SERVER_RESPONSE",
            ) from exc

    @staticmethod
    def _detail(payload: Any, status: int) -> DragonZpyderClientError:
        detail = payload.get("detail") if isinstance(payload, Mapping) else None
        details: dict[str, Any] = {}
        if isinstance(detail, Mapping):
            code = str(detail.get("code") or f"HTTP_{status}")
            message = str(detail.get("message") or code)
            retryable = bool(detail.get("retryable", False))
            nested = detail.get("details")
            if isinstance(nested, Mapping):
                details = dict(nested)
            # An ambiguous external mutation is deliberately not a transport retry.
            # It must be reconciled by its stable provider identity before another send.
            if code == "execution_outcome_uncertain":
                retryable = False
        else:
            code = f"HTTP_{status}"
            message = str(detail or f"Operly request failed with HTTP {status}")
            retryable = status >= 500
        error_type = DragonZpyderAuthError if status == 401 else DragonZpyderClientError
        return error_type(
            message,
            code=code,
            status=status,
            retryable=retryable,
            details=details,
        )

    def request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        csrf: bool = False,
        authenticated: bool = False,
    ) -> ClientResponse:
        normalized_method = method.strip().upper()
        if not path.startswith("/api/"):
            raise DragonZpyderClientError(
                "DragonZpyder only calls Operly API paths.",
                code="INVALID_API_PATH",
            )
        url = self.config.operly_base_url + path
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "DragonZpyder/0.1",
        }
        if payload is not None:
            body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if csrf:
            token = self._csrf_token(preauth=not authenticated)
            if not token:
                if authenticated:
                    self.clear()
                    raise DragonZpyderAuthError(
                        "Your saved Operly session is incomplete. Sign in again.",
                        code="SESSION_INVALID",
                        status=401,
                    )
                raise DragonZpyderClientError(
                    "Operly did not issue a pre-authentication CSRF token.",
                    code="CSRF_BOOTSTRAP_FAILED",
                )
            headers["X-CSRF-Token"] = token

        request = Request(
            url,
            data=body,
            headers=headers,
            method=normalized_method,
        )
        try:
            with self.opener.open(
                request,
                timeout=self.config.request_timeout_seconds,
            ) as response:
                response_payload = self._decode_payload(response.read())
                self._save()
                return ClientResponse(status=int(response.status), payload=response_payload)
        except HTTPError as exc:
            raw = exc.read()
            try:
                response_payload = self._decode_payload(raw)
            except DragonZpyderClientError:
                response_payload = {}
            if authenticated and exc.code == 401:
                self.clear()
            raise self._detail(response_payload, int(exc.code)) from exc
        except URLError as exc:
            raise DragonZpyderClientError(
                f"Could not reach Operly: {exc.reason}",
                code="OPERLY_UNREACHABLE",
                retryable=True,
            ) from exc
        except TimeoutError as exc:
            raise DragonZpyderClientError(
                "Operly request timed out. Reuse the same request ID before retrying a submission.",
                code="OPERLY_TIMEOUT",
                retryable=True,
            ) from exc


class DragonZpyderClient:
    """Thin Personal client. Operly remains the authority and execution boundary."""

    def __init__(
        self,
        config: DragonZpyderConfig,
        *,
        transport: ClientTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or CookieSessionTransport(config)

    def login(self, *, email: str, password: str) -> Mapping[str, Any]:
        clean_email = str(email or "").strip()
        if not clean_email or not password:
            raise DragonZpyderClientError(
                "Email and password are required.",
                code="LOGIN_INPUT_REQUIRED",
            )
        self.transport.request_json("GET", "/api/auth/bootstrap")
        login = self.transport.request_json(
            "POST",
            "/api/auth/login",
            {"email": clean_email, "password": password},
            csrf=True,
            authenticated=False,
        ).payload
        if not isinstance(login, Mapping):
            raise DragonZpyderClientError(
                "Operly login returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        scope = str(login.get("scope") or "")
        if scope != "personal":
            personal = self.transport.request_json(
                "POST",
                "/api/auth/personal-scope",
                {},
                csrf=True,
                authenticated=True,
            ).payload
            if not isinstance(personal, Mapping) or personal.get("scope") != "personal":
                raise DragonZpyderClientError(
                    "Operly could not issue a Personal-only session.",
                    code="PERSONAL_SCOPE_REQUIRED",
                )
        current = self.status()
        if current.get("scope") != "personal":
            raise DragonZpyderClientError(
                "The active Operly session is not Personal-only.",
                code="PERSONAL_SCOPE_REQUIRED",
            )
        return current

    def status(self) -> Mapping[str, Any]:
        payload = self.transport.request_json(
            "GET",
            "/api/auth/sessions",
            authenticated=True,
        ).payload
        if not isinstance(payload, list):
            raise DragonZpyderClientError(
                "Operly session status returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        for row in payload:
            if isinstance(row, Mapping) and row.get("current"):
                return row
        raise DragonZpyderAuthError(
            "No active Operly session is available. Sign in again.",
            code="SESSION_INVALID",
            status=401,
        )

    def logout(self) -> None:
        try:
            self.transport.request_json(
                "POST",
                "/api/auth/logout",
                {},
                csrf=True,
                authenticated=True,
            )
        except DragonZpyderAuthError:
            # A server-side expired/revoked session is already logged out. Always
            # remove the local cookie material as the final logout step.
            pass
        finally:
            self.transport.clear()

    def submit(
        self,
        message: str,
        *,
        conversation_id: str | None = None,
        request_id: str | None = None,
    ) -> Mapping[str, Any]:
        clean_message = str(message or "").strip()
        if not clean_message:
            raise DragonZpyderClientError(
                "Task text is required.",
                code="TASK_REQUIRED",
            )
        stable_request_id = str(request_id or uuid4()).strip()
        payload: dict[str, Any] = {
            "message": clean_message,
            "request_id": stable_request_id,
        }
        if conversation_id:
            payload["conversation_id"] = str(conversation_id).strip()
        result = self.transport.request_json(
            "POST",
            "/api/personal-tools/client/submit",
            payload,
            csrf=True,
            authenticated=True,
        ).payload
        if not isinstance(result, Mapping):
            raise DragonZpyderClientError(
                "Operly task submission returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        return result

    def approvals(self, *, status: str | None = None) -> tuple[Mapping[str, Any], ...]:
        path = "/api/personal-tools/approvals"
        if status:
            path += "?status=" + quote(str(status).strip(), safe="")
        payload = self.transport.request_json("GET", path, authenticated=True).payload
        rows = payload.get("approvals") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            raise DragonZpyderClientError(
                "Operly approval status returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        return tuple(row for row in rows if isinstance(row, Mapping))

    def pending_approvals(self) -> tuple[Mapping[str, Any], ...]:
        return self.approvals(status="pending")

    def _approval(self, approval_id: str) -> Mapping[str, Any]:
        clean_id = str(approval_id or "").strip()
        for row in self.approvals():
            if str(row.get("id") or "") == clean_id:
                return row
        raise DragonZpyderClientError(
            "That Personal approval is not available in this account.",
            code="APPROVAL_NOT_FOUND",
        )

    def decide_approval(self, approval_id: str, *, approved: bool) -> Mapping[str, Any]:
        clean_id = str(approval_id or "").strip()
        if not clean_id:
            raise DragonZpyderClientError(
                "Approval ID is required.",
                code="APPROVAL_ID_REQUIRED",
            )
        result = self.transport.request_json(
            "POST",
            f"/api/personal-tools/approvals/{clean_id}/decision",
            {"approved": bool(approved)},
            csrf=True,
            authenticated=True,
        ).payload
        if not isinstance(result, Mapping):
            raise DragonZpyderClientError(
                "Operly approval decision returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        return result

    def execute_approved(self, approval: Mapping[str, Any]) -> Mapping[str, Any]:
        if str(approval.get("status") or "") != "approved":
            raise DragonZpyderClientError(
                "Only an approved Personal action can be resumed.",
                code="APPROVAL_NOT_EXECUTABLE",
            )
        capability_id = str(approval.get("capability_id") or "").strip()
        request_id = str(approval.get("request_id") or "").strip()
        approval_id = str(approval.get("id") or "").strip()
        arguments = approval.get("arguments")
        if not capability_id or not request_id or not approval_id or not isinstance(arguments, Mapping):
            raise DragonZpyderClientError(
                "The approved action is missing its bound execution contract.",
                code="APPROVAL_CONTRACT_INVALID",
            )
        payload: dict[str, Any] = {
            "goal": "",
            "arguments": dict(arguments),
            "request_id": request_id,
            "approval_id": approval_id,
        }
        if approval.get("conversation_id"):
            payload["conversation_id"] = str(approval["conversation_id"])
        result = self.transport.request_json(
            "POST",
            f"/api/personal-tools/{quote(capability_id, safe='')}/execute",
            payload,
            csrf=True,
            authenticated=True,
        ).payload
        if not isinstance(result, Mapping):
            raise DragonZpyderClientError(
                "Operly approved action returned an invalid response.",
                code="INVALID_SERVER_RESPONSE",
            )
        return result

    def approve_and_execute(self, approval_id: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        approved = self.decide_approval(approval_id, approved=True)
        return approved, self.execute_approved(approved)

    def resume_approved(self, approval_id: str) -> Mapping[str, Any]:
        return self.execute_approved(self._approval(approval_id))
