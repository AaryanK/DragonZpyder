from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


class ConfigError(RuntimeError):
    """Raised when required DragonZpyder configuration is missing or unsafe."""


@dataclass(frozen=True)
class DragonZpyderConfig:
    operly_base_url: str
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "DragonZpyderConfig":
        base_url = os.getenv("DRAGONZPYDER_OPERLY_BASE_URL", "").strip()
        if not base_url:
            raise ConfigError(
                "DRAGONZPYDER_OPERLY_BASE_URL is required; copy .env.example and set the Operly endpoint."
            )

        parsed = urlparse(base_url)
        is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        allowed_schemes = {"http", "https"} if is_local else {"https"}
        if parsed.scheme not in allowed_schemes:
            raise ConfigError(
                "DRAGONZPYDER_OPERLY_BASE_URL must use https (http is allowed only for localhost)."
            )
        if not parsed.hostname:
            raise ConfigError("DRAGONZPYDER_OPERLY_BASE_URL must include a hostname.")

        timeout_raw = os.getenv("DRAGONZPYDER_REQUEST_TIMEOUT_SECONDS", "30").strip()
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ConfigError("DRAGONZPYDER_REQUEST_TIMEOUT_SECONDS must be numeric.") from exc
        if not 0 < timeout <= 120:
            raise ConfigError("DRAGONZPYDER_REQUEST_TIMEOUT_SECONDS must be > 0 and <= 120.")

        return cls(
            operly_base_url=base_url.rstrip("/"),
            request_timeout_seconds=timeout,
        )
