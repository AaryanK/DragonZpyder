"""Hash-compatibility tests using synthetic credentials only."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identity.passwords import hash_password, legacy_hash_password, verify_and_update_password, normalize_email, validate_password, PasswordPolicyError


def test_argon2_login_parity():
    stored = hash_password("An Example Password 2026!")
    assert verify_and_update_password("An Example Password 2026!", stored).valid
    assert not verify_and_update_password("incorrect", stored).valid
    assert verify_and_update_password("An Example Password 2026!", stored).upgraded_hash is None


def test_legacy_pbkdf2_upgrade():
    old = legacy_hash_password("An Example Password 2026!")
    result = verify_and_update_password("An Example Password 2026!", old)
    assert result.valid and result.upgraded_hash.startswith("$argon2id$")
    assert verify_and_update_password("An Example Password 2026!", result.upgraded_hash).valid
    assert not verify_and_update_password("incorrect", old).valid


def test_reject_invalid_and_expensive_legacy_hash():
    import base64
    salt = base64.urlsafe_b64encode(b"x" * 16).decode()
    digest = base64.urlsafe_b64encode(b"x" * 32).decode()
    assert not verify_and_update_password("anything", f"pbkdf2_sha256$999999999$${salt}$${digest}").valid
    assert not verify_and_update_password("anything", "pbkdf2_sha256$invalid").valid


def test_policy_compatibility():
    assert normalize_email("Person@Example.COM") == "person@example.com"
    try:
        validate_password("password1234")
    except PasswordPolicyError:
        pass
    else:
        raise AssertionError("common password accepted")
