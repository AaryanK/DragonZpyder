// Browser-native capture and turn segmentation. No third-party audio transport.
// The browser retains no recordings; only bounded complete utterances are sent.
const TARGET_RATE=16000, FRAME_MS=20, PRE_FRAMES=12, START_FRAMES=3, END_FRAMES=30;
const MAX_FRAMES=1450, MIN_VOICED=8;
const WORKLET=`
class Capture extends AudioWorkletProcessor {
  constructor(){super();this.length=Math.round(sampleRate/50);this.frame=new Float32Array(this.length);this.offset=0;}
  process(inputs){
    const input=inputs[0]?.[0];
    if(input)for(const sample of input){
      this.frame[this.offset++]=sample;
      if(this.offset===this.length){
        this.port.postMessage(this.frame,[this.frame.buffer]);
        this.frame=new Float32Array(this.length);this.offset=0;
      }
    }
    return true;
  }
}
registerProcessor("dz-voice-capture",Capture);
`;

export function encodeWav(frames,rate) {
  const total=frames.reduce((n,x)=>n+x.length,0);
  if(!Number.isFinite(rate)||rate<8000||rate>192000||total/rate>30||total/rate<0.15)throw Error("Invalid utterance length");
  const input=new Float32Array(total);let off=0;
  for(const frame of frames){input.set(frame,off);off+=frame.length;}
  const count=Math.floor(total*TARGET_RATE/rate),bytes=new Uint8Array(44+2*count),view=new DataView(bytes.buffer);
  const tag=(at,t)=>{for(let i=0;i<t.length;i++)bytes[at+i]=t.charCodeAt(i);};
  tag(0,"RIFF");view.setUint32(4,bytes.length-8,true);tag(8,"WAVE");tag(12,"fmt ");
  view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
  view.setUint32(24,TARGET_RATE,true);view.setUint32(28,TARGET_RATE*2,true);
  view.setUint16(32,2,true);view.setUint16(34,16,true);tag(36,"data");view.setUint32(40,count*2,true);
  for(let i=0;i<count;i++){
    const start=i*rate/TARGET_RATE,end=(i+1)*rate/TARGET_RATE;
    let sample=0,n=0;
    for(let j=Math.floor(start);j<Math.min(total,Math.ceil(end));j++){
      const weight=Math.max(0,Math.min(end,j+1)-Math.max(start,j));
      sample+=input[j]*weight;n+=weight;
    }
    sample=Math.max(-1,Math.min(1,n?sample/n:0));
    view.setInt16(44+i*2,Math.round(sample*(sample<0?32768:32767)),true);
  }
  return bytes;
}
function base64(bytes){let str="";for(let i=0;i<bytes.length;i+=8192)str+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(str);}

export class UtteranceDetector {
  constructor(onStart,onEnd){this.onStart=onStart;this.onEnd=onEnd;this.noise=.004;this.reset();}
  reset(){this.pre=[];this.frames=null;this.hot=0;this.cold=0;this.voiced=0;}
  push(frame){
    let sum=0;for(const x of frame)sum+=x*x;
    const rms=Math.sqrt(sum/frame.length),threshold=Math.max(.012,Math.min(.07,this.noise*3.5));
    const hot=rms>threshold;
    if(!this.frames){
      if(!hot)this.noise=.98*this.noise+.02*rms;
      this.pre.push(frame);if(this.pre.length>PRE_FRAMES)this.pre.shift();
      this.hot=hot?this.hot+1:0;
      if(this.hot>=START_FRAMES){
        this.frames=this.pre.slice();this.voiced=this.hot;this.cold=0;this.onStart();
      }
      return;
    }
    this.frames.push(frame);
    if(hot){this.voiced++;this.cold=0;}else this.cold++;
    if(this.cold>=END_FRAMES||this.frames.length>=MAX_FRAMES){
      const frames=this.frames,voiced=this.voiced;this.reset();
      if(voiced>=MIN_VOICED)this.onEnd(frames);
    }
  }
}

export async function connectOpenRouterVoice({stream,sessionId,csrf,onData,onState,onRemote}){
  const Audio=window.AudioContext||window.webkitAudioContext;
  if(!Audio)throw Error("Browser audio unavailable");
  const ctx=new Audio();
  if(!ctx.audioWorklet){await ctx.close();throw Error("AudioWorklet required for live voice");}
  const source=ctx.createMediaStreamSource(stream),sink=ctx.createMediaStreamDestination();
  const url=URL.createObjectURL(new Blob([WORKLET],{type:"text/javascript"}));
  let worklet;
  try{await ctx.resume();await ctx.audioWorklet.addModule(url);worklet=new AudioWorkletNode(ctx,"dz-voice-capture");}
  catch(error){await ctx.close();throw error;}
  finally{URL.revokeObjectURL(url);}
  source.connect(worklet);worklet.connect(ctx.destination);
  onRemote(sink.stream);
  let closed=false,muted=false,busy=false,speech=null,playing=null,speechVersion=0;
  const life=new AbortController();
  const root="/dz/v2/personal/voice/sessions/"+sessionId;
  async function post(path,body,signal){
    const response=await fetch(root+path,{method:"POST",credentials:"same-origin",redirect:"error",cache:"no-store",
      headers:{"Content-Type":"application/json","X-DZ-CSRF":csrf},body:JSON.stringify(body),signal});
    if(!response.ok)throw Error("Voice request unavailable ("+response.status+")");
    return response;
  }
  function stopSpeech(){
    speechVersion++;speech?.abort();speech=null;
    if(playing){try{playing.stop()}catch{}playing=null;}
  }
  async function speak(data){
    stopSpeech();const v=speechVersion;const controller=new AbortController();speech=controller;
    const valid=()=>!closed&&v===speechVersion&&!controller.signal.aborted;
    const load=async i=>{
      const res=await post("/speech/"+data.event_id+"/"+i,{},controller.signal);
      if(!res.headers.get("content-type")?.startsWith("audio/"))throw Error("Invalid voice audio");
      const bytes=await res.arrayBuffer();
      if(bytes.byteLength>5*1024*1024)throw Error("Voice audio exceeds bound");
      return await ctx.decodeAudioData(bytes);
    };
    try{
      const count=Math.min(4,Math.max(0,Number(data.speech_segments)||0));
      if(!count)return;
      let next=load(0);
      for(let i=0;i<count&&valid();i++){
        const buffer=await next;if(!valid())return;
        // Only one segment ahead. Attach a rejection handler immediately so
        // interruption or provider failure cannot leak an unhandled promise.
        if(i+1<count){next=load(i+1);next.catch(()=>{});}
        const node=ctx.createBufferSource();node.buffer=buffer;
        node.connect(ctx.destination);node.connect(sink);playing=node;
        onState("Speaking…","speaking");
        await new Promise(resolve=>{node.onended=resolve;node.start();});
        if(playing===node)playing=null;
        node.disconnect();
      }
      if(valid())onState("Listening — speak naturally","listening");
    }catch(error){if(valid())onState("Speech unavailable. The answer is in chat.","error");}
    finally{if(speech===controller)speech=null;}
  }
  async function submit(frames){
    if(closed||muted||busy)return;
    busy=true;stopSpeech();
    const id=crypto.randomUUID();
    onState("Transcribing and working…","working");
    try{
      const encoded=base64(encodeWav(frames,ctx.sampleRate));
      const res=await post("/turn",{event_id:id,audio:encoded},life.signal);
      const data=await res.json();
      if(closed)return;
      if(data.event_id!==id)throw Error("Invalid voice response");
      if(data.status==="no_speech"){onState("Listening — speak naturally","listening");return;}
      if(typeof data.message!=="string"||typeof data.conversation_id!=="string")throw Error("Invalid voice answer");
      onData(data);
      // A single accepted agent turn is allowed at a time. Playback is
      // asynchronous: barge-in interrupts speech without replaying the turn.
      if(!detector.frames)void speak(data);
      else onState("Answer is in chat — listening","listening");
    }catch(error){if(!closed)onState("Request outcome unconfirmed. Check your chat before repeating.","error");}
    finally{busy=false;}
  }
  const detector=new UtteranceDetector(()=>{
    if(closed||muted)return;
    stopSpeech();
    onState(busy?"Previous request still running":"Listening…",busy?"working":"listening");
  },frames=>{if(!busy&&!closed&&!muted)void submit(frames);});
  worklet.port.onmessage=e=>{if(!closed&&!muted&&e.data instanceof Float32Array)detector.push(e.data);};
  return {
    setMuted(value){muted=Boolean(value);detector.reset();},
    async disconnect(){if(closed)return;closed=true;life.abort();stopSpeech();detector.reset();worklet.port.onmessage=null;
      source.disconnect();worklet.disconnect();await ctx.close();}
  };
}
