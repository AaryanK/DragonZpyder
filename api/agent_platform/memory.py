"""Opt-in Mem0 memory backed by a separately provisioned pgvector database.

Memory extraction/storage requires user consent in the calling product.
No automatic saving from conversations, tools or workspace contexts.
"""
from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlsplit


def memory_config() -> dict:
    dsn = os.getenv("DRAGONZPYDER_MEMORY_DATABASE_URL", "")
    parsed = urlsplit(dsn)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise RuntimeError("Mem0 requires a PostgreSQL DSN")
    llm_key = os.getenv("OPENROUTER_API_KEY", "")
    embeddings_key = os.getenv("DRAGONZPYDER_EMBEDDING_API_KEY", "")
    if not llm_key or not embeddings_key:
        raise RuntimeError("Mem0 requires explicit LLM and embedding API keys")
    llm_model = os.getenv("DRAGONZPYDER_MEM0_LLM_MODEL", "").strip()
    embed_model = os.getenv("DRAGONZPYDER_MEM0_EMBED_MODEL", "").strip()
    dims_raw = os.getenv("DRAGONZPYDER_EMBEDDING_DIMENSIONS", "").strip()
    if not llm_model or not embed_model or not dims_raw.isdigit():
        raise RuntimeError("Configure memory extraction model, embedding model and dimensions")
    dims = int(dims_raw)
    if not 1 <= dims <= 8192:
        raise RuntimeError("Invalid embedding dimensions")
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "api_key": llm_key,
                "openai_base_url": "https://openrouter.ai/api/v1",
                "temperature": 0,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_model,
                "api_key": embeddings_key,
                # Embeddings provider may differ from OpenRouter on purpose.
                "openai_base_url": os.getenv(
                    "DRAGONZPYDER_EMBEDDING_BASE_URL",
                    "https://api.openai.com/v1",
                ),
            },
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "user": unquote(parsed.username or ""),
                "password": unquote(parsed.password or ""),
                "dbname": parsed.path.lstrip("/") or "postgres",
                "collection_name": "dragonzpyder_personal_memories",
                "embedding_model_dims": dims,
            },
        },
    }


class PersonalMemory:
    """Caller supplies a verified DragonZpyder ID and explicit consent."""
    def __init__(self):
        from mem0 import Memory
        self._memory = Memory.from_config(memory_config())

    @staticmethod
    def _principal(user_id: str) -> str:
        if not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,120}", user_id):
            raise ValueError("Invalid stable user ID")
        return "dz:" + user_id

    def remember(self, *, user_id: str, text: str, consent: bool):
        if not consent:
            raise PermissionError("Persistent memory requires explicit consent")
        if not text or len(text) > 8000:
            raise ValueError("Invalid memory text")
        return self._memory.add(text, user_id=self._principal(user_id))

    def search(self, *, user_id: str, query: str):
        if not query or len(query) > 4000:
            raise ValueError("Invalid memory query")
        return self._memory.search(query, user_id=self._principal(user_id))

    def delete_user(self, *, user_id: str):
        return self._memory.delete_all(user_id=self._principal(user_id))
