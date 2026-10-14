const launch=document.getElementById("companion-open"),panel=document.getElementById("companion-panel"),end=document.getElementById("companion-end"),mute=document.getElementById("companion-mute"),status=document.getElementById("companion-status"),history=document.getElementById("companion-transcript"),audio=document.getElementById("companion-audio");
let peer=null,channel=null,mic=null,controller=null,live=false,starting=false,silent=false,version=0;
const calls=new Set(),rows=new Map();
function setStatus(message,kind="idle"){status.textContent=message;panel.dataset.state=kind}
function csrf(){for(const k of ["__Host-operly_csrf","operly_csrf"]){const c=document.cookie.split(";").map(s=>s.trim()).find(s=>s.startsWith(k+"="));if(c)return decodeURIComponent(c.slice(k.length+1))}return ""}
function row(id,label,value,add=false){
  if(!value)return;
  let el=rows.get(id);
  if(!el){el=document.createElement("p");const b=document.createElement("strong");b.textContent=label+": ";el.append(b,document.createElement("span"));history.append(el);rows.set(id,el)}
  const span=el.querySelector("span");span.textContent=add?span.textContent+value:value;history.scrollTop=history.scrollHeight;
}
function send(event){if(channel?.readyState==="open")channel.send(JSON.stringify(event))}
function cleanup(){
  version++;controller?.abort();controller=null;
  for(const t of mic?.getTracks()||[])t.stop();mic=null;
  if(channel)channel.close();channel=null;if(peer)peer.close();peer=null;
  audio.pause();audio.srcObject=null;live=false;starting=false;silent=false;mute.disabled=true;mute.textContent="Mute";launch.setAttribute("aria-expanded","false");
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
    setStatus("Working through Operly…","active");
    output=await window.dragonzpyderDelegatePersonalTask(request);
  }catch(error){output={error:String(error.message||error)}}
  if(v!==version)return;
  send({type:"conversation.item.create",item:{type:"function_call_output",call_id:item.call_id,output:JSON.stringify(output)}});
  send({type:"response.create"});setStatus("Listening — speak naturally","active");
}
function onEvent(text,v){
  if(v!==version)return;
  let e;try{e=JSON.parse(text)}catch{return}
  if(e.type==="input_audio_buffer.speech_started")setStatus("Listening…","active");
  if(e.type==="input_audio_buffer.speech_stopped")setStatus("Thinking…","active");
  if(e.type==="response.created")setStatus("Speaking…","active");
  if(["response.output_audio_transcript.delta","response.audio_transcript.delta"].includes(e.type))row(e.item_id||e.response_id||"agent","DragonZpyder",e.delta,true);
  if(["response.output_audio_transcript.done","response.audio_transcript.done"].includes(e.type))row(e.item_id||e.response_id||"agent","DragonZpyder",e.transcript);
  if(e.type==="conversation.item.input_audio_transcription.completed")row(e.item_id||"user","You",e.transcript);
  if(e.type==="response.output_item.done"&&e.item?.type==="function_call"&&e.item.name==="delegate_personal_task")handleTool(e.item,v);
  if(e.type==="response.done")setStatus("Listening — speak naturally","active");
  if(e.type==="error")setStatus(String(e.error?.message||"Voice error"),"error");
}
async function start(){
  if(live||starting)return;
  panel.hidden=false;launch.setAttribute("aria-expanded","true");
  if(!navigator.mediaDevices?.getUserMedia||!window.RTCPeerConnection){setStatus("This browser cannot stream live audio","error");return}
  const v=++version;starting=true;controller=new AbortController();history.replaceChildren();rows.clear();calls.clear();setStatus("Requesting microphone…","connecting");
  try{
    mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
    if(v!==version)return;
    peer=new RTCPeerConnection();peer.ontrack=e=>{audio.srcObject=e.streams[0];audio.play().catch(()=>setStatus("Tap to enable audio playback","error"))};
    for(const t of mic.getAudioTracks())peer.addTrack(t,mic);
    channel=peer.createDataChannel("oai-events");channel.onmessage=e=>onEvent(e.data,v);
    channel.onclose=()=>{if(v===version&&live)close()};
    const offer=await peer.createOffer();await peer.setLocalDescription(offer);setStatus("Connecting live voice…","connecting");
    const r=await fetch("/companion/realtime",{method:"POST",credentials:"same-origin",headers:{"content-type":"application/sdp","x-csrf-token":csrf()},body:peer.localDescription.sdp,signal:controller.signal});
    if(!r.ok){const data=await r.json().catch(()=>({}));throw Error(data.detail?.message||"Connection failed: "+r.status)}
    const answer=await r.text();if(v!==version)return;
    await peer.setRemoteDescription({type:"answer",sdp:answer});live=true;starting=false;mute.disabled=false;setStatus("Listening — speak naturally","active");
  }catch(e){if(v!==version)return;cleanup();panel.hidden=false;setStatus(e.name==="NotAllowedError"?"Microphone permission denied":String(e.message||"Connection failed"),"error")}
}
launch.addEventListener("click",start);end.addEventListener("click",close);
mute.addEventListener("click",()=>{if(!mic||!live)return;silent=!silent;mic.getAudioTracks().forEach(t=>t.enabled=!silent);mute.textContent=silent?"Unmute":"Mute";setStatus(silent?"Microphone muted":"Listening — speak naturally","active")});
window.addEventListener("keydown",e=>{if(e.ctrlKey&&e.code==="Space"&&!e.repeat&&!e.altKey&&!e.metaKey){e.preventDefault();if(panel.hidden)start();else close()}else if(e.key==="Escape"&&!panel.hidden)close()});
window.addEventListener("pagehide",cleanup);window.addEventListener("dragonzpyder:logout",close);
