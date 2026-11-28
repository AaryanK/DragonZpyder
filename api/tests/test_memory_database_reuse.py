"""No-network memory reuse contract: no new database without review."""
import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_platform.memory import memory_config

DATA = {
    "DRAGONZPYDER_AGENT_DATABASE_URL": "postgresql://worker:synthetic@localhost:5432/agent_memory",
    "OPENROUTER_API_KEY": "synthetic-model-key",
    "DRAGONZPYDER_EMBEDDING_API_KEY": "synthetic-embed-key",
    "DRAGONZPYDER_MEM0_LLM_MODEL": "sample-model",
    "DRAGONZPYDER_MEM0_EMBED_MODEL": "sample-embed",
    "DRAGONZPYDER_EMBEDDING_DIMENSIONS": "1536",
}

def test_no_implicit_memory_database():
    with patch.dict(os.environ, DATA, clear=True):
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            memory_config()

def test_reuse_requires_explicit_operator_approval():
    with patch.dict(os.environ, {**DATA, "DRAGONZPYDER_MEM0_USE_AGENT_DATABASE": "1"}, clear=True):
        with pytest.raises(RuntimeError, match="operator approval"):
            memory_config()

def test_approved_existing_database_reuse():
    with patch.dict(os.environ, {**DATA, "DRAGONZPYDER_MEM0_USE_AGENT_DATABASE": "1",
                                  "DRAGONZPYDER_MEM0_AGENT_DB_APPROVED": "1"}, clear=True):
        result = memory_config()
    assert result["vector_store"]["config"]["dbname"] == "agent_memory"
    assert result["vector_store"]["config"]["embedding_model_dims"] == 1536

def test_ambiguous_database_config_rejected():
    with patch.dict(os.environ, {**DATA, "DRAGONZPYDER_MEM0_USE_AGENT_DATABASE": "1",
                                  "DRAGONZPYDER_MEM0_AGENT_DB_APPROVED": "1",
                                  "DRAGONZPYDER_MEMORY_DATABASE_URL": DATA["DRAGONZPYDER_AGENT_DATABASE_URL"]}, clear=True):
        with pytest.raises(RuntimeError, match="Ambiguous"):
            memory_config()


def test_native_memory_rejects_unconsented_save_without_db():
    import asyncio
    from uuid import uuid4
    from agent_platform.memory import save_native_memory
    with pytest.raises(PermissionError):
        asyncio.run(save_native_memory(None,owner="synthetic",memory_id=uuid4(),content="fact",consent=False,recall_in_chat=True))


def test_native_memory_search_binds_owner_and_consent_and_delete():
    import asyncio
    from uuid import uuid4
    from agent_platform.memory import search_native_memory,delete_native_memory
    class Db:
        async def fetch(self,sql,*args):
            assert "owner_id=$1 AND recall_in_chat" in sql and "LIMIT 5" in sql
            assert args==("owner-a","example")
            return []
        async def fetchval(self,sql,*args):
            assert "owner_id=$1 AND id=$2" in sql and args[0]=="owner-a"
            return None
    async def run():
        assert await search_native_memory(Db(),owner="owner-a",query=" example ")==[]
        assert await delete_native_memory(Db(),owner="owner-a",memory_id=uuid4()) is False
        with pytest.raises(ValueError):
            await search_native_memory(Db(),owner="owner-a",query="")
    asyncio.run(run())


def test_native_memory_tool_requires_live_authority_before_read():
    import asyncio
    from agent_platform.memory import native_memory_tools
    async def denied():raise PermissionError("revoked")
    tool=native_memory_tools(owner="owner-a",db_factory=None,authorize=denied)[0]
    with pytest.raises(PermissionError):
        asyncio.run(tool.ainvoke({"query":"example"}))
