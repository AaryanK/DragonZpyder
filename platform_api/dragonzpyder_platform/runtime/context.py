from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Sequence


class ContextKind(StrEnum):
    CONVERSATION = "conversation"
    MEMORY = "memory"
    OBSERVATION = "observation"
    ARTIFACT = "artifact"
    USER_PROVIDED = "user_provided"


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_items: int = 6
    max_bytes: int = 12 * 1024
    max_item_bytes: int = 4 * 1024

    def __post_init__(self) -> None:
        if not 0 <= self.max_items <= 32:
            raise ValueError("max_items must be between 0 and 32")
        if self.max_bytes < 0 or self.max_item_bytes < 0:
            raise ValueError("context byte budgets cannot be negative")
        if self.max_items and (self.max_bytes == 0 or self.max_item_bytes == 0):
            raise ValueError("nonzero max_items requires positive byte budgets")


@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    kind: ContextKind
    text: str
    relevance: float = 0.0
    priority: int = 0

    def __post_init__(self) -> None:
        key = str(self.key or "").strip()
        text = " ".join(str(self.text or "").replace("\x00", " ").split())
        try:
            kind = ContextKind(str(self.kind))
        except ValueError as error:
            raise ValueError("context kind is unsupported") from error
        if not key or len(key) > 160:
            raise ValueError("context key must contain 1-160 characters")
        if not text:
            raise ValueError("context text is required")
        if not 0.0 <= float(self.relevance) <= 1.0:
            raise ValueError("context relevance must be between 0 and 1")
        if not 0 <= int(self.priority) <= 100:
            raise ValueError("context priority must be between 0 and 100")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "relevance", float(self.relevance))
        object.__setattr__(self, "priority", int(self.priority))

    def as_prompt_dict(self) -> dict[str, str]:
        # Internal keys deliberately do not flow to model prompts.
        return {"kind": self.kind.value, "text": self.text}


@dataclass(frozen=True, slots=True)
class ContextSlice:
    items: tuple[ContextItem, ...]
    total_bytes: int
    omitted_count: int

    def as_prompt_items(self) -> list[dict[str, str]]:
        return [item.as_prompt_dict() for item in self.items]


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").lower())
        if len(token) > 1
    }


class ContextAssembler:
    """Select a small relevance-bounded context slice for one inference phase.

    Upstream retrieval may offer many candidate memories, observations, conversation
    fragments or artifacts. This assembler never forwards the candidate set wholesale.
    It keeps only items that have explicit relevance/priority or lexical overlap with
    the current query, then applies per-item, item-count and total-byte budgets.
    """

    def select(
        self,
        query: str,
        items: Sequence[ContextItem],
        *,
        budget: ContextBudget | None = None,
    ) -> ContextSlice:
        effective_budget = budget or ContextBudget()
        if effective_budget.max_items == 0 or not items:
            return ContextSlice(items=(), total_bytes=0, omitted_count=len(items))

        query_tokens = _tokens(query)
        ranked: list[tuple[int, float, int, int, str, ContextItem]] = []
        omitted = 0

        for item in items:
            encoded = json.dumps(
                item.as_prompt_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            if len(encoded) > effective_budget.max_item_bytes:
                omitted += 1
                continue

            overlap = len(query_tokens & _tokens(item.text))
            if item.priority <= 0 and item.relevance <= 0.0 and overlap == 0:
                omitted += 1
                continue

            ranked.append(
                (item.priority, item.relevance, overlap, -len(encoded), item.key, item)
            )

        ranked.sort(key=lambda row: (-row[0], -row[1], -row[2], -row[3], row[4]))

        selected: list[ContextItem] = []
        total_bytes = 0
        for _, _, _, _, _, item in ranked:
            if len(selected) >= effective_budget.max_items:
                omitted += 1
                continue
            encoded = json.dumps(
                item.as_prompt_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            if total_bytes + len(encoded) > effective_budget.max_bytes:
                omitted += 1
                continue
            selected.append(item)
            total_bytes += len(encoded)

        return ContextSlice(
            items=tuple(selected),
            total_bytes=total_bytes,
            omitted_count=omitted,
        )
