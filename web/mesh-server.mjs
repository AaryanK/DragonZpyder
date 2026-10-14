
import { createHmac, createHash, timingSafeEqual } from "node:crypto";
const BASE="https://openrouter.ai/api/v1";
const lists=new Map(),limits=new Map();
const MAX_BODY=8*1024*1024;
function response(res,code,obj){
  const body=JSON.stringify(obj);
  res.writeHead(code,{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"});
  res.end(body);
}
function error(res,code,message){response(res,code,{detail:{message}})}
function cookies(header){
  const out=new Map();
  for(const p of String(header||"").split(";")){const at=p.indexOf("=");if(at<0)continue;
    try{out.set(p.slice(0,at).trim(),decodeURIComponent(p.slice(at+1).trim()))}
    catch{out.set(p.slice(0,at).trim(),p.slice(at+1).trim())}}
  return out;
}
function same(a,b){const x=Buffer.from(String(a||"")),y=Buffer.from(String(b||""));return x.length>0&&x.length===y.length&&timingSafeEqual(x,y)}
function validOrigin(req){
  try{const o=new URL(String(req.headers.origin||""));return o.host===req.headers.host&&(o.protocol==="https:"||o.protocol==="http:"&&["localhost","127.0.0.1"].includes(o.hostname))}
  catch{return false}
}
async function identity(req,operly,mutating){
  if(mutating&&!validOrigin(req))throw {code:403,message:"Same-origin request required"};
  if(mutating){
    const jar=cookies(req.headers.cookie),token=req.headers["x-csrf-token"];
    if(!same(token,jar.get("__Host-operly_csrf"))&&!same(token,jar.get("operly_csrf")))
      throw {code:403,message:"Invalid session security token"};
  }
  const result=await fetch(operly+"/api/auth/sessions",{
    headers:{cookie:String(req.headers.cookie||""),origin:operly,referer:operly+"/",accept:"application/json"},
    signal:AbortSignal.timeout(10000)});
  if(!result.ok)throw {code:401,message:"Sign in to DragonZpyder Personal"};
  const sessions=await result.json();
  const session=Array.isArray(sessions)?sessions.find(s=>s?.current&&s.scope==="personal"):null;
  if(!session?.id)throw {code:403,message:"Personal-only session is required"};
  return createHash("sha256").update(String(session.id)).digest("hex");
}
async function jsonBody(req){
  if(Number(req.headers["content-length"]||0)>MAX_BODY)throw {code:413,message:"Attachment is too large"};
  const chunks=[];let total=0;
  for await(const c of req){total+=c.length;if(total>MAX_BODY)throw {code:413,message:"Request size limit reached"};chunks.push(c)}
  try{return JSON.parse(Buffer.concat(chunks).toString("utf8"))}
  catch{throw {code:400,message:"Invalid JSON request"}}
}
function key(){
  const k=process.env.OPENROUTER_API_KEY;
  if(!k)throw {code:503,message:"OpenRouter credentials are not configured"};
  return k;
}
function authHeaders(){return {authorization:"Bearer "+key(),"content-type":"application/json","HTTP-Referer":"https://dragonzpyder.xyz","X-Title":"DragonZpyder AI Mesh"}}
async function upstream(path,{method="GET",data,timeout=60000}={}){
  const r=await fetch(BASE+path,{method,headers:authHeaders(),body:data===undefined?undefined:JSON.stringify(data),signal:AbortSignal.timeout(timeout)});
  if(!r.ok){
    let detail;try{detail=await r.json()}catch{}
    const msg=String(detail?.error?.message||detail?.message||"OpenRouter request failed").slice(0,240);
    throw {code:r.status>=500?502:r.status,message:msg};
  }
  return r;
}
async function catalogue(kind){
  const now=Date.now(),cached=lists.get(kind);
  if(cached&&cached.until>now)return cached.items;
  const paths={chat:"/models",image:"/images/models",video:"/videos/models"};
  const data=await (await upstream(paths[kind],{timeout:14000})).json();
  const items=Array.isArray(data?.data)?data.data:[];
  lists.set(kind,{items,until:now+15*60*1000});
  return items;
}
const modes={
  chat:"chat",
  image:"image",
  video:"video"
};
const inputs=m=>m.architecture?.input_modalities||[];
const outputs=m=>m.architecture?.output_modalities||[];
function cents(m){
  const inp=Number(m.pricing?.prompt),out=Number(m.pricing?.completion);
  if(!Number.isFinite(inp)||!Number.isFinite(out)||inp<0||out<0)return Infinity;
  return inp+out;
}
async function catalogList(){
  const [chat,image,video]=await Promise.all([catalogue("chat"),catalogue("image"),catalogue("video")]);
  const chats=chat.filter(m=>inputs(m).includes("text")&&outputs(m).includes("text"))
    .sort((a,b)=>cents(a)-cents(b)).slice(0,500).map(m=>({
      id:m.id,name:m.name||m.id,inputs:inputs(m),outputs:outputs(m),
      promptPrice:m.pricing?.prompt,completionPrice:m.pricing?.completion,
      context:m.context_length
    }));
  const images=image.slice(0,80).map(m=>({id:m.id,name:m.name||m.id}));
  const videos=video.slice(0,80).map(m=>({
    id:m.id,name:m.name||m.id,options:{durations:m.supported_durations||[],resolutions:m.supported_resolutions||[],ratios:m.supported_aspect_ratios||[],pricing:m.pricing_skus||{}}
  }));
  const tts=chat.filter(m=>outputs(m).includes("speech")).map(m=>({id:m.id,name:m.name||m.id})).slice(0,40);
  const stt=chat.filter(m=>outputs(m).includes("transcription")).map(m=>({id:m.id,name:m.name||m.id})).slice(0,40);
  return {chat:chats,image:images,video:videos,tts,stt,videoEnabled:process.env.MESH_ENABLE_VIDEO==="true"};
}
function take(identity,kind){
  const day=new Date().toISOString().slice(0,10),id=day+":"+identity+":"+kind;
  const max={chat:40,image:2,video:1,speech:10,transcribe:10};
  if(limits.size>10000)for(const k of limits.keys())if(!k.startsWith(day+":"))limits.delete(k);
  const n=limits.get(id)||0;
  if(n>=max[kind])throw {code:429,message:"Daily AI Mesh test limit reached for "+kind};
  limits.set(id,n+1);
}
function selected(list,id){return list.find(m=>m.id===id)}
function modestChat(m){
  const a=Number(m.pricing?.prompt),b=Number(m.pricing?.completion);
  if(!Number.isFinite(a)||!Number.isFinite(b)||a>0.0000015||b>0.000004||a<0||b<0)
    throw {code:403,message:"That model exceeds the AI Mesh low-cost testing policy"};
}
const formats=new Map([["image/png","png"],["image/jpeg","jpeg"],["image/webp","webp"],["audio/webm","webm"],["audio/mpeg","mp3"],["audio/mp4","m4a"],["audio/ogg","ogg"],["audio/wav","wav"],["audio/flac","flac"]]);
function inline(raw,allow){
  const value=String(raw||"");
  const match=value.match(/^data:([\w.+/-]+);base64,([A-Za-z0-9+/=]+)$/);
  if(!match||!allow.includes(match[1])||value.length>5*1024*1024)throw {code:400,message:"Unsupported attachment or too large (3.5 MB maximum)"};
  return {value,mime:match[1],data:match[2]};
}
function conversations(body){
  const arr=body.messages;
  if(!Array.isArray(arr)||!arr.length||arr.length>12)throw {code:400,message:"Send 1–12 conversation messages"};
  let chars=0,images=0;
  const cleaned=arr.map(m=>{
    if(!["user","assistant"].includes(m?.role))throw {code:400,message:"Unsupported role"};
    let content;
    if(Array.isArray(m.content)){
      content=m.content.map(p=>{
        if(p.type==="text"){const t=String(p.text||"").slice(0,5000);chars+=t.length;return {type:"text",text:t}}
        if(p.type==="image_url"){images++;const i=inline(p.image_url?.url,["image/jpeg","image/png","image/webp"]);return {type:"image_url",image_url:{url:i.value}}}
        throw {code:400,message:"Unsupported media input"};
      });
    }else{content=String(m.content||"").slice(0,5000);chars+=content.length}
    return {role:m.role,content};
  });
  if(chars>14000||images>2)throw {code:413,message:"Context too large (14,000 characters / 2 images)"};
  return {messages:cleaned,hasImage:images>0};
}
async function chat(req,res,id,body){
  const messages=conversations(body);
  const all=await catalogue("chat");
  let m=selected(all,body.model);
  if(!m){m=selected(all,"qwen/qwen3.7-flash")||selected(all,"google/gemini-3.1-flash-lite")||all.filter(m=>inputs(m).includes("text")&&outputs(m).includes("text")).sort((a,b)=>cents(a)-cents(b))[0]}
  if(!m||!outputs(m).includes("text")||!inputs(m).includes("text")||(messages.hasImage&&!inputs(m).includes("image")))
    throw {code:400,message:"Choose a compatible text/vision model"};
  modestChat(m);take(id,"chat");
  const r=await upstream("/chat/completions",{method:"POST",data:{
    model:m.id,messages:[{role:"system",content:"You are DragonZpyder AI Mesh. Give useful, precise answers. You may analyse supplied text and images. You have no access to connected accounts or tools; users should switch to Agent for external actions."},...messages.messages],
    max_tokens:700,temperature:0.5,stream:false
  },timeout:90000});
  const payload=await r.json();const answer=payload.choices?.[0]?.message;
  const text=typeof answer?.content==="string"?answer.content:Array.isArray(answer?.content)?answer.content.filter(x=>x.type==="text").map(x=>x.text).join("\n"):"";
  response(res,200,{model:m.id,text:text||"No text was returned.",usage:payload.usage||null,generation_id:payload.id});
}
async function imageGenerate(res,id,body){
  const model=selected(await catalogue("image"),body.model);
  if(!model)throw {code:400,message:"Choose a currently available image model"};
  if(body.confirmed!==true)throw {code:400,message:"Confirm the image generation charge"};
  const prompt=String(body.prompt||"").trim();
  if(!prompt||prompt.length>1600)throw {code:400,message:"Image prompt must be 1–1,600 characters"};
  take(id,"image");
  const r=await upstream("/images",{method:"POST",data:{model:model.id,prompt,n:1,output_format:"png"},timeout:120000});
  const p=await r.json();
  const item=p.data?.[0];const base64=item?.b64_json;
  if(typeof base64!=="string"||base64.length>7*1024*1024)throw {code:502,message:"Provider returned no supported inline image"};
  response(res,200,{model:model.id,image:"data:image/png;base64,"+base64,usage:p.usage||null});
}
async function transcribe(res,id,body){
  const m=selected(await catalogue("chat"),body.model);
  if(!m||!outputs(m).includes("transcription"))throw {code:400,message:"Choose a transcription model"};
  const audio=inline(body.audio,["audio/webm","audio/mpeg","audio/mp4","audio/ogg","audio/wav","audio/flac"]);
  take(id,"transcribe");
  const r=await upstream("/audio/transcriptions",{method:"POST",data:{model:m.id,input_audio:{data:audio.data,format:formats.get(audio.mime)}},timeout:90000});
  const p=await r.json();
  response(res,200,{text:String(p.text||""),model:m.id,usage:p.usage||null});
}
async function speak(res,id,body){
  const m=selected(await catalogue("chat"),body.model);
  if(!m||!outputs(m).includes("speech"))throw {code:400,message:"Choose a speech model"};
  const text=String(body.text||"").trim();
  if(!text||text.length>1200)throw {code:400,message:"Speech text must be 1–1,200 characters"};
  take(id,"speech");
  const data={model:m.id,input:text,response_format:"mp3"};
  if(m.id.startsWith("openai/"))data.voice="alloy";
  const r=await upstream("/audio/speech",{method:"POST",data,timeout:90000});
  const buf=Buffer.from(await r.arrayBuffer());
  if(buf.length>4*1024*1024)throw {code:502,message:"Audio result exceeded safe output limit"};
  response(res,200,{model:m.id,audio:"data:audio/mpeg;base64,"+buf.toString("base64")});
}
function sign(id,session,until){
  return createHmac("sha256",key()).update(session+"|"+id+"|"+until).digest("hex");
}
function verify(job,id,session,url){
  const until=Number(url.searchParams.get("until")),mac=url.searchParams.get("proof")||"";
  if(!Number.isSafeInteger(until)||until<Date.now()||until>Date.now()+26*3600000)throw {code:403,message:"Video access expired"};
  if(!/^[a-f0-9]{64}$/.test(mac)||!same(mac,sign(id,session,until)))throw {code:403,message:"Video job does not belong to this session"};
}
async function video(res,id,body){
  if(process.env.MESH_ENABLE_VIDEO!=="true")throw {code:403,message:"Video generation is disabled until a strict provider spending limit is configured"};
  if(body.confirmed!==true)throw {code:400,message:"Confirm video generation cost first"};
  const m=selected(await catalogue("video"),body.model);
  if(!m)throw {code:400,message:"Choose a video model"};
  const prompt=String(body.prompt||"").trim();
  if(!prompt||prompt.length>900)throw {code:400,message:"Video prompt must be 1–900 characters"};
  const durations=(m.supported_durations||[]).filter(n=>Number.isInteger(n)&&n>0&&n<=5);
  if(!durations.length)throw {code:400,message:"This model does not offer a short, low-cost test duration"};
  const resolutions=(m.supported_resolutions||[]);
  const resolution=resolutions.includes("480p")?"480p":resolutions.includes("720p")?"720p":null;
  if(!resolution)throw {code:400,message:"This model does not offer a low-resolution test"};
  take(id,"video");
  const r=await upstream("/videos",{method:"POST",data:{model:m.id,prompt,duration:durations[0],resolution,aspect_ratio:(m.supported_aspect_ratios||[]).includes("16:9")?"16:9":undefined,generate_audio:false},timeout:30000});
  const p=await r.json();if(!/^[-\w]+$/.test(p.id||""))throw {code:502,message:"Invalid provider video job identifier"};
  const until=Date.now()+24*3600000;
  response(res,202,{id:p.id,status:p.status,model:m.id,until,proof:sign(p.id,id,until)});
}
async function getVideo(req,res,id,url,jobId,isContent){
  if(!/^[-\w]+$/.test(jobId)||jobId.length>150)throw {code:400,message:"Invalid video job"};
  verify(jobId,id,id,url);
  if(isContent){
    const upstreamResponse=await fetch(BASE+"/videos/"+encodeURIComponent(jobId)+"/content?index=0",{
      headers:{authorization:"Bearer "+key()},signal:AbortSignal.timeout(120000)});
    if(!upstreamResponse.ok)throw {code:502,message:"Video content unavailable"};
    const type=upstreamResponse.headers.get("content-type")||"video/mp4";
    if(!type.startsWith("video/"))throw {code:502,message:"Unexpected video content"};
    res.writeHead(200,{"content-type":type,"cache-control":"private,no-store","x-content-type-options":"nosniff","content-disposition":"inline"});
    for await(const chunk of upstreamResponse.body){if(!res.write(chunk))await new Promise(resolve=>res.once("drain",resolve))}
    res.end();return;
  }
  const p=await (await upstream("/videos/"+encodeURIComponent(jobId),{timeout:20000})).json();
  response(res,200,{id:p.id,status:p.status,error:p.error||null,usage:p.usage||null});
}
export async function handleMesh(req,res,url,operly){
  try{
    const mutating=req.method==="POST";
    const id=await identity(req,operly,mutating);
    const route=url.pathname;
    if(req.method==="GET"&&route==="/mesh/models"){const d=await catalogList();return response(res,200,d)}
    if(req.method==="GET"&&route.startsWith("/mesh/video/")){
      const parts=route.split("/").filter(Boolean);
      if(parts.length===3||parts.length===4&&parts[3]==="content")
        return await getVideo(req,res,id,url,parts[2],parts.length===4);
    }
    if(req.method!=="POST")return error(res,405,"Unsupported method");
    if(!["/mesh/chat","/mesh/image","/mesh/transcribe","/mesh/speech","/mesh/video"].includes(route))return error(res,404,"Unknown Mesh endpoint");
    if(!process.env.OPENROUTER_API_KEY)return error(res,503,"OpenRouter is not configured");
    const data=await jsonBody(req);
    if(route==="/mesh/chat")return await chat(req,res,id,data);
    if(route==="/mesh/image")return await imageGenerate(res,id,data);
    if(route==="/mesh/transcribe")return await transcribe(res,id,data);
    if(route==="/mesh/speech")return await speak(res,id,data);
    if(route==="/mesh/video")return await video(res,id,data);
  }catch(e){
    console.error("AI Mesh request failed",e?.code||e?.message||"unknown");
    if(!res.headersSent)error(res,e?.code>=400&&e?.code<600?e.code:502,String(e?.message||"AI provider unavailable").slice(0,250));
    else res.end();
  }
}
