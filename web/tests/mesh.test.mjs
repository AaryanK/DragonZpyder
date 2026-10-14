import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { handleMesh } from "../mesh-server.mjs";

const originalFetch=globalThis.fetch;
const originalKey=process.env.OPENROUTER_API_KEY;
process.env.OPENROUTER_API_KEY="unit-test-key-not-live";
process.env.MESH_ENABLE_VIDEO="false";
let providerCalls=0;
const providerModels=[
  {id:"qwen/qwen3.7-flash",name:"Qwen3.7 Flash",architecture:{input_modalities:["text","image"],output_modalities:["text"]},pricing:{prompt:"0.00000003",completion:"0.00000013"}},
  {id:"premium/very-costly",architecture:{input_modalities:["text"],output_modalities:["text"]},pricing:{prompt:"0.01",completion:"0.05"}},
  {id:"openai/whisper-large-v3",architecture:{input_modalities:["audio"],output_modalities:["transcription"]},pricing:{prompt:"0.001",completion:"0"}}
];
globalThis.fetch=async function mockFetch(url,options={}){
  const target=String(url);
  if(target.endsWith("/api/auth/sessions")){
    if(!String(options.headers?.cookie||"").includes("operly_csrf=unit-csrf"))return new Response(JSON.stringify({detail:"Unauthorized"}),{status:401});
    return Response.json([{id:"unit-session",current:true,scope:"personal"}]);
  }
  if(target==="https://openrouter.ai/api/v1/models")return Response.json({data:providerModels});
  if(target==="https://openrouter.ai/api/v1/images/models")return Response.json({data:[]});
  if(target==="https://openrouter.ai/api/v1/videos/models")return Response.json({data:[]});
  if(target==="https://openrouter.ai/api/v1/chat/completions"){
    providerCalls++;
    const body=JSON.parse(options.body);
    assert.equal(body.model,"qwen/qwen3.7-flash");
    if(body.stream)return new Response('data: {"choices":[{"delta":{"content":"Hello "}}]}\n\ndata: {"choices":[{"delta":{"content":"from stream."}}]}\n\ndata: [DONE]\n\n',{status:200,headers:{"content-type":"text/event-stream"}});
    return Response.json({id:"generation-mock",choices:[{message:{content:"Hello from the mocked model."}}],usage:{total_tokens:24}});
  }
  throw Error("Unexpected external connection: "+target);
};
const app=createServer((req,res)=>{
  const url=new URL(req.url||"/","http://localhost");
  void handleMesh(req,res,url,"http://operly.test");
});
app.listen(0,"127.0.0.1");
await once(app,"listening");
const port=app.address().port,origin="http://127.0.0.1:"+port;
async function call(path,{method="GET",body,csrf="unit-csrf",originHeader=origin,cookie="operly_csrf=unit-csrf"}={}){
 const headers={cookie};
 if(method==="POST"){headers.origin=originHeader;headers["x-csrf-token"]=csrf;headers["content-type"]="application/json";}
 return await originalFetch(origin+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body)});
}
test("Unauthenticated users cannot list models",async()=>{
 const r=await call("/mesh/models",{cookie:""});
 assert.equal(r.status,401);
});
test("Personal sessions see model capabilities without exposing keys",async()=>{
 const r=await call("/mesh/models");assert.equal(r.status,200);
 const data=await r.json();
 assert.equal(data.chat.some(m=>m.id==="qwen/qwen3.7-flash"),true);
 assert.equal(data.videoEnabled,false);
 assert.equal(JSON.stringify(data).includes("unit-test-key"),false);
});
test("Mutating operations require valid CSRF and same origin",async()=>{
 const body={model:"qwen/qwen3.7-flash",messages:[{role:"user",content:"hello"}]};
 assert.equal((await call("/mesh/chat",{method:"POST",body,csrf:"wrong"})).status,403);
 assert.equal((await call("/mesh/chat",{method:"POST",body,originHeader:"https://evil.example"})).status,403);
 assert.equal(providerCalls,0);
});
test("Cheap chat uses the selected model and returns clean results",async()=>{
 const body={model:"qwen/qwen3.7-flash",messages:[{role:"user",content:"hello"}]};
 const r=await call("/mesh/chat",{method:"POST",body});
 assert.equal(r.status,200);
 const p=await r.json();
 assert.equal(p.text,"Hello from the mocked model.");
 assert.equal(providerCalls,2);
});
test("Streams text deltas through the authenticated proxy",async()=>{
 const r=await call("/mesh/chat-stream",{method:"POST",body:{model:"qwen/qwen3.7-flash",messages:[{role:"user",content:"hi"}]}});
 assert.equal(r.status,200);
 const body=await r.text();
 assert.match(body,/Hello /);
 assert.match(body,/from stream/);
 assert.match(body,/"type":"done"/);
 assert.equal(providerCalls,2);
});
test("Expensive models are blocked before provider invocation",async()=>{
 const body={model:"premium/very-costly",messages:[{role:"user",content:"hello"}]};
 const r=await call("/mesh/chat",{method:"POST",body});
 assert.equal(r.status,403);assert.equal(providerCalls,2);
});
test("Video generation is disabled without financial guardrails",async()=>{
 const r=await call("/mesh/video",{method:"POST",body:{model:"any",prompt:"A small flower",confirmed:true}});
 assert.equal(r.status,403);assert.equal(providerCalls,2);
});
test("Rejects malformed image and oversized text inputs",async()=>{
 const body={model:"qwen/qwen3.7-flash",messages:[{role:"user",content:[{type:"image_url",image_url:{url:"javascript:alert(1)"}}]}]};
 const r=await call("/mesh/chat",{method:"POST",body});
 assert.equal(r.status,400);assert.equal(providerCalls,2);
});
test.after(async()=>{
 app.close();await once(app,"close");
 globalThis.fetch=originalFetch;
 if(originalKey===undefined)delete process.env.OPENROUTER_API_KEY;
 else process.env.OPENROUTER_API_KEY=originalKey;
});
