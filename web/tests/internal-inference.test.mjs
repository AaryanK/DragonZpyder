import test from "node:test";
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {once} from "node:events";
import {handleInternalInference} from "../internal-inference.mjs";
const oldFetch=globalThis.fetch,oldToken=process.env.DRAGONZPYDER_RUNTIME_TOKEN,oldKey=process.env.OPENROUTER_API_KEY;
process.env.DRAGONZPYDER_RUNTIME_TOKEN="test-internal-service-token-1234567890-secret";
process.env.OPENROUTER_API_KEY="fake-model-key";
let upstreamCalls=0;
globalThis.fetch=async (url,options)=>{
  assert.equal(url,"https://openrouter.ai/api/v1/chat/completions");
  upstreamCalls++;
  const body=JSON.parse(options.body);
  assert.equal(body.model,"openai/gpt-oss-120b");
  return Response.json({id:"completion_1",choices:[{message:{role:"assistant",content:"Answer from DragonZpyder"}}],usage:{total_tokens:33}});
};
const http=createServer((req,res)=>{void handleInternalInference(req,res,new URL(req.url,"http://localhost"))});
http.listen(0,"127.0.0.1");await once(http,"listening");
const base="http://127.0.0.1:"+http.address().port;
const call=(path,options={})=>oldFetch(base+path,{headers:{authorization:"Bearer "+(options.token||"test-internal-service-token-1234567890-secret"),"content-type":"application/json"},method:options.method||"GET",body:options.body?JSON.stringify(options.body):undefined});
test("Blocks missing and invalid service credentials",async()=>{
 const r=await call("/internal/v1/health",{token:"invalid"});assert.equal(r.status,401);
 const raw=await oldFetch(base+"/internal/v1/models");assert.equal(raw.status,401);
});
test("Offers scoped service health and model registry",async()=>{
 const r=await call("/internal/v1/health");assert.equal(r.status,200);
 const v=await r.json();assert.equal(v.service,"dragonzpyder-inference");
 const models=await(await call("/internal/v1/models")).json();
 assert.deepEqual(models.data.map(x=>x.id),["openai/gpt-oss-120b"]);
});
test("Operly-compatible inference succeeds with structured responses",async()=>{
 const r=await call("/internal/v1/chat/completions",{method:"POST",body:{model:"openai/gpt-oss-120b",messages:[{role:"system",content:"Do good."},{role:"user",content:"Give JSON"}],response_format:{type:"json_object"},max_tokens:200}});
 assert.equal(r.status,200);const d=await r.json();assert.equal(d.choices[0].message.content,"Answer from DragonZpyder");assert.equal(d.usage.total_tokens,33);assert.equal(upstreamCalls,1);
});
test("Rejects an unauthorised costly model before OpenRouter",async()=>{
 const r=await call("/internal/v1/chat/completions",{method:"POST",body:{model:"premium/opus",messages:[{role:"user",content:"test"}]}});
 assert.equal(r.status,403);assert.equal(upstreamCalls,1);
});
test("Rejects tool injections and malformed requests",async()=>{
 const r=await call("/internal/v1/chat/completions",{method:"POST",body:{model:"openai/gpt-oss-120b",messages:[{role:"user",content:"hi"}],tools:[{type:"function",name:"danger"}]}});
 assert.equal(r.status,400);assert.equal(upstreamCalls,1);
});
test.after(async()=>{
 http.close();await once(http,"close");
 globalThis.fetch=oldFetch;
 if(oldToken===undefined)delete process.env.DRAGONZPYDER_RUNTIME_TOKEN;else process.env.DRAGONZPYDER_RUNTIME_TOKEN=oldToken;
 if(oldKey===undefined)delete process.env.OPENROUTER_API_KEY;else process.env.OPENROUTER_API_KEY=oldKey;
});
