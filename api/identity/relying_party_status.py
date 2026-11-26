"""Read-only issuer status for the explicitly configured Operly relying party.

Independent feature gate and dedicated server credential. This route is not
an agent tool or public account lookup. No email, password or session secret
is returned. Transport must be HTTPS and clients must not follow redirects.
"""
import hmac
import os
import re
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .http_bridge import _enabled, _identity_db
from .pending_proof_http import _payload

router = APIRouter(prefix="/identity/v1/relying-party",tags=["identity-relying-party"])


@router.post("/status",include_in_schema=False)
async def relying_party_status(request: Request):
    _enabled()
    if os.getenv("DRAGONZPYDER_OPERLY_STATUS_ENABLED")!="1":
        raise HTTPException(404,"Not found")
    expected=os.getenv("DRAGONZPYDER_OPERLY_STATUS_SECRET","")
    supplied=request.headers.get("authorization","")
    if len(expected)<43:
        raise HTTPException(503,"Status service unavailable")
    if not hmac.compare_digest(supplied.encode(),"Bearer ".encode()+expected.encode()):
        raise HTTPException(401,"Unauthorized")
    body=await _payload(request,{"subject":160})
    sid=body["subject"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}",sid):
        raise HTTPException(400,"Invalid status request")
    async with _identity_db() as db:
        row=await db.fetchrow("""
            SELECT a.status='active' AND a.source_active AS active,
                   (SELECT max(s.revoked_at) FROM identity_browser_sessions s
                    WHERE s.subject=a.subject) AS revoked_at
            FROM identity_accounts a WHERE a.subject=$1
        """,sid)
    active=bool(row and row["active"])
    revoked=row["revoked_at"] if row else None
    return JSONResponse({"active":active,"revoked_at":revoked.isoformat() if revoked else None},
                        headers={"Cache-Control":"no-store"})
