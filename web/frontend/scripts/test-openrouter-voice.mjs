import test from "node:test";
import assert from "node:assert/strict";
import {encodeWav,UtteranceDetector,voiceFailureMessage,connectOpenRouterVoice} from "../src/openrouter-voice.js";

test("resamples and emits canonical 16 kHz mono WAV",()=>{
  const bytes=encodeWav([new Float32Array(48000).fill(.25)],48000);
  const view=new DataView(bytes.buffer);
  assert.equal(bytes.length,32044);
  assert.equal(view.getUint32(24,true),16000);
  assert.equal(view.getUint16(22,true),1);
  assert.equal(view.getUint16(34,true),16);
  assert.equal(view.getUint32(40,true),32000);
  assert.equal(view.getInt16(44,true),8192);
  assert.throws(()=>encodeWav([new Float32Array(100)],16000));
});
test("local VAD ignores silence, preserves pre-roll and ends after pause",()=>{
  let starts=0,turns=[];
  const d=new UtteranceDetector(()=>starts++,frames=>turns.push(frames));
  const quiet=new Float32Array(320),loud=new Float32Array(320).fill(.2);
  for(let i=0;i<100;i++)d.push(quiet);
  assert.equal(starts,0);
  for(let i=0;i<15;i++)d.push(loud);
  assert.equal(starts,1);
  for(let i=0;i<30;i++)d.push(quiet);
  assert.equal(turns.length,1);
  assert.equal(turns[0][0],quiet);
  for(let i=0;i<30;i++)d.push(quiet);
  assert.equal(turns.length,1);
});
test("short noises do not submit utterances",()=>{
  let turns=0;const d=new UtteranceDetector(()=>{},()=>turns++);
  for(let i=0;i<3;i++)d.push(new Float32Array(320).fill(.1));
  for(let i=0;i<30;i++)d.push(new Float32Array(320));
  assert.equal(turns,0);
});

test("voice failures distinguish unsubmitted transcription from uncertain agent work",()=>{
  assert.match(voiceFailureMessage({code:"voice_transcription_quota_or_rate_limit",outcome:"not_submitted"}),/No agent task was submitted/);
  assert.match(voiceFailureMessage({code:"voice_transcription_provider_unavailable",outcome:"not_submitted"}),/Transcription unavailable/);
  assert.match(voiceFailureMessage({code:"voice_agent_unconfirmed",outcome:"unconfirmed"}),/Check your chat/);
  assert.match(voiceFailureMessage({code:"private upstream data",outcome:"not_submitted"}),/Check your chat/);
});

test("native audio lifecycle stops capture on rejected turn and controls actual playback gain",async()=>{
  let node,gain,posted=0,closed=false,states=[];
  const previous={window:globalThis.window,AudioWorkletNode:globalThis.AudioWorkletNode,fetch:globalThis.fetch,crypto:globalThis.crypto};
  const link=()=>({connect(){},disconnect(){}});
  class Context {
    constructor(){this.sampleRate=16000;this.destination={};this.audioWorklet={addModule:async()=>{}};}
    async resume(){}
    async close(){closed=true;}
    createMediaStreamSource(){return link();}
    createMediaStreamDestination(){return {...link(),stream:{}};}
    createGain(){gain={...link(),gain:{value:1}};return gain;}
  }
  class Worklet {constructor(){node=this;this.port={};}connect(){}disconnect(){}}
  try{
    globalThis.window={AudioContext:Context};globalThis.AudioWorkletNode=Worklet;
    globalThis.fetch=async()=>{posted++;return new Response(JSON.stringify({detail:{code:"voice_transcription_quota_or_rate_limit",outcome:"not_submitted"}}),{status:429,headers:{"Content-Type":"application/json"}});};
    const room=await connectOpenRouterVoice({stream:{},sessionId:"test",csrf:"test",onData(){assert.fail("unexpected agent answer");},onRemote(){},onState(m,k){states.push([m,k]);}});
    room.setPlaybackMuted(true);assert.equal(gain.gain.value,0);
    room.setPlaybackMuted(false);assert.equal(gain.gain.value,1);
    const utterance=()=>{for(let i=0;i<15;i++)node.port.onmessage({data:new Float32Array(320).fill(.2)});for(let i=0;i<30;i++)node.port.onmessage({data:new Float32Array(320)});};
    utterance();await new Promise(resolve=>setImmediate(resolve));
    assert.equal(posted,1);assert.equal(states.at(-1)[1],"error");assert.match(states.at(-1)[0],/No agent task was submitted/);
    utterance();room.setMuted(true);room.setMuted(false);utterance();
    await new Promise(resolve=>setImmediate(resolve));assert.equal(posted,1);
    await room.disconnect();assert.equal(closed,true);
  }finally{globalThis.window=previous.window;globalThis.AudioWorkletNode=previous.AudioWorkletNode;globalThis.fetch=previous.fetch;}
});
