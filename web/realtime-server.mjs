import { createHash, timingSafeEqual } from "node:crypto";
const counts=new Map();
function json(res,status,message){
  res.writeHead(status,{"content-type":"application/json; charset=utf-8","cache-control":"no-store"});
  res.end(JSON.stringify({detail:{message}}));
}
function cookies(header){
  const map=new Map();
  for(const bit of String(header||"").split(";")){
    const i=bit.indexOf("=");if(i<0)continue;
    try{map.set(bit.slice(0,i).trim(),decodeURIComponent(bit.slice(i+1).trim()))}
    catch{map.set(bit.slice(0,i).trim(),bit.slice(i+1).trim())}
  }
  return map;
}
function same(a,b){
  const x=Buffer.from(String(a||"")),y=Buffer.from(String(b||""));
  return x.length>0&&x.length===y.length&&timingSafeEqual(x,y);
}
async function readOffer(req){
  let n=0;const parts=[];
  for await(const part of req){n+=part.length;if(n>65536)throw Error("Too big");parts.push(part)}
  const sdp=Buffer.concat(parts).toString("utf8");
  if(!sdp.startsWith("v=0")||!sdp.includes("\nm=audio "))throw Error("Invalid SDP");
  return sdp;
}
export async function handleCompanionRealtime(req,res,operly){
  if(req.method!=="POST")return json(res,405,"POST required");
  let origin;try{origin=new URL(String(req.headers.origin||""))}catch{return json(res,403,"Same-origin request required")}
  if(origin.host!==req.headers.host||!["http:","https:"].includes(origin.protocol))return json(res,403,"Same-origin request required");
  if(origin.protocol!=="https:"&&!["localhost","127.0.0.1"].includes(origin.hostname))return json(res,403,"HTTPS required");
  const jar=cookies(req.headers.cookie),csrf=req.headers["x-csrf-token"];
  if(!same(csrf,jar.get("__Host-operly_csrf"))&&!same(csrf,jar.get("operly_csrf")))return json(res,403,"Session security token missing");
  if(!/^application\/sdp(?:\s*;|$)/i.test(String(req.headers["content-type"]||"")))return json(res,415,"Expected application/sdp");
  if(Number(req.headers["content-length"]||0)>65536)return json(res,413,"SDP offer too large");
  if(!process.env.OPENAI_API_KEY)return json(res,503,"Live voice is not configured");
  try{
    const auth=await fetch(operly+"/api/auth/sessions",{headers:{cookie:String(req.headers.cookie||""),origin:operly,referer:operly+"/",accept:"application/json"},signal:AbortSignal.timeout(10000)});
    if(!auth.ok)return json(res,401,"Sign in to DragonZpyder Personal");
    const sessions=await auth.json();
    if(!Array.isArray(sessions)||!sessions.some(s=>s?.current&&s?.scope==="personal"))return json(res,403,"Personal session required");
  }catch(e){console.error("Realtime auth error",e?.message);return json(res,502,"Unable to verify Personal session")}
  let sdp;try{sdp=await readOffer(req)}catch{return json(res,400,"Invalid SDP offer")}
  const user=createHash("sha256").update(String(req.headers.cookie)).digest("hex"),now=Date.now(),prev=counts.get(user);
  const max=Math.max(1,Math.min(30,Number(process.env.REALTIME_SESSIONS_PER_HOUR)||6));
  if(prev&&prev.until>now&&prev.count>=max)return json(res,429,"Voice session limit reached");
  counts.set(user,{until:prev?.until>now?prev.until:now+3600000,count:prev?.until>now?prev.count+1:1});
  if(counts.size>5000)for(const [k,v] of counts)if(v.until<now)counts.delete(k);
  const form=new FormData();form.set("sdp",sdp);
  form.set("session",JSON.stringify({
    type:"realtime",model:process.env.OPENAI_REALTIME_MODEL||"gpt-realtime-2.1",
    instructions:"You are DragonZpyder, a friendly and efficient realtime voice companion. Speak naturally and allow interruptions. If the user asks you to take action through connected apps, use delegate_personal_task, which goes through existing Operly permissions and approvals. Never claim a task completed without confirmation. Pending approvals require human review in the Personal workspace. Do not pretend to see the screen.",
    audio:{input:{turn_detection:{type:"server_vad",create_response:true,interrupt_response:true},transcription:{model:"gpt-4o-mini-transcribe"}},output:{voice:"marin"}},
    tools:[{type:"function",name:"delegate_personal_task",description:"Send an authorised personal task to the existing Operly agent. Does not approve consequential actions.",parameters:{type:"object",properties:{request:{type:"string"}},required:["request"],additionalProperties:false}}]
  }));
  try{
    const r=await fetch("https://api.openai.com/v1/realtime/calls",{method:"POST",headers:{authorization:"Bearer "+process.env.OPENAI_API_KEY,"OpenAI-Safety-Identifier":user.slice(0,32)},body:form,signal:AbortSignal.timeout(30000)});
    const answer=await r.text();
    if(!r.ok){console.error("Realtime API error",r.status);return json(res,502,"Voice provider refused session ("+r.status+")")}
    res.writeHead(200,{"content-type":"application/sdp","cache-control":"no-store","x-content-type-options":"nosniff"});res.end(answer);
  }catch(e){console.error("Realtime setup error",e?.message);json(res,502,"Could not establish live voice")}
}
