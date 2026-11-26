"""LiveKit transport worker. No model provider, tool authority or login cookies."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, room_io
from livekit.agents.llm import StopResponse
from livekit.plugins import deepgram, silero

server = AgentServer()

def settings():
    origin = os.environ["DRAGONZPYDER_VOICE_API_ORIGIN"].rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("Invalid internal API origin")
    token = os.environ["DRAGONZPYDER_VOICE_WORKER_TOKEN"]
    if len(token) < 40 or not os.environ.get("DEEPGRAM_API_KEY"):
        raise ValueError("Dedicated voice credentials required")
    return origin, token

def scope_from_metadata(metadata, room):
    scope = json.loads(metadata)
    sid = UUID(scope["session_id"])
    if scope["room"] != room or room != "dz-voice-" + sid.hex:
        raise ValueError("Room scope mismatch")
    return {k: scope[k] for k in ("session_id", "room", "nonce")}

@server.rtc_session(agent_name="dragonzpyder-voice-transport")
async def entrypoint(ctx: JobContext):
    origin, token = settings()
    scope = scope_from_metadata(ctx.job.metadata, ctx.room.name)
    async with httpx.AsyncClient(base_url=origin, headers={"Authorization": "Bearer "+token},
                                 timeout=145, follow_redirects=False) as http:
        async def call(path, body, timeout):
            res = await http.post("/internal/agents/voice/modular/"+path, json=body, timeout=timeout)
            res.raise_for_status()
            return res.json()

        grant = await call("authorize", scope, 10)
        identity = grant["participant_identity"]
        expiry = datetime.fromisoformat(grant["expires_at"])
        await ctx.connect()
        session = AgentSession(
            stt=deepgram.STTv2(model=os.getenv("DRAGONZPYDER_VOICE_STT_MODEL", "flux-general-en")),
            tts=deepgram.TTS(model=os.getenv("DRAGONZPYDER_VOICE_TTS_MODEL", "aura-2-thalia-en")),
            vad=silero.VAD.load(), turn_detection="stt",
            preemptive_generation=False, allow_interruptions=True,
        )
        stopped = asyncio.Event()
        active = None
        seen = set()

        async def notify(data):
            if not stopped.is_set():
                await ctx.room.local_participant.publish_data(
                    json.dumps(data, ensure_ascii=False).encode(), reliable=True,
                    destination_identities=[identity], topic="dz.voice")

        async def execute(event_id, transcript):
            try:
                await notify({"type":"working","event_id":event_id})
                result = await call("turn", {**scope,"event_id":event_id,"transcript":transcript}, 140)
                await call("authorize",scope,10)
                text = str(result.get("message",""))
                await notify({"type":"result","event_id":event_id,"transcript":transcript,
                              "conversation_id":result["conversation_id"],"message":text,
                              "status":result.get("status")})
                if not stopped.is_set() and text:
                    spoken = text[:4000] + (" The full answer is in your chat." if len(text)>4000 else "")
                    session.say(spoken, allow_interruptions=True, add_to_chat_ctx=False)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not retry an accepted or uncertain canonical turn.
                try:
                    await notify({"type":"uncertain","event_id":event_id})
                    if not stopped.is_set():
                        session.say("I could not confirm the result. Check your chat before repeating the request.",
                                    allow_interruptions=True, add_to_chat_ctx=False)
                except Exception:
                    pass

        class TransportAgent(Agent):
            async def on_user_turn_completed(self, turn_ctx, new_message):
                nonlocal active
                transcript = (new_message.text_content or "").strip()
                event_id = hashlib.sha256(str(new_message.id).encode()).hexdigest()
                if not transcript or event_id in seen or stopped.is_set():
                    raise StopResponse()
                if active is not None and not active.done():
                    session.say("Your previous request is still running.", allow_interruptions=True, add_to_chat_ctx=False)
                    raise StopResponse()
                if len(transcript)>12000 or len(seen)>=100:
                    raise StopResponse()
                seen.add(event_id)
                active = asyncio.create_task(execute(event_id, transcript))
                # No local LLM or preemptive tool execution. Playback cancellation
                # does not cancel or automatically replay the canonical request.
                raise StopResponse()

        @ctx.room.on("participant_disconnected")
        def participant_left(participant):
            if participant.identity == identity:
                stopped.set()

        await session.start(agent=TransportAgent(instructions="Transport only; no independent reasoning."),
                            room=ctx.room, room_options=room_io.RoomOptions(participant_identity=identity))
        try:
            while not stopped.is_set() and datetime.now(timezone.utc)<expiry:
                try:
                    await asyncio.wait_for(stopped.wait(), timeout=3)
                except asyncio.TimeoutError:
                    await call("authorize",scope,10)
        finally:
            stopped.set()
            if active and not active.done():
                active.cancel()
                await asyncio.gather(active, return_exceptions=True)
            await session.aclose()
            await ctx.room.disconnect()

if __name__ == "__main__":
    cli.run_app(server)
