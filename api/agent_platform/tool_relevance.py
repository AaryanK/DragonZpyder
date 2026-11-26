"""Deterministic, authorization-scoped candidate retrieval for MCP tools.

No model calls, network requests, or permissions are inferred here. Keep
generic catalog discovery as a fallback. This is a high-precision shortlist
for direct binding, not an intent classifier or authorization decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_STOP = frozenset({
    "a", "an", "the", "i", "me", "my", "our", "your", "please", "can", "could",
    "would", "should", "to", "of", "in", "on", "for", "from", "with", "and",
    "or", "is", "are", "what", "all", "this", "that", "now", "do", "you",
})
_GENERIC = frozenset({"list", "read", "get", "search", "find", "show", "fetch",
                      "lookup", "query", "view", "retrieve", "status", "record",
                      "data", "item", "info", "tool", "details"})
_MUTATION = frozenset({"create", "delete", "remove", "update", "modify", "change",
                       "send", "publish", "write", "buy", "cancel", "approve",
                       "schedule", "execute", "run", "deploy", "transfer"})


def terms(value: str) -> frozenset[str]:
    # Split snake/dotted/kebab and camel/Pascal names before lowercasing.
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value[:12000])
    value = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", value)
    words = re.findall(r"[a-z0-9]+", value.lower())
    def singular(word: str) -> str:
        if len(word) > 4 and word.endswith("ies"):
            return word[:-3] + "y"
        if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
            return word[:-1]
        return word
    return frozenset(singular(w) for w in words if w not in _STOP)


@dataclass(frozen=True)
class Candidate:
    provider_id: str
    tool_name: str
    score: int
    substantive_overlap: int


def rank_candidates(query: str, entries: Iterable[tuple[str, str, Iterable[str]]]) -> list[Candidate]:
    query_terms = terms(query)
    ranked = []
    for provider_id, description, capabilities in entries:
        provider_words = terms(provider_id + " " + description[:500])
        for capability in capabilities:
            words = terms(capability)
            overlap = words & query_terms
            substantive = len(overlap - _GENERIC)
            score = 5 * substantive + 2 * len(overlap & _GENERIC) + len(provider_words & query_terms)
            if score:
                ranked.append(Candidate(provider_id, capability, score, substantive))
    return sorted(ranked, key=lambda c: (-c.score, c.provider_id, c.tool_name))


def direct_candidates(query: str, entries: Iterable[tuple[str, str, Iterable[str]]],
                      *, maximum: int = 3) -> list[Candidate]:
    if not isinstance(query, str) or not query.strip() or len(query) > 12000:
        return []
    if type(maximum) is not int or not 1 <= maximum <= 3:
        raise ValueError("Invalid direct binding limit")
    # Leave mutation or scheduled work to the full harness. The reviewed
    # read allowlist remains the actual security boundary.
    if terms(query) & _MUTATION:
        return []
    ranked = rank_candidates(query, entries)
    relevant = [c for c in ranked if c.substantive_overlap and c.score >= 5]
    # Never select an arbitrary account for the same capability if tied.
    if any(a.tool_name == b.tool_name and a.score == b.score
           and a.provider_id != b.provider_id
           for i, a in enumerate(relevant) for b in relevant[i + 1:]):
        return []
    return relevant[:maximum]
