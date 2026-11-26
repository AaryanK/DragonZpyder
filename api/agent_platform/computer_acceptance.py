"""Independent VM outcome acceptance for a bounded, operator-authorized run.

This is not an HTTP endpoint or automatic paid test. The trusted caller must
supply an already-budgeted gateway model, authorized ComputerRun, durable
checkpointer, and an independent authenticated artifact publication adapter.
This checks one critical release slice, not the 100-workflow release gate.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
from time import monotonic
from uuid import UUID, uuid4


def fixture():
    # Fresh case data defeats stale checkpoint/artifact credit. The oracle
    # computes the expected bytes locally, independently of the agent.
    from secrets import randbelow
    values = [randbelow(10000) for _ in range(9)]
    raw = json.dumps(values, separators=(",", ":"))
    expected = (str(sum(v * v for v in values)) + "\n").encode()
    return raw, expected


def verify_export(packet, *, path, expected):
    if (not isinstance(packet, dict) or packet.get("ok") is not True
            or packet.get("path") != path or type(packet.get("size_bytes")) is not int
            or packet["size_bytes"] != len(expected)):
        raise ValueError("Invalid exported artifact metadata")
    encoded = packet.get("content_base64")
    if not isinstance(encoded, str) or len(encoded) > 4096:
        raise ValueError("Invalid export bytes")
    data = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(data).hexdigest()
    if data != expected or packet.get("sha256") != digest:
        raise ValueError("Independent artifact oracle failed")
    return data, digest


async def verify_computer_objective(*, model, checkpointer, run, publish_and_readback):
    """One graph execution, independent VM export, durable publication/readback.

    publish_and_readback is trusted service code, never an agent tool. It must
    enforce authenticated owner/scope, save bytes as an immutable run artifact,
    independently read bytes back, and return (opaque ID, actual bytes).
    It must not simply echo input or mint a mock receipt in production.
    This function intentionally has no automatic live CLI or billing bypass.
    """
    from .computer_run import ComputerRun
    from .harness import build_frontier_agent
    from .runtime import summarize_agent_result
    if not isinstance(run, ComputerRun) or not callable(publish_and_readback):
        raise ValueError("Trusted computer and publication services required")
    case_id = uuid4().hex
    input_path, output_path = "input.json", "result.txt"
    raw, expected = fixture()
    prompt = (
        "Use the isolated computer tools, not the virtual filesystem. "
        f"Write {input_path} with exactly this JSON array: {raw}. "
        "Execute Python to load that file, calculate the sum of squares of the "
        f"integers, and write the decimal result plus a single newline to {output_path}. "
        "Read the output file and report the exact integer. Do not merely describe "
        "the steps or claim to have published a downloadable file."
    )
    config = {"configurable":{"thread_id":"sandbox-acceptance-"+case_id},
              "recursion_limit":128}
    result = {"case_id":case_id,"status":"incomplete","objective_verified":False,
              "graph_completed":False,"external_bytes_verified":False,
              "artifact_readback_verified":False,"checkpoint_verified":False,
              "cleanup_confirmed":False}
    started = monotonic()
    turn_id = uuid4().hex
    try:
        agent = build_frontier_agent(model,checkpointer,computer_run=run)
        state = await asyncio.wait_for(agent.ainvoke(
            {"messages":[{"role":"user","content":prompt,"id":turn_id}]},
            config=config),timeout=150)
        report = summarize_agent_result(state)
        required = {"computer_write_file","computer_python","computer_read_file"}
        if report["status"] != "completed" or not required <= set(report["successful_tools"]):
            raise ValueError("Required actual native operations missing")
        answer = report.get("answer", "")
        if not isinstance(answer,str) or not re.search(
                r"(?<![0-9])" + re.escape(expected.decode().strip()) + r"(?![0-9])", answer):
            raise ValueError("Final answer does not report the verified integer")
        result["graph_completed"] = True
        # A model-generated assertion or earlier file read is NOT the oracle.
        exported = await run.execute("artifact.export", {"path":output_path,"max_bytes":1024})
        data, digest = verify_export(exported,path=output_path,expected=expected)
        result["external_bytes_verified"] = True
        artifact_id, readback = await asyncio.wait_for(
            publish_and_readback(case_id,output_path,data),timeout=20)
        if not isinstance(artifact_id,str) or not artifact_id or type(readback) is not bytes or readback != data:
            raise ValueError("Authenticated artifact readback mismatch")
        result.update(artifact_readback_verified=True, artifact_id=artifact_id, artifact_sha256=digest)
        # New graph object, same checkpoint. This is reconstruction, not a
        # process restart test; the separate release recovery gate is required.
        reconstructed = build_frontier_agent(model,checkpointer)
        snapshot = await asyncio.wait_for(reconstructed.aget_state(config),timeout=10)
        messages = snapshot.values.get("messages",[])
        current = [i for i,m in enumerate(messages)
                   if getattr(m,"type",None)=="human" and getattr(m,"id",None)==turn_id]
        if len(current)!=1 or any(getattr(m,"type",None)=="human" for m in messages[current[0]+1:]):
            raise ValueError("Durable exact-turn checkpoint missing")
        result["checkpoint_verified"]=True
    except Exception as exc:
        # Report bounded taxonomy, not sensitive provider messages or prompts.
        result["failure_type"]=type(exc).__name__
    finally:
        result["cleanup_confirmed"] = await run.close()
        result["elapsed_ms"] = round((monotonic()-started)*1000)
    result["objective_verified"] = all(result[key] is True for key in (
        "graph_completed","external_bytes_verified","artifact_readback_verified",
        "checkpoint_verified","cleanup_confirmed"))
    result["status"] = "verified_slice" if result["objective_verified"] else "incomplete"
    return result


def artifact_publication_adapter(db_factory, *, owner):
    """Adapter for the reviewed shared-artifacts service (PR #142).

    Owner is fixed by authenticated operator/service context. The caller must
    bind it to the computer grant's principal and authorize publication.
    Separate DB leases ensure readback is an independent storage operation.
    Fails closed until shared-artifacts integration and migration are present.
    """
    if not isinstance(owner,str) or not owner:
        raise ValueError("Authenticated artifact owner required")

    async def publish_and_readback(case_id, name, data):
        from .artifacts import put, get
        run_id = UUID(case_id)
        async with db_factory() as db:
            item = await put(db,owner=owner,name=name,mime="text/plain",
                             data=data,direction="generated",run_id=run_id)
        artifact_id = UUID(item["id"])
        async with db_factory() as db:
            meta, actual = await get(db,owner=owner,file_id=artifact_id)
        if meta.get("id") != str(artifact_id) or meta.get("sha256") != hashlib.sha256(data).hexdigest():
            raise ValueError("Stored artifact identity or digest mismatch")
        return str(artifact_id), actual
    return publish_and_readback
