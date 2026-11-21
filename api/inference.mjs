/**
 * DragonZpyder private model inference gateway.
 * Client: authorised backend services (e.g. Operly), NOT browsers.
 * Operly retains its workspace and Personal execution-policy boundary.
 */
import { timingSafeEqual } from "node:crypto";

const API = "https://openrouter.ai/api/v1";
const buckets = new Map();
const routeOf = path => path.startsWith("/internal/v1/") ? path.slice("/internal".length) : path;
const MAX_BYTES = 160_000;
function send(res,status,value) {
  const body=JSON.stringify(value);
  res.writeHead(status,{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"});
  res.end(body);
}
function deny(res,status,message){send(res,status,{error:{message,type:"dragonzpyder_inference_error",code:status}})}
function equals(a,b) {
  const x=Buffer.from(String(a||"")),y=Buffer.from(String(b||""));
  return x.length>0&&x.length===y.length&&timingSafeEqual(x,y);
}
function authorised(req){
  const secret=process.env.DRAGONZPYDER_RUNTIME_TOKEN;
  if(!secret||secret.length<32)return false;
  const auth=String(req.headers.authorization||"");
  return auth.startsWith("Bearer ")&&equals(auth.slice(7),secret);
}
function permittedModels(){
  // A fixed operator-controlled allowlist prevents arbitrary costly model invocation.
  const raw=process.env.DRAGONZPYDER_RUNTIME_ALLOWED_MODELS || "openai/gpt-oss-120b";
  return [...new Set(raw.split(",").map(x=>x.trim()).filter(x=>/^[a-zA-Z0-9_.:/-]{3,100}$/.test(x)))].slice(0,20);
}
function perHourAllowed(){
  const key="operly",now=Date.now();
  const old=buckets.get(key);
  const next=old&&old.until>now?old:{n:0,until:now+3600000};
  const max=Math.min(1000,Math.max(1,Number(process.env.DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR)||120));
  if(next.n>=max)return false;
  next.n++;buckets.set(key,next);return true;
}
async function parseRequest(req){
  const chunks=[];let bytes=0;
  for await(const chunk of req){bytes+=chunk.length;if(bytes>MAX_BYTES)throw {status:413,message:"Request payload exceeds 160 KB"};chunks.push(chunk)}
  let payload;
  try{payload=JSON.parse(Buffer.concat(chunks).toString("utf8"))}
  catch{throw {status:400,message:"Invalid JSON request"}}
  if(!payload||typeof payload!=="object"||Array.isArray(payload))throw {status:400,message:"Invalid request"};
  const models=permittedModels();
  if(!models.includes(payload.model))throw {status:403,message:"Selected model is not enabled by DragonZpyder"};
  const messages=payload.messages;
  if(!Array.isArray(messages)||messages.length<1||messages.length>24)throw {status:400,message:"Invalid message count"};
  let totalChars=0;
  const safe=messages.map(item=>{
    if(!item||!["system","developer","user","assistant"].includes(item.role)||typeof item.content!=="string")
      throw {status:400,message:"Unsupported role or message content"};
    if(item.content.length>30000)throw {status:413,message:"Individual message is too long"};
    totalChars+=item.content.length;
    return {role:item.role,content:item.content};
  });
  if(totalChars>100000)throw {status:413,message:"Conversation exceeds model input budget"};
  const maxTokens=Number(payload.max_tokens??1200);
  if(!Number.isInteger(maxTokens)||maxTokens<1||maxTokens>4096)throw {status:400,message:"Output token limit must be 1–4096"};
  if(payload.tools||payload.tool_choice||payload.stream)throw {status:400,message:"Tool calling and streaming require separate scoped APIs"};
  const temperature=payload.temperature===undefined?0.2:Number(payload.temperature);
  if(!Number.isFinite(temperature)||temperature<0||temperature>1.5)throw {status:400,message:"Unsupported temperature"};
  const out={model:payload.model,messages:safe,max_tokens:maxTokens,temperature,stream:false};
  if(payload.response_format!==undefined){
    if(payload.response_format?.type!=="json_object")throw {status:400,message:"Only json_object response format is supported"};
    out.response_format={type:"json_object"};
  }
  return out;
}
export async function handleInternalInference(req,res,url){
  if(!authorised(req))return deny(res,401,"Service authentication required");
  const route = routeOf(url.pathname);
  if(req.method==="GET"&&route==="/v1/health")
    return send(res,200,{service:"dragonzpyder-inference",status:process.env.OPENROUTER_API_KEY?"ready":"unconfigured",models:permittedModels().length});
  if(req.method==="GET"&&route==="/v1/models")
    return send(res,200,{object:"list",data:permittedModels().map(id=>({id,object:"model",owned_by:"dragonzpyder"}))});
  if(req.method!=="POST"||route!=="/v1/chat/completions")return deny(res,405,"Unsupported inference endpoint");
  if(!/^application\/json(?:\s*;|$)/i.test(String(req.headers["content-type"]||"")))return deny(res,415,"JSON request required");
  if(!process.env.OPENROUTER_API_KEY)return deny(res,503,"Inference provider is not configured");
  try{
    const body=await parseRequest(req);
    if(!perHourAllowed())return deny(res,429,"DragonZpyder internal inference test quota reached");
    const upstream=await fetch(API+"/chat/completions",{
      method:"POST",headers:{
        authorization:"Bearer "+process.env.OPENROUTER_API_KEY,
        "content-type":"application/json",
        "HTTP-Referer":"https://dragonzpyder.xyz",
        "X-Title":"DragonZpyder Runtime"
      },body:JSON.stringify(body),signal:AbortSignal.timeout(90000)
    });
    if(!upstream.ok){
      // Avoid leaking upstream response bodies or keys to the caller or logs.
      console.error("DragonZpyder inference upstream response",upstream.status);
      return deny(res,upstream.status===429?429:upstream.status===400?400:502,
        upstream.status===429?"Inference budget or rate limit reached":"Model provider rejected the request");
    }
    const data=await upstream.json();
    if(!Array.isArray(data.choices)||typeof data.choices[0]?.message?.content!=="string")
      return deny(res,502,"Model provider returned unexpected content");
    const text=data.choices[0].message.content;
    if(Buffer.byteLength(text,"utf8")>90000)return deny(res,502,"Model response exceeded output size limit");
    // Compatible with Operly's existing /chat/completions inference adapter.
    send(res,200,{
      id:String(data.id||""),object:"chat.completion",
      model:String(data.model||body.model),
      choices:[{index:0,message:{role:"assistant",content:text},finish_reason:data.choices[0].finish_reason||"stop"}],
      usage:data.usage||undefined
    });
  }catch(e){
    console.error("DragonZpyder inference request failed",e?.status||e?.name||"error");
    deny(res,Number(e?.status)||502,e?.status?String(e.message):"Inference service unavailable");
  }
}
