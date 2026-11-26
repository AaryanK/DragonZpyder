const launch=document.getElementById("companion-open"),panel=document.getElementById("companion-panel"),end=document.getElementById("companion-end"),mute=document.getElementById("companion-mute"),audio=document.getElementById("companion-audio");
let peer=null,channel=null,mic=null,controller=null,live=false,starting=false,silent=false,version=0;
const calls=new Set();
// Native voice reservations belong to the authenticated session, not the
// legacy companion. Let a submitted start settle even if the UI closes,
// so a late accepted provider call can be ended rather than orphaned.
let nativeCall=null,nativePending=null,nativeClosing=null,expiryTimer=null;
function voiceContext(){return window.dragonzpyderVoiceContext?.()||{available:false,native:false}}
function endNative(call){
  if(!call||call.ending)return call?.ending;
  call.ending=(async()=>{
    try{
      const res=await fetch("/dz/v2/personal/voice/"+call.id+"/end",{
        method:"POST",credentials:"same-origin",headers:{"X-DZ-CSRF":call.csrf},cache:"no-store",keepalive:true,redirect:"error"
      });
      if(!res.ok)throw Error("Voice hangup unconfirmed");
      const body=await res.json();
      if(body.session_id!==call.id||body.state!=="closed")throw Error("Voice hangup unconfirmed");
    }catch{
      // The server retains uncertain calls and reconciles expired sessions.
      // Never silently start another provider call to recover this one.
      browserEvent("voice-hangup-unconfirmed",{session_id:call.id});
    }
  })();
  nativeClosing=call.ending;
  void call.ending.finally(()=>{if(nativeClosing===call.ending)nativeClosing=null;});
  return call.ending;
}
// This is transcription only: browser speech recognition must not trigger agent calls.
const SpeechApi=window.SpeechRecognition||window.webkitSpeechRecognition;
let browserMode=false,recognition=null,recognitionRun=0,restartTimer=null;
function browserEvent(name,detail){window.dispatchEvent(new CustomEvent("dragonzpyder:"+name,{detail}))}
function stopRecognition(){
  clearTimeout(restartTimer);restartTimer=null;
  const instance=recognition;recognition=null;
  if(instance){try{instance.abort()}catch{}}
}
function browserPaused(message="Tap the microphone to resume transcription."){
  // SpeechRecognition uses its browser-managed capture. Explicitly mute the
  // separately held meter track too, so pausing transcription pauses visuals.
  for(const track of mic?.getAudioTracks?.()||[])track.enabled=false;
  silent=true;browserEvent("voice-mute",{muted:true});setStatus(message,"paused");
}
function listenInBrowser(){
  if(!browserMode||recognition||!SpeechApi)return;
  clearTimeout(restartTimer);restartTimer=null;
  let instance;
  try{instance=new SpeechApi()}catch{browserPaused("Browser transcription could not start. Tap the microphone to retry.");return}
  const v=version,run=++recognitionRun;
  recognition=instance;
  let failed=false,hadSpeech=false;
  for(const track of mic?.getAudioTracks?.()||[])track.enabled=true;
  silent=false;browserEvent("voice-mute",{muted:false});
  setStatus("Starting browser transcription…","transcribing");
  const current=()=>browserMode&&v===version&&recognition===instance;
  instance.lang=navigator.language||"en-US";
  instance.continuous=true;
  instance.interimResults=true;
  instance.onstart=()=>{if(current())setStatus("Listening — speak naturally","transcribing")};
  instance.onresult=event=>{
    if(!current()||silent)return;
    for(let i=event.resultIndex||0;i<event.results.length;i++){
      const result=event.results[i],value=result[0]?.transcript?.trim();
      if(!value)continue;
      hadSpeech=hadSpeech||Boolean(result.isFinal);
      browserEvent("voice-transcript",{id:"browser-"+run+"-"+i,label:"You",value,append:false,interim:!result.isFinal});
    }
  };
  instance.onerror=event=>{
    if(!current())return;
    failed=true;
    if(event.error==="aborted")return;
    if(event.error==="not-allowed"||event.error==="service-not-allowed"){
      browserPaused("Speech recognition permission denied. Check browser permissions, then tap the mic.");
    }else if(event.error==="no-speech"){
      browserPaused("No speech detected. Tap the microphone to try again.");
    }else{
      browserPaused("Browser transcription stopped. Tap the microphone to retry.");
    }
  };
  instance.onend=()=>{
    if(!current())return;
    recognition=null;
    // Mobile browsers may end after an utterance even with continuous=true.
    // Restart only following actual final speech; never loop on denied permissions,
    // unavailable services, silence, or an explicit pause.
    if(!failed&&hadSpeech&&!silent){
      restartTimer=setTimeout(()=>{if(browserMode&&v===version&&!silent)listenInBrowser()},250);
    }else if(!silent){browserPaused()}
  };
  try{instance.start()}catch{recognition=null;browserPaused("Tap the microphone to start browser transcription.")}
}
function beginBrowserFallback(){
  if(!SpeechApi)return false;
  // The WebRTC negotiation failed, not the user's granted microphone access.
  // Retain only the previously authorized *local* audio stream for the visual
  // meter; close the peer/data channel and abort the provider request as usual.
  // Without this, the fallback closes its microphone and has no actual audio
  // energy to drive the original canvas orb.
  const localMeterStream=mic;
  mic=null;
  cleanup();
  mic=localMeterStream;
  browserMode=true;panel.hidden=false;launch.setAttribute("aria-expanded","true");
  browserEvent("voice-mode",{mode:"browser"});
  if(mic?.getAudioTracks?.().some(track=>track.readyState!=="ended")){
    browserEvent("voice-input",{stream:mic});
  }
  listenInBrowser();
  return true;
}
function setStatus(message,kind="idle"){
  panel.dataset.state=kind;
  window.dispatchEvent(new CustomEvent("dragonzpyder:voice-state",{detail:{kind,message}}));
}
function csrf(native=false){for(const k of (native?["__Host-dz_csrf"]:["__Host-operly_csrf","operly_csrf"])){const c=document.cookie.split(";").map(s=>s.trim()).find(s=>s.startsWith(k+"="));if(c)return decodeURIComponent(c.slice(k.length+1))}return ""}
function row(id,label,value,append=false){
  if(!value)return;
  window.dispatchEvent(new CustomEvent("dragonzpyder:voice-transcript",{
    detail:{id,label,value,append}
  }));
}
function send(event){if(channel?.readyState==="open")channel.send(JSON.stringify(event))}
function cleanup(){
  version++;clearTimeout(expiryTimer);expiryTimer=null;
  const closing=nativeCall;nativeCall=null;
  if(closing){closing.closed=true;if(closing.settled)void endNative(closing);}
  else controller?.abort();
  controller=null;
  browserMode=false;stopRecognition();
  browserEvent("voice-mode",{mode:"realtime"});
  for(const t of mic?.getTracks()||[])t.stop();mic=null;
  if(channel)channel.close();channel=null;if(peer)peer.close();peer=null;
  audio.pause();audio.srcObject=null;live=false;starting=false;silent=false;
  launch.setAttribute("aria-expanded","false");
  window.dispatchEvent(new CustomEvent("dragonzpyder:voice-session",{detail:{connected:false}}));
  window.dispatchEvent(new CustomEvent("dragonzpyder:voice-mute",{detail:{muted:false}}));
  window.dispatchEvent(new Event("dragonzpyder:voice-closed"));
}
function close(){cleanup();panel.hidden=true;setStatus("Ended");launch.focus()}
async function handleTool(item,v){
  if(!item.call_id||calls.has(item.call_id))return;
  calls.add(item.call_id);
  let output;
  try{
    const input=JSON.parse(item.arguments||"{}"),request=String(input.request||"").trim();
    if(!request||request.length>12000)throw Error("Invalid Personal task");
    if(typeof window.dragonzpyderDelegatePersonalTask!=="function")throw Error("Personal agent unavailable");
    setStatus("Working through Operly…","working");
    output=await window.dragonzpyderDelegatePersonalTask(request);
  }catch(error){output={error:String(error.message||error)}}
  if(v!==version)return;
  send({type:"conversation.item.create",item:{type:"function_call_output",call_id:item.call_id,output:JSON.stringify(output)}});
  send({type:"response.create"});setStatus("Listening — speak naturally","listening");
}
function onEvent(text,v,native=false){
  if(v!==version)return;
  let e;try{e=JSON.parse(text)}catch{return}
  if(e.type==="input_audio_buffer.speech_started")setStatus("Listening…","listening");
  if(e.type==="input_audio_buffer.speech_stopped")setStatus("Thinking…","thinking");
  if(e.type==="response.created")setStatus("Speaking…","speaking");
  if(["response.output_audio_transcript.delta","response.audio_transcript.delta"].includes(e.type))row(e.item_id||e.response_id||"agent","DragonZpyder",e.delta,true);
  if(["response.output_audio_transcript.done","response.audio_transcript.done"].includes(e.type))row(e.item_id||e.response_id||"agent","DragonZpyder",e.transcript);
  if(e.type==="conversation.item.input_audio_transcription.completed")row(e.item_id||"user","You",e.transcript);
  if(!native&&e.type==="response.output_item.done"&&e.item?.type==="function_call"&&e.item.name==="delegate_personal_task")handleTool(e.item,v);
  if(e.type==="response.done")setStatus("Listening — speak naturally","listening");
  if(e.type==="error")setStatus(String(e.error?.message||"Voice error"),"error");
}
async function start(){
  if(live||starting||browserMode)return;
  const context=voiceContext();
  if(!context.available||launch.disabled||nativePending||nativeClosing)return;
  const native=context.native===true;
  window.dispatchEvent(new Event("dragonzpyder:live-start"));
  panel.hidden=false;launch.setAttribute("aria-expanded","true");
  window.dispatchEvent(new Event("dragonzpyder:voice-open"));
  if(!navigator.mediaDevices?.getUserMedia||!window.RTCPeerConnection){
    if(native||!beginBrowserFallback())setStatus("This browser cannot stream live audio. Use chat dictation instead.","error");
    return;
  }
  const v=++version;starting=true;controller=new AbortController();calls.clear();setStatus("Requesting microphone…","connecting");
  try{
    const acquired=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
    if(v!==version){ acquired.getTracks().forEach(track=>track.stop()); return; }
    mic=acquired;
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-input",{detail:{stream:mic}}));
    peer=new RTCPeerConnection();peer.ontrack=e=>{
      if(v!==version)return;
      audio.srcObject=e.streams[0];
      window.dispatchEvent(new CustomEvent("dragonzpyder:voice-output",{detail:{stream:e.streams[0]}}));
      audio.play().catch(()=>setStatus("Tap to enable audio playback","error"));
    };
    for(const t of mic.getAudioTracks())peer.addTrack(t,mic);
    channel=peer.createDataChannel("oai-events");channel.onmessage=e=>onEvent(e.data,v,native);
    channel.onclose=()=>{if(v===version&&live)close()};
    const offer=await peer.createOffer();if(v!==version)return;
    await peer.setLocalDescription(offer);if(v!==version)return;
    setStatus("Connecting live voice…","connecting");
    let r,call;
    if(native){
      const token=csrf(true);if(!token)throw Error("Secure session missing. Sign in again.");
      if(!window.crypto?.randomUUID)throw Error("Secure browser context required.");
      call={id:crypto.randomUUID(),csrf:token,settled:false,closed:false,ending:null};nativeCall=call;nativePending=call;
      try{r=await fetch("/dz/v2/personal/voice/start",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json","X-DZ-CSRF":token},body:JSON.stringify({session_id:call.id,sdp:peer.localDescription.sdp}),cache:"no-store",redirect:"error"});}
      catch(err){call.settled=true;void endNative(call);throw err;}
      finally{if(nativePending===call)nativePending=null;}
      call.settled=true;
      if(v!==version||call.closed){if(r.ok||r.status>=500)void endNative(call);return;}
    }else r=await fetch("/companion/realtime",{method:"POST",credentials:"same-origin",headers:{"content-type":"application/sdp","x-csrf-token":csrf()},body:peer.localDescription.sdp,signal:controller.signal});
    if(!r.ok){
      const data=await r.json().catch(()=>({}));
      if(v!==version)return;
      // Only provider availability failures can fall back; never bypass an
      // authentication error, CSRF rejection, or the provider rate limit.
      if(!native&&(r.status===502||r.status===503)&&beginBrowserFallback())return;
      if(native&&r.status<500)nativeCall=null;
      throw Error(typeof data.detail==="string"?data.detail:data.detail?.message||"Connection failed: "+r.status);
    }
    let answer;
    if(native){
      const result=await r.json();if(v!==version)return;
      if(result.session_id!==call.id||typeof result.sdp!=="string"||!result.sdp.startsWith("v=0")||result.sdp.length>65536||!Number.isFinite(result.duration_seconds)||result.duration_seconds<=0||result.duration_seconds>600)throw Error("Invalid native voice response.");
      answer=result.sdp;
      const expires=Date.parse(result.expires_at),duration=result.duration_seconds*1000;
      expiryTimer=setTimeout(()=>{if(v===version){cleanup();panel.hidden=false;setStatus("Voice session allowance reached. Return to chat to continue.","error");}},Number.isFinite(expires)?Math.max(0,Math.min(duration,expires-Date.now())):duration);
    }else answer=await r.text();
    if(v!==version)return;
    await peer.setRemoteDescription({type:"answer",sdp:answer});if(v!==version)return;live=true;starting=false;
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-session",{detail:{connected:true}}));
    setStatus("Listening — speak naturally","listening");
  }catch(e){if(v!==version)return;cleanup();panel.hidden=false;setStatus(e.name==="NotAllowedError"?"Microphone permission denied":String(e.message||"Connection failed"),"error")}
}
launch.addEventListener("click",start);end.addEventListener("click",close);
mute.addEventListener("click",()=>{
  if(browserMode){
    if(!silent){stopRecognition();browserPaused()}
    else{stopRecognition();listenInBrowser()}
    return;
  }
  if(!mic||!live)return;
  silent=!silent;mic.getAudioTracks().forEach(t=>t.enabled=!silent);
  window.dispatchEvent(new CustomEvent("dragonzpyder:voice-mute",{detail:{muted:silent}}));
  setStatus(silent?"Microphone muted":"Listening — speak naturally","listening");
});
window.addEventListener("keydown",e=>{if(e.ctrlKey&&e.code==="Space"&&!e.repeat&&!e.altKey&&!e.metaKey){e.preventDefault();if(panel.hidden){if(voiceContext().available&&!launch.disabled)start()}else close()}else if(e.key==="Escape"&&!panel.hidden)close()});
window.addEventListener("pagehide",cleanup);window.addEventListener("dragonzpyder:logout",close);
