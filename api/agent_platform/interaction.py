"""Versioned interaction envelope; no transport, credentials or execution authority.

Binary content is represented by existing owner-scoped artifact IDs. The
canonical chat boundary remains responsible for authorization and execution.
"""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextPart(Contract):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=12000)


class ArtifactPart(Contract):
    kind: Literal["file", "image", "audio", "video"]
    artifact_id: UUID


ContentPart = Annotated[TextPart | ArtifactPart, Field(discriminator="kind")]


class InteractionInput(Contract):
    version: Literal["1"] = "1"
    request_id: UUID
    conversation_id: UUID | None = None
    content: list[ContentPart] = Field(min_length=1, max_length=6)
    mcp_connection_ids: list[str] = Field(default_factory=list, max_length=10)
    allow_computer: bool = Field(default=False, strict=True)
    allow_media: bool = Field(default=False, strict=True)
    allow_durable: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def validate_content(self):
        text = "\n".join(p.text for p in self.content if isinstance(p, TextPart))
        ids = [p.artifact_id for p in self.content if isinstance(p, ArtifactPart)]
        if not text.strip() or len(text) > 12000:
            raise ValueError("A nonblank objective of at most 12000 characters is required")
        if len(ids) > 5 or len(ids) != len(set(ids)):
            raise ValueError("At most five distinct artifacts are permitted")
        return self

    def chat_fields(self):
        """Normalize without granting authority or trusting declared media types."""
        return dict(message="\n".join(p.text for p in self.content if isinstance(p, TextPart)),
                    attachment_ids=[p.artifact_id for p in self.content if isinstance(p, ArtifactPart)],
                    request_id=self.request_id, conversation_id=self.conversation_id,
                    mcp_connection_ids=self.mcp_connection_ids,
                    allow_computer=self.allow_computer, allow_media=self.allow_media,
                    allow_durable=self.allow_durable)
