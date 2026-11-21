import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { serve } from "../server.mjs";

const nativeFetch = globalThis.fetch;
const vars = Object.fromEntries(["DRAGONZPYDER_RUNTIME_TOKEN","OPENROUTER_API_KEY","DRAGONZPYDER_RUNTIME_ALLOWED_MODELS","DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR"].map(k=>[k,process.env[k]]));
process.env.DRAGONZPYDER_RUNTIME_TOKEN="unit-test-internal-token-at-least-32-bytes";
process.env.OPENROUTER_API_KEY="mock-no-credits";
process.env.DRAGONZPYDER_RUNTIME_ALLOWED_MODELS="openai/gpt-oss-120b";
process.env.DRAGONZPYDER_RUNTIME_CALLS_PER_HOUR="30";
let called=0;
globalThis.fetch=async (url,opts={})=>{
  called++;
  assert.equal(String(url),"https://openrouter.ai/api/v1/chat/completions");
  assert.equal(opts.headers.authorization,"Bearer mock-no-credits");
  const req=JSON.parse(opts.body);
  assert.equal(req.model,"openai/gpt-oss-120b");
  assert.equal(req.stream,false);
  return Response.json({id:"mock-reply",model:req.model,choices:[{message:{role:"assistant",content:'{"ok":true}'}}],usage:{prompt_tokens:23,completion_tokens:4,total_tokens:27}});
};
const app=createServer(serve);
app.listen(0,"127.0.0.1");
await once(app,"listening");
const base="http://127.0.0.1:"+app.address().port;
const call=(path,{method="GET",payload,token="unit-test-internal-token-at-least-32-bytes"}={})=>nativeFetch(base+path,{
  method,
  headers:{"authorization":"Bearer "+token,"content-type":"application/json"},
  body:payload===undefined?undefined:JSON.stringify(payload)
});
test("health works without exposing service secret",async()=>{
  const r=await nativeFetch(base+"/healthz");
  assert.equal(r.status,200);
  const payload=await r.text();
  assert.equal(payload.includes(process.env.DRAGONZPYDER_RUNTIME_TOKEN),false);
});
test("rejects unauthenticated service calls",async()=>{
  assert.equal((await nativeFetch(base+"/v1/models")).status,401);
  assert.equal((await call("/internal/v1/health",{token:"wrong"})).status,401);
  assert.equal(called,0);
});
test("both internal and public-compatible routes expose allowed model IDs",async()=>{
  for(const p of ["/v1/models","/internal/v1/models"]){
    const result=await (await call(p)).json();
    assert.deepEqual(result.data.map(m=>m.id),["openai/gpt-oss-120b"]);
  }
});
test("Operly's existing ChatCompletions contract remains compatible",async()=>{
  const r=await call("/internal/v1/chat/completions",{method:"POST",payload:{model:"openai/gpt-oss-120b",messages:[{role:"user",content:"Reply JSON"}],response_format:{type:"json_object"},max_tokens:300}});
  assert.equal(r.status,200);
  const p=await r.json();
  assert.equal(p.choices[0].message.content,'{"ok":true}');
  assert.equal(p.usage.total_tokens,27);
  assert.equal(called,1);
});
test("public-compatible path is still authenticated and model-restricted",async()=>{
  const request={model:"private/expensive",messages:[{role:"user",content:"Do it"}]};
  assert.equal((await call("/v1/chat/completions",{method:"POST",payload:request})).status,403);
  assert.equal(called,1);
});
test("rejects tool injection, streaming, and unknown routes before model call",async()=>{
  const request={model:"openai/gpt-oss-120b",messages:[{role:"user",content:"Hi"}]};
  assert.equal((await call("/v1/chat/completions",{method:"POST",payload:{...request,tools:[{name:"destroy"}]}})).status,400);
  assert.equal((await call("/v1/chat/completions",{method:"POST",payload:{...request,stream:true}})).status,400);
  assert.equal((await call("/api/auth/sessions")).status,404);
  assert.equal(called,1);
});
test.after(async()=>{
  await new Promise(resolve=>app.close(resolve));
  globalThis.fetch=nativeFetch;
  for(const [key,value] of Object.entries(vars)) if(value===undefined)delete process.env[key];else process.env[key]=value;
});
