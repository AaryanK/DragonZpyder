"""Password/email compatibility ported from Operly (2026-11-21).
Pure functions only. No sessions, tokens or login routes are enabled.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


PBKDF2_ITERATIONS = 220_000
ARGON2_MEMORY_KIB = 19 * 1024
ARGON2_ITERATIONS = 2
ARGON2_LANES = 1
PASSWORD_MIN_BYTES = 12
PASSWORD_MAX_BYTES = 1024

COMMON_PASSWORDS = frozenset(
    line.strip().casefold()
    for line in Path(__file__).with_name("common_passwords.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
)

EMAIL_LOCAL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")


class PasswordPolicyError(ValueError):
    pass


class EmailAddressError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    valid: bool
    upgraded_hash: str | None = None


def normalize_email(value: str) -> str:
    if not isinstance(value, str):
        raise EmailAddressError("Enter a valid email address")
    email = value.strip()
    if not email or len(email) > 320 or "\x00" in email or email.count("@") != 1:
        raise EmailAddressError("Enter a valid email address")
    local, domain = email.rsplit("@", 1)
    if not local or len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise EmailAddressError("Enter a valid email address")
    if not EMAIL_LOCAL_RE.fullmatch(local):
        raise EmailAddressError("Enter a valid email address")
    try:
        ascii_domain = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise EmailAddressError("Enter a valid email address") from error
    labels = ascii_domain.split(".")
    if (
        not ascii_domain
        or len(ascii_domain) > 253
        or "." not in ascii_domain
        or any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels)
        or any(not re.fullmatch(r"[a-z0-9-]+", label) for label in labels)
    ):
        raise EmailAddressError("Enter a valid email address")
    return f"{local.lower()}@{ascii_domain}"


def validate_password(password: str, *, email: str | None = None) -> None:
    if not isinstance(password, str) or "\x00" in password:
        raise PasswordPolicyError("Choose a valid password")
    byte_length = len(password.encode("utf-8"))
    if byte_length < PASSWORD_MIN_BYTES:
        raise PasswordPolicyError("Use at least 12 characters")
    if byte_length > PASSWORD_MAX_BYTES:
        raise PasswordPolicyError("Password is too long")
    folded = password.casefold()
    compact = re.sub(r"[^a-z0-9]", "", folded)
    if folded in COMMON_PASSWORDS or compact in COMMON_PASSWORDS:
        raise PasswordPolicyError("Choose a less common password")
    if len(set(password)) < 4:
        raise PasswordPolicyError("Choose a less predictable password")
    if email:
        local = email.split("@", 1)[0].casefold()
        if len(local) >= 4 and local in folded:
            raise PasswordPolicyError("Password should not contain your email name")


def _argon2(salt: bytes) -> Argon2id:
    return Argon2id(
        salt=salt,
        length=32,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_KIB,
    )


def hash_password(password: str) -> str:
    return _argon2(secrets.token_bytes(16)).derive_phc_encoded(password.encode("utf-8"))


def legacy_hash_password(password: str) -> str:
    """Compatibility helper for legacy-user tests and controlled migrations."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{base64.urlsafe_b64encode(salt).decode()}$"
        f"{base64.urlsafe_b64encode(derived).decode()}"
    )


def _verify_pbkdf2(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_text, hash_text = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        count = int(iterations)
        if not 1 <= count <= 1_000_000:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(hash_text.encode())
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, count
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def verify_and_update_password(password: str, stored: str | None) -> PasswordVerification:
    if not stored or len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return PasswordVerification(False)
    if stored.startswith("$argon2id$"):
        try:
            Argon2id.verify_phc_encoded(password.encode("utf-8"), stored)
            return PasswordVerification(True)
        except (InvalidKey, ValueError):
            return PasswordVerification(False)
    if _verify_pbkdf2(password, stored):
        return PasswordVerification(True, hash_password(password))
    return PasswordVerification(False)


def verify_password(password: str, stored: str | None) -> bool:
    return verify_and_update_password(password, stored).valid

