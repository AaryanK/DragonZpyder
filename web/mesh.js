import { renderMarkdown } from "./frontend/src/markdown.js";
// AI Mesh is deliberately separate from the existing permissioned Operly Agent.
// This browser-preview conversation is ephemeral until durable Mesh persistence lands.
const el=id=>document.getElementById(id);
const switcher=el("mesh-switch"),controls=el("mesh-controls"),task=el("mesh-task"),model=el("mesh-model");
const upload=el("mesh-upload"),fileLabel=el("mesh-file-label"),preview=el("mesh-attachments"),status=el("mesh-status");
const field=el("message-input"),chat=el("messages"),empty=el("empty-state"),scroller=el("chat-main");
const send=el("send-button"),conversationList=el("conversation-list"),composer=el("composer");
let enabled=false,loading=false,models=null,assets=[],payloadHistory=[],polling=false;
const allTasks={chat:"Text & vision",image:"Create image",transcribe:"Transcribe audio",speech:"Create speech",video:"Create video"};
function note(text,isError=false){
 status.textContent=text;status.classList.toggle("error",isError);status.hidden=!text;
}
function getCsrf(){
 const list=document.cookie.split(";").map(t=>t.trim());
 for(const key of ["__Host-operly_csrf","operly_csrf"]){
  const hit=list.find(x=>x.startsWith(key+"="));
  if(hit)return decodeURIComponent(hit.slice(key.length+1));
 }
 return "";
}
async function fetchMesh(path,payload){
 const r=await fetch("/mesh/"+path,{method:payload===undefined?"GET":"POST",credentials:"same-origin",
  headers:payload===undefined?{accept:"application/json"}:{"content-type":"application/json",accept:"application/json","x-csrf-token":getCsrf()},
  body:payload===undefined?undefined:JSON.stringify(payload),cache:"no-store",redirect:"error"});
 const data=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(data.detail?.message||"AI Mesh error ("+r.status+")");
 return data;
}

async function streamMeshChat(body,onChunk){
 const response=await fetch("/mesh/chat-stream",{
   method:"POST",credentials:"same-origin",redirect:"error",cache:"no-store",
   headers:{"content-type":"application/json",accept:"text/event-stream","x-csrf-token":getCsrf()},
   body:JSON.stringify(body)
 });
 if(!response.ok){
   let json={};try{json=await response.json()}catch{}
   throw Error(json.detail?.message||"Stream request failed ("+response.status+")");
 }
 const reader=response.body?.getReader();
 if(!reader)throw Error("Streaming is not supported by this browser");
 const decoder=new TextDecoder();let buffer="",text="",picked=body.model,usage=null,done=false;
 while(!done){
   const piece=await reader.read();
   if(piece.done)break;
   buffer+=decoder.decode(piece.value,{stream:true});
   const frames=buffer.split(/\r?\n\r?\n/);buffer=frames.pop()||"";
   for(const frame of frames){
     const line=frame.split(/\r?\n/).find(value=>value.startsWith("data:"));
     if(!line)continue;
     let event;try{event=JSON.parse(line.slice(5).trim())}catch{continue}
     if(event.type==="start")picked=event.model||picked;
     if(event.type==="delta"){text+=String(event.text||"");onChunk(text);}
     if(event.type==="usage")usage=event.usage;
     if(event.type==="error")throw Error(event.message||"Stream stopped unexpectedly");
     if(event.type==="done"){done=true;break}
   }
 }
 if(!done&&!text)throw Error("No streaming reply was returned");
 return {text,model:picked,usage};
}

function append(role,text,kind=""){
 empty.hidden=true;empty.style.setProperty("display","none","important");chat.classList.add("active");
 const article=document.createElement("article");article.className="message "+(role==="user"?"user":"assistant");
 const avatar=document.createElement("div");avatar.className="message-avatar";avatar.textContent=role==="user"?"You":"DZ";
 const body=document.createElement("div");body.className="message-body";
 const label=document.createElement("div");label.className="message-role";label.textContent=role==="user"?"You":"DragonZpyder · AI Mesh";
 const value=document.createElement("div");value.className="message-content";
 if(role==="assistant")renderMarkdown(value,text);else value.textContent=text;
 body.append(label,value);article.append(avatar,body);chat.append(article);
 requestAnimationFrame(()=>{scroller.scrollTop=scroller.scrollHeight});
 return {article,body,value};
}
function addMedia(item,kind,source){
 if(kind==="image"){
  const img=document.createElement("img");img.className="mesh-result-image";img.alt="Generated image";img.src=source;img.addEventListener("click",()=>window.open(img.src,"_blank","noopener,noreferrer"));item.body.append(img);
 }else if(kind==="audio"){
  const audio=document.createElement("audio");audio.controls=true;audio.className="mesh-result-audio";audio.src=source;item.body.append(audio);
 }else if(kind==="video"){
  const video=document.createElement("video");video.controls=true;video.playsInline=true;video.className="mesh-result-video";video.src=source;item.body.append(video);
 }
}
function option(m,selectedValue){
 const node=document.createElement("option");node.value=m.id;node.textContent=m.name||m.id;
 if(m.id===selectedValue)node.selected=true;
 return node;
}
function availableModels(){
 if(!models)return[];
 const selectedTask=task.value;
 if(selectedTask==="chat")return models.chat||[];
 if(selectedTask==="image")return models.image||[];
 if(selectedTask==="video")return models.video||[];
 if(selectedTask==="speech")return models.tts||[];
 if(selectedTask==="transcribe")return models.stt||[];
 return[];
}
function refreshModels(){
 if(!models)return;
 const list=availableModels();const old=model.value;
 model.replaceChildren();
 if(task.value==="chat"){
  const cheap=list.filter(m=>Number(m.promptPrice)<=0.0000015&&Number(m.completionPrice)<=0.000004&&m.inputs?.includes("text")&&m.outputs?.includes("text")&&(!assets.some(a=>a.mime.startsWith("image/"))||m.inputs?.includes("image")));
  const first=cheap.find(m=>m.id==="qwen/qwen3.7-flash")||cheap.find(m=>m.id==="google/gemini-3.1-flash-lite")||cheap[0];
  for(const m of cheap.slice(0,80))model.append(option(m,old||first?.id));
 }else{
  for(const m of list)model.append(option(m,old));
 }
 if(!model.options.length)note("No compatible models are available for this task.",true);
 else if(old&&Array.from(model.options).some(o=>o.value===old))model.value=old;
 else if(task.value==="chat"){const q=Array.from(model.options).find(o=>o.value==="qwen/qwen3.7-flash");if(q)model.value=q.value;}
}
const IMAGE_TYPES=["image/png","image/jpeg","image/webp"];
const AUDIO_TYPES=["audio/webm","audio/mpeg","audio/mp4","audio/ogg","audio/wav","audio/flac"];
const DOC_TYPES={pdf:"application/pdf",docx:"application/vnd.openxmlformats-officedocument.wordprocessingml.document",txt:"text/plain",md:"text/plain",csv:"text/plain",json:"application/json",py:"text/plain",log:"text/plain"};
function refreshTask(){
 const t=task.value;
 upload.accept=t==="transcribe"?"audio/*":'image/png,image/jpeg,image/webp,.pdf,.docx,.txt,.md,.csv,.json,.py,.log,audio/*';
 if(assets.length&&!["chat","transcribe"].includes(t))clearAssets();
 if(t==="video"&&!models?.videoEnabled)note("Video creation is disabled until a provider spending limit is configured.");
 else if(t==="image"&&!models?.imageEnabled)note("Image creation requires a provider spending limit.");
 else if(!loading)note(t==="chat"?"AI Mesh: text, images and files. Direct model calls do not access connected tools.":"");
 refreshModels();
}
function renderAssets(){
 preview.replaceChildren();
 preview.hidden=!assets.length;
 assets.forEach((item,index)=>{
  const chip=document.createElement("span");chip.className="mesh-file-chip";
  if(item.mime.startsWith("image/")){
   const img=document.createElement("img");img.src=item.data;img.alt="";img.className="mesh-file-thumb";chip.append(img);
  }
  const label=document.createElement("span");label.textContent=item.name+" · "+Math.max(1,Math.ceil(item.bytes/1024))+" KB";chip.append(label);
  const remove=document.createElement("button");remove.type="button";remove.setAttribute("aria-label","Remove "+item.name);
  remove.textContent="×";remove.addEventListener("click",()=>removeAsset(index));chip.append(remove);preview.append(chip);
 });
 window.dragonzpyderComposerSync?.();
}
function removeAsset(index){
 if(typeof index==="number")assets.splice(index,1);
 else assets=[];
 upload.value="";renderAssets();refreshModels();
}
function clearAssets(){removeAsset();}
async function asDataUrl(file,mime){
 return await new Promise((resolve,reject)=>{
  const reader=new FileReader();
  reader.onload=()=>resolve("data:"+mime+";base64,"+String(reader.result||"").split(",").slice(1).join(","));
  reader.onerror=()=>reject(Error("Could not read "+file.name));
  reader.readAsDataURL(file);
 });
}
async function setFiles(files){
 if(loading)return;
 const offered=Array.from(files||[]).filter(Boolean);if(!offered.length)return;
 const incoming=[];let bytes=assets.reduce((total,a)=>total+a.bytes,0);
 for(const file of offered){
  if(assets.length+incoming.length>=3){note("Attach at most three items.",true);break;}
  const ext=String(file.name||"").split(".").pop().toLowerCase();
  const mime=IMAGE_TYPES.includes(file.type)||AUDIO_TYPES.includes(file.type)?file.type:DOC_TYPES[ext];
  if(!mime){note("Supported: images, PDF, Word, text, code and audio.",true);continue;}
  if(!file.size||file.size>3*1024*1024||bytes+file.size>7*1024*1024){
    note("Each file must be at most 3 MB (7 MB combined).",true);continue;
  }
  bytes+=file.size;
  incoming.push({name:file.name||"pasted-image.png",mime,data:await asDataUrl(file,mime),bytes:file.size});
 }
 if(!incoming.length)return;
 if(!enabled)setActive(true,{preserveDraft:true});
 if(task.value!=="chat"&&!(task.value==="transcribe"&&incoming.every(item=>item.mime.startsWith("audio/")))){
  task.value="chat";refreshTask();
 }
 assets.push(...incoming);
 renderAssets();refreshModels();
 note("Attached "+assets.length+" file"+(assets.length===1?"":"s")+". Sent only when you submit.");
}
async function loadModels(){
 if(models)return;
 note("Loading available OpenRouter models…");
 models=await fetchMesh("models");
 refreshTask();
}
function clear(){
 payloadHistory=[];assets=[];upload.value="";preview.hidden=true;preview.replaceChildren();
 chat.replaceChildren();chat.classList.remove("active");empty.hidden=false;empty.style.removeProperty("display");
 field.value="";field.dispatchEvent(new Event("input"));note("");
 window.dragonzpyderComposerSync?.();
}
function setActive(value,{preserveDraft=false}={}){
 const draft=preserveDraft?field.value:"";
 if(loading)return;
 enabled=Boolean(value);switcher.setAttribute("aria-pressed",String(enabled));switcher.innerHTML=enabled?"<span>✦</span> AI Mesh":"<span>✦</span> Agent";
 controls.hidden=!enabled;
 if(enabled){
   // Distinct conversational state from Operly Agent; switching starts a clean view.
   clear();loadModels().catch(e=>note(e.message,true));
 }else{
   clear();
   note("");
   // Restore existing Operly history without creating any agent action.
   window.dispatchEvent(new Event("dragonzpyder:mesh-disabled"));
 }
 if(preserveDraft){field.value=draft;field.dispatchEvent(new Event("input"));}
 window.dragonzpyderComposerSync?.();
}
async function submit(text){
 if(!enabled||loading)return;
 const prompt=String(text||"").trim(),mode=task.value;
 if(!prompt&&!assets.length)return;
 if(!models){note("Models are still loading.",true);return}
 const chosen=model.value;if(!chosen){note("Choose a model.",true);return}
 if(mode==="transcribe"&&!assets.some(a=>a.mime.startsWith("audio/"))){note("Attach an audio recording to transcribe.",true);return}
 if(mode==="video"&&!models.videoEnabled){note("Video generation is disabled until a strict provider spending limit is configured.",true);return}
 if(mode==="image"&&!models.imageEnabled){note("Image generation is disabled until a provider key-level spending cap is configured.",true);return}
 if(mode==="image"&&!confirm("Generate ONE image? OpenRouter may charge your prepaid credits."))return;
 if(mode==="video"&&!confirm("Generate one SHORT video? This may cost more than ordinary chat; do you want to spend credits?"))return;
 loading=true;send.disabled=true;field.disabled=true;note("Working with "+chosen+" …");
 window.dragonzpyderComposerSync?.();
 field.value="";field.dispatchEvent(new Event("input"));
 const originals=[...assets];
 const userText=prompt||("Attached: "+originals.map(a=>a.name).join(", "));
 const user=append("user",userText+(originals.length?"\nAttached: "+originals.map(a=>a.name).join(", "):""));
 for(const item of originals.filter(a=>a.mime.startsWith("image/"))){
  const img=document.createElement("img");img.className="mesh-attachment-preview";img.src=item.data;img.alt="Attached image";user.body.append(img);
 }
 const answer=append("assistant","Working…");
 try{
  if(mode==="chat"){
   let cleaned=prompt;
   const audio=originals.find(a=>a.mime.startsWith("audio/"));
   if(audio){
    const speechModel=models.stt?.find(x=>x.id==="openai/whisper-large-v3")?.id||models.stt?.[0]?.id;
    if(!speechModel)throw Error("No transcription model available");
    note("Transcribing audio before sending…");
    const speech=await fetchMesh("transcribe",{audio:audio.data,model:speechModel});
    cleaned=(prompt?prompt+"\n\n":"")+"Audio transcript: "+speech.text;
   }
   const parts=[{type:"text",text:cleaned||"Please analyse these attachments."}];
   for(const item of originals){
    if(item.mime.startsWith("image/"))parts.push({type:"image_url",image_url:{url:item.data}});
    else if(!item.mime.startsWith("audio/"))parts.push({type:"file",file:{filename:item.name,file_data:item.data}});
   }
   const history=payloadHistory.slice(-10);
   const content=parts.length>1?parts:cleaned;
   const result=await streamMeshChat({model:chosen,messages:[...history,{role:"user",content}]},value=>{renderMarkdown(answer.value,value,{streaming:true});});
   const safeText=cleaned+(originals.length?"\n[Attached: "+originals.map(a=>a.name).join(", ")+"]":"");
   payloadHistory=[...history,{role:"user",content:safeText},{role:"assistant",content:result.text}].slice(-10);
   renderMarkdown(answer.value,result.text);
   const meta=document.createElement("div");meta.className="message-meta";meta.textContent="Model: "+result.model+(result.usage?.cost!=null?" · API cost: $"+Number(result.usage.cost).toFixed(5):"");answer.body.append(meta);
  }else if(mode==="image"){
   const result=await fetchMesh("image",{model:chosen,prompt,confirmed:true});
   answer.value.textContent="Image created with "+result.model;addMedia(answer,"image",result.image);
  }else if(mode==="transcribe"){
   const result=await fetchMesh("transcribe",{model:chosen,audio:originals.find(a=>a.mime.startsWith("audio/")).data});
   renderMarkdown(answer.value,result.text||"No words detected.");
   field.value=result.text||"";field.dispatchEvent(new Event("input"));
  }else if(mode==="speech"){
   const result=await fetchMesh("speech",{model:chosen,text:prompt});
   answer.value.textContent="Audio ready. Play below.";addMedia(answer,"audio",result.audio);
  }else if(mode==="video"){
   const job=await fetchMesh("video",{model:chosen,prompt,confirmed:true});
   answer.value.textContent="Video queued. This may take several minutes.";
   const query="?until="+encodeURIComponent(job.until)+"&proof="+encodeURIComponent(job.proof);
   const endAt=Date.now()+15*60*1000;
   let finished=false;
   while(enabled&&Date.now()<endAt&&!finished){
    await new Promise(resolve=>setTimeout(resolve,15000));
    const state=await fetchMesh("video/"+encodeURIComponent(job.id)+query);
    if(["failed","cancelled","expired"].includes(state.status))throw Error("Video job "+state.status+(state.error?": "+state.error:""));
    if(state.status==="completed"){
      answer.value.textContent="Video ready.";
      addMedia(answer,"video","/mesh/video/"+encodeURIComponent(job.id)+"/content"+query);
      finished=true;
    }else answer.value.textContent="Video "+state.status+"…";
   }
   if(!finished)answer.value.textContent+=" You can reopen this job while your session remains valid: "+job.id;
  }
  note("Completed · "+chosen);
 }catch(e){
  answer.value.textContent=e.message||"The model request failed.";answer.value.classList.add("error");note(e.message||"Request failed",true);
 }finally{
  loading=false;field.disabled=false;send.disabled=false;
  clearAssets();
  window.dragonzpyderComposerSync?.();
  field.focus();requestAnimationFrame(()=>{scroller.scrollTop=scroller.scrollHeight});
 }
}
switcher.addEventListener("click",()=>setActive(!enabled));
task.addEventListener("change",refreshTask);
upload.addEventListener("change",()=>setFiles(upload.files).catch(e=>note(e.message,true)));
field.addEventListener("paste",event=>{
 const files=Array.from(event.clipboardData?.items||[]).filter(x=>x.kind==="file"&&x.type.startsWith("image/")).map(x=>x.getAsFile()).filter(Boolean);
 if(files.length){event.preventDefault();setFiles(files).catch(e=>note(e.message,true));}
});
composer.addEventListener("dragover",event=>{
 if(event.dataTransfer?.types?.includes("Files")){event.preventDefault();composer.classList.add("dragging");}
});
composer.addEventListener("dragleave",event=>{
 if(!composer.contains(event.relatedTarget))composer.classList.remove("dragging");
});
composer.addEventListener("drop",event=>{
 composer.classList.remove("dragging");
 if(event.dataTransfer?.files?.length){event.preventDefault();setFiles(event.dataTransfer.files).catch(e=>note(e.message,true));}
});
fileLabel.addEventListener("keydown",event=>{
 if(event.key==="Enter"||event.key===" "){event.preventDefault();upload.click();}
});
window.dragonzpyderMesh={isActive:()=>enabled,isBusy:()=>loading,hasAttachments:()=>assets.length>0,submit,clear,disable:()=>setActive(false)};
window.dragonzpyderComposerSync?.();
