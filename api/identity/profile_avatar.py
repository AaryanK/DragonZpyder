"""Optional, non-authoritative Google profile metadata and bounded image readback.

Only a verified, already-linked Google proof can refresh the avatar. The
client never submits an image URL. A separately reviewed SQL migration and
feature flag are required; the normal authentication path remains unchanged.
"""
import asyncio
import os
import re
from urllib.parse import urlsplit

import asyncpg
import httpx

MAX_AVATAR_BYTES = 256 * 1024
ALLOWED_HOST = "lh3.googleusercontent.com"


def avatar_enabled() -> bool:
    return os.getenv("DRAGONZPYDER_IDENTITY_PROFILE_AVATAR_ENABLED") == "1"


def verified_avatar_url(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return None
    # Only Google's canonical HTTPS picture host and opaque ASCII paths.
    # No userinfo, port, query, fragment, path traversal or URL rewriting.
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.netloc != ALLOWED_HOST
                or parts.query or parts.fragment
                or not re.fullmatch(r"/(?:a|a-)/[A-Za-z0-9_./=+-]+", parts.path)
                or any(p in (".", "..") for p in parts.path.split("/"))):
            return None
    except ValueError:
        return None
    return value if value == f"https://{ALLOWED_HOST}{parts.path}" else None


async def save_google_avatar(db, subject, proof):
    if not avatar_enabled() or proof.provider != "google":
        return
    picture = verified_avatar_url(proof.profile_picture)
    try:
        await db.execute(
            """UPDATE identity_accounts AS a SET google_avatar_url=$1
               WHERE a.subject=$2 AND a.status='active' AND a.source_active=TRUE
               AND EXISTS (SELECT 1 FROM identity_provider_links p
                           WHERE p.subject=a.subject AND p.provider='google'
                           AND p.provider_subject=$3 AND p.source='auth'
                           AND p.login_eligible=TRUE)""",
            picture, subject, proof.provider_subject)
    except asyncpg.PostgresError:
        # Optional profile metadata must not break a verified login if its
        # migration/permission is unavailable. No secrets or URLs are logged.
        return


async def read_google_avatar(db, subject):
    if not avatar_enabled():
        return None
    try:
        value = await db.fetchval(
            """SELECT a.google_avatar_url FROM identity_accounts a
               WHERE a.subject=$1 AND a.status='active' AND a.source_active=TRUE
               AND EXISTS (SELECT 1 FROM identity_provider_links p
                           WHERE p.subject=a.subject AND p.provider='google'
                           AND p.source='auth' AND p.login_eligible=TRUE)""", subject)
    except asyncpg.PostgresError:
        return None
    return verified_avatar_url(value)


def image_matches(mime, data):
    return ((mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
            or (mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
            or (mime == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))


async def fetch_google_avatar(client, url):
    """No redirects, authentication headers, cookies or arbitrary destination."""
    url = verified_avatar_url(url)
    if not url:
        return None
    try:
        async with asyncio.timeout(6):
            async with client.stream("GET", url, follow_redirects=False,
                    headers={"Accept": "image/jpeg,image/png,image/webp",
                             "Accept-Encoding": "identity"}) as response:
                if response.status_code != 200:
                    return None
                mime = response.headers.get("content-type", "").split(";")[0].lower()
                if mime not in {"image/jpeg", "image/png", "image/webp"}:
                    return None
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    return None
                length = response.headers.get("content-length")
                if length is not None and (not length.isdecimal() or int(length) > MAX_AVATAR_BYTES):
                    return None
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_AVATAR_BYTES:
                        return None
                raw = bytes(data)
                return (mime, raw) if image_matches(mime, raw) else None
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None
