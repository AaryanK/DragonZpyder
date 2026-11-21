"""Native, bounded Personal document factory with durable user-owned artifacts.

This is a document renderer, NOT an OS sandbox or arbitrary Python interpreter.
Only a first-party signed Personal run may create or inspect artifacts. Downloads
use a short-lived, artifact-specific bearer URL; it never grants tool authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import escape
from io import BytesIO
import hmac
import os
import re
import time
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

import asyncpg
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from langchain_core.tools import tool

router = APIRouter(tags=["personal-artifacts"])
KINDS = {
    "pdf": ("application/pdf", ".pdf"),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS dz_personal_artifacts (
    artifact_id text PRIMARY KEY,
    user_id text NOT NULL,
    conversation_id text NOT NULL,
    format text NOT NULL,
    title text NOT NULL,
    filename text NOT NULL,
    media_type text NOT NULL,
    content bytea NOT NULL,
    content_sha256 char(64) NOT NULL,
    size_bytes integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS dz_personal_artifacts_owner
    ON dz_personal_artifacts (user_id, conversation_id, created_at DESC);
"""
ARTIFACT_TTL = timedelta(days=7)
URL_TTL_SECONDS = 900
MAX_BYTES = 4_000_000
MAX_SECTIONS = 14


def _canonical(value: str) -> str:
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Signed Personal identity must be a canonical UUID") from None
    if value != canonical:
        raise ValueError("Signed Personal identity must be a canonical UUID")
    return canonical


def _gate() -> tuple[str, bytes, str]:
    if os.getenv("DRAGONZPYDER_PERSONAL_ARTIFACTS_ENABLED") != "1":
        raise RuntimeError("Personal artifact factory is disabled")
    dsn = (os.getenv("DRAGONZPYDER_PERSONAL_MCP_DATABASE_URL")
           or os.getenv("DRAGONZPYDER_AGENT_DATABASE_URL", ""))
    secret = os.getenv("DRAGONZPYDER_ARTIFACT_DOWNLOAD_SIGNING_KEY", "")
    origin = os.getenv("DRAGONZPYDER_ARTIFACT_PUBLIC_ORIGIN", "")
    if not dsn.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("Artifact PostgreSQL is not configured")
    if len(secret) < 32:
        raise RuntimeError("Artifact download signing key not configured")
    if (not origin.startswith("https://") or "/" in origin[8:]
            or "@" in origin or "?" in origin or "#" in origin):
        raise RuntimeError("Artifact public HTTPS origin is not configured")
    return dsn, secret.encode("utf-8"), origin.rstrip("/")


def _normal_text(value, *, limit: int, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    value = value.strip()
    if not value or len(value) > limit or any(
        ord(c) < 32 and c not in "\n\t" for c in value
    ):
        raise ValueError(f"{label} is invalid or too long")
    return value


def validate_outline(title: str, sections: list[dict]) -> tuple[str, list[dict]]:
    title = _normal_text(title, limit=140, label="title")
    if (not isinstance(sections, list) or not 1 <= len(sections) <= MAX_SECTIONS):
        raise ValueError("Provide between 1 and 14 sections")
    cleaned = []
    size = len(title)
    for idx, section in enumerate(sections):
        if not isinstance(section, dict) or set(section) - {"heading", "body", "bullets"}:
            raise ValueError(f"Section {idx + 1} has unknown fields")
        heading = _normal_text(section.get("heading"), limit=130, label="heading")
        body = section.get("body") or ""
        if not isinstance(body, str) or len(body) > 2400:
            raise ValueError("Section body is too large")
        bullets = section.get("bullets", [])
        if (not isinstance(bullets, list) or len(bullets) > 8
                or any(not isinstance(x, str) or len(x) > 300 for x in bullets)):
            raise ValueError("Section bullets are invalid")
        body = body.strip()
        bullets = [x.strip() for x in bullets if x.strip()]
        if not body and not bullets:
            raise ValueError("Every section must contain body or bullets")
        size += len(heading) + len(body) + sum(len(x) for x in bullets)
        cleaned.append({"heading": heading, "body": body, "bullets": bullets})
    if size > 22000:
        raise ValueError("Document contents exceed the bounded renderer budget")
    return title, cleaned


def _pdf(title: str, sections: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(612, 792), rightMargin=49,
                            leftMargin=49, topMargin=57, bottomMargin=50,
                            title=title, author="DragonZpyder")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="DZTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                              textColor=colors.HexColor("#172339"), fontSize=23,
                              leading=29, spaceAfter=22, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="DZHeading", parent=styles["Heading2"],
                              textColor=colors.HexColor("#355B8C"), fontSize=13,
                              leading=17, spaceBefore=17, spaceAfter=8))
    styles.add(ParagraphStyle(name="DZBody", parent=styles["BodyText"],
                              fontSize=10.3, leading=15, spaceAfter=7))
    blocks = [Paragraph(escape(title), styles["DZTitle"]), Spacer(1, 6)]
    for item in sections:
        blocks.append(Paragraph(escape(item["heading"]), styles["DZHeading"]))
        if item["body"]:
            for paragraph in item["body"].split("\n"):
                if paragraph.strip():
                    blocks.append(Paragraph(escape(paragraph), styles["DZBody"]))
        for bullet in item["bullets"]:
            blocks.append(Paragraph("&#8226;&nbsp; " + escape(bullet), styles["DZBody"]))
    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#65758E"))
        canvas.drawString(49, 30, "DragonZpyder | Verified artifact")
        canvas.drawRightString(563, 30, str(document.page))
    doc.build(blocks, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


def _docx(title: str, sections: list[dict]) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    out = BytesIO()
    doc = Document()
    doc.core_properties.title = title
    doc.core_properties.author = "DragonZpyder"
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Inches(.8)
    sec.top_margin = sec.bottom_margin = Inches(.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    heading = doc.styles["Heading 1"]
    heading.font.name = "Aptos Display"
    heading.font.size = Pt(15)
    heading.font.color.rgb = RGBColor(42, 84, 127)
    doc.add_heading(title, level=0)
    for item in sections:
        doc.add_heading(item["heading"], level=1)
        if item["body"]:
            for p in item["body"].split("\n"):
                if p.strip():
                    doc.add_paragraph(p.strip())
        for bullet in item["bullets"]:
            doc.add_paragraph(bullet, style="List Bullet")
    footer = sec.footer.paragraphs[0]
    footer.text = "DragonZpyder | Verified artifact"
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _pptx(title: str, sections: list[dict]) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    bg = RGBColor(15, 23, 42)
    white = RGBColor(239, 245, 254)
    accent = RGBColor(126, 183, 248)
    secondary = RGBColor(185, 199, 218)

    def textbox(slide, x, y, w, h, content, pts, color, bold=False):
        frame = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
        frame.word_wrap = True
        frame.text = content
        for para in frame.paragraphs:
            para.font.name = "Aptos"
            para.font.size = Pt(pts)
            para.font.bold = bold
            para.font.color.rgb = color
        return frame

    def slide_base():
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = bg
        return slide

    first = slide_base()
    textbox(first, .9, 2.0, 11.6, 2.1, title, 39, white, True)
    textbox(first, .95, 6.65, 10, .35, "DRAGONZPYDER  /  ARTIFACT FACTORY", 12, accent)
    for number, item in enumerate(sections, 1):
        slide = slide_base()
        textbox(slide, .85, .62, 11.5, 1.2, item["heading"], 30, accent, True)
        body = "\n".join([item["body"], *("• " + x for x in item["bullets"])]).strip()
        # Reject content that could overflow a slide rather than silently cut it.
        if len(body) > 900 or body.count("\n") > 15:
            raise ValueError(f"Slide {number} is too dense; shorten it")
        body_pts = 21 if len(body) < 420 else 17
        textbox(slide, .92, 1.82, 11.5, 4.75, body, body_pts, white)
        textbox(slide, .94, 6.73, 10.2, .31,
                "DragonZpyder  •  " + str(number).zfill(2), 11, secondary)
    out = BytesIO()
    deck.save(out)
    return out.getvalue()


def render_artifact(kind: Literal["pdf", "docx", "pptx"], title: str,
                    sections: list[dict]) -> bytes:
    title, clean = validate_outline(title, sections)
    if kind not in KINDS:
        raise ValueError("Unsupported artifact format")
    content = {"pdf": _pdf, "docx": _docx, "pptx": _pptx}[kind](title, clean)
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Rendered artifact exceeds the 4 MB limit")
    verify_artifact(kind, content, title, len(clean))
    return content


def verify_artifact(kind: str, content: bytes, title: str, sections: int) -> None:
    """Reopen the actual bytes, not the tool's asserted success."""
    if kind == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not reader.pages or title not in text:
            raise ValueError("PDF readback failed")
    elif kind == "docx":
        from docx import Document
        doc = Document(BytesIO(content))
        if title not in "\n".join(p.text for p in doc.paragraphs):
            raise ValueError("DOCX readback failed")
    elif kind == "pptx":
        from pptx import Presentation
        deck = Presentation(BytesIO(content))
        if len(deck.slides) != sections + 1:
            raise ValueError("PPTX slide-count readback failed")
        first = " ".join(shape.text for shape in deck.slides[0].shapes
                         if shape.has_text_frame)
        if title not in first:
            raise ValueError("PPTX title readback failed")
    else:
        raise ValueError("Unsupported format")


def _download_url(artifact_id: str, owner: str, content_hash: str,
                  secret: bytes, origin: str, expiry: int) -> str:
    signed = f"dz-artifact-v1:{artifact_id}:{owner}:{content_hash}:{expiry}".encode()
    signature = hmac.new(secret, signed, "sha256").hexdigest()
    return f"{origin}/artifacts/{artifact_id}/download?exp={expiry}&sig={signature}"


async def _pool():
    dsn, _, _ = _gate()
    return await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2,
                                     timeout=10, command_timeout=35)


def personal_artifact_tools(*, user_id: str, conversation_id: str):
    """Generate tools bound to the trusted signed Personal invocation."""
    user_id, conversation_id = _canonical(user_id), _canonical(conversation_id)

    @tool("artifact_create")
    async def artifact_create(format: Literal["pdf", "docx", "pptx"],
                              title: str, sections: list[dict]) -> dict:
        """Create and verify an actual downloadable PDF, DOCX, or PowerPoint.

        Provide between one and fourteen sections, each shaped as
        {"heading": str, "body": str, "bullets": [str,...]}. For PowerPoints
        keep each section slide-sized. No code execution or third-party writes.
        Return the verified, expiring download URL to the user.
        """
        try:
            dsn, secret, origin = _gate()
            title, clean = validate_outline(title, sections)
            content = render_artifact(format, title, clean)
        except (ValueError, RuntimeError) as error:
            return {"status": "rejected", "reason": str(error)[:180]}
        artifact_id = str(uuid4())
        digest = sha256(content).hexdigest()
        expiry = datetime.now(timezone.utc) + ARTIFACT_TTL
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", title).strip("-")[:60] or "report"
        filename = safe_name + KINDS[format][1]
        pool = await _pool()
        try:
            async with pool.acquire() as con:
                if os.getenv("DRAGONZPYDER_ARTIFACT_SCHEMA_INSTALL_ALLOWED") == "1":
                    await con.execute(SCHEMA)
                async with con.transaction():
                    await con.execute("SELECT pg_advisory_xact_lock(hashtext($1))", user_id)
                    # Limit creation volume as well as individual file size.
                    count = await con.fetchval(
                        """SELECT count(*) FROM dz_personal_artifacts
                           WHERE user_id=$1 AND created_at > now() - interval '1 day'""",
                        user_id,
                    )
                    if count >= 12:
                        return {"status": "rejected", "reason": "daily_artifact_limit"}
                    await con.execute(
                        """INSERT INTO dz_personal_artifacts
                           (artifact_id,user_id,conversation_id,format,title,filename,
                            media_type,content,content_sha256,size_bytes,expires_at)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                        artifact_id,user_id,conversation_id,format,title,filename,
                        KINDS[format][0],content,digest,len(content),expiry,
                    )
                    readback = await con.fetchrow(
                        """SELECT content,content_sha256 FROM dz_personal_artifacts
                           WHERE artifact_id=$1 AND user_id=$2""",
                        artifact_id,user_id,
                    )
                    if (readback is None or
                            sha256(bytes(readback["content"])).hexdigest() != digest or
                            readback["content_sha256"] != digest):
                        raise RuntimeError("Durable artifact readback did not match")
        finally:
            await pool.close()
        url = _download_url(artifact_id,user_id,digest,secret,origin,
                            int(time.time())+URL_TTL_SECONDS)
        return {"status":"completed","verified":True,"artifact_id":artifact_id,
                "format":format,"filename":filename,"size_bytes":len(content),
                "sha256":digest,"download_url":url,
                "download_expires_in_seconds":URL_TTL_SECONDS,
                "stored_until_utc":expiry.isoformat()}

    @tool("artifact_status")
    async def artifact_status(artifact_id: str) -> dict:
        """Verify your previously generated Personal artifact and renew its download link.

        Only artifacts belonging to the signed-in user AND this conversation
        are accessible. Does not create a duplicate artifact.
        """
        try:
            _canonical(artifact_id)
        except ValueError:
            return {"status":"not_found"}
        _,secret,origin = _gate()
        pool = await _pool()
        try:
            async with pool.acquire() as con:
                row = await con.fetchrow(
                    """SELECT * FROM dz_personal_artifacts
                       WHERE artifact_id=$1 AND user_id=$2 AND conversation_id=$3
                         AND expires_at > now()""",
                    artifact_id,user_id,conversation_id,
                )
                if row is None:
                    return {"status":"not_found"}
                digest = sha256(bytes(row["content"])).hexdigest()
                if digest != row["content_sha256"]:
                    return {"status":"corrupted","verified":False}
                url = _download_url(artifact_id,user_id,digest,secret,origin,
                                    int(time.time())+URL_TTL_SECONDS)
                return {"status":"completed","verified":True,
                        "artifact_id":artifact_id,"filename":row["filename"],
                        "format":row["format"],"size_bytes":row["size_bytes"],
                        "sha256":digest,"download_url":url,
                        "download_expires_in_seconds":URL_TTL_SECONDS}
        finally:
            await pool.close()

    return [artifact_create, artifact_status]


@router.get("/artifacts/{artifact_id}/download")
async def download_personal_artifact(artifact_id: str, exp: str = "",
                                     sig: str = ""):
    """Single-artifact, short-lived bearer URL. No Operly session is exposed."""
    try:
        _canonical(artifact_id)
        expiry = int(exp)
        if (expiry < time.time() or expiry > time.time() + URL_TTL_SECONDS+30
                or not re.fullmatch(r"[a-f0-9]{64}", sig)):
            raise ValueError("Invalid or expired download token")
        _,secret,_ = _gate()
    except (ValueError, RuntimeError):
        raise HTTPException(404, "Artifact link unavailable") from None
    pool = await _pool()
    try:
        async with pool.acquire() as con:
            row = await con.fetchrow(
                """SELECT user_id,filename,media_type,content,content_sha256
                   FROM dz_personal_artifacts
                   WHERE artifact_id=$1 AND expires_at > now()""",
                artifact_id,
            )
            if row is None:
                raise HTTPException(404, "Artifact unavailable")
            expected = hmac.new(
                secret,
                f"dz-artifact-v1:{artifact_id}:{row['user_id']}:{row['content_sha256']}:{expiry}".encode(),
                "sha256",
            ).hexdigest()
            if not hmac.compare_digest(expected, sig):
                raise HTTPException(404, "Artifact unavailable")
            content = bytes(row["content"])
            if sha256(content).hexdigest() != row["content_sha256"]:
                raise HTTPException(503, "Artifact integrity check failed")
            name = row["filename"].replace('"', "")
            return Response(content=content, media_type=row["media_type"],
                            headers={"Content-Disposition":f'attachment; filename="{name}"',
                                     "Cache-Control":"private, no-store",
                                     "X-Content-Type-Options":"nosniff"})
    finally:
        await pool.close()
