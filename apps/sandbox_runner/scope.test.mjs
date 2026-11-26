import test from "node:test";
import assert from "node:assert/strict";
import {parseScope,verifyScope,parseCreate,parseToolArguments} from "./scope.mjs";
const alice={scopeKind:"personal",principalId:"alice-123",clientSessionId:"run-123"};
const bob={...alice,principalId:"bob-123"};
const expiresAt="2030-01-01T00:00:00Z";
test("personal and workspace scopes never inherit each other's identity",()=>{
  assert.deepEqual(parseScope(alice),{...alice,workspaceId:null});
  assert.throws(()=>parseScope({...alice,workspaceId:"work-123"}));
  assert.throws(()=>parseScope({...alice,scopeKind:"workspace"}));
  assert.throws(()=>parseScope({...alice,unknown:"x"}));
  assert.throws(()=>verifyScope({scope:alice,expiresAt},bob,{now:0}));
  assert.throws(()=>verifyScope({scope:alice,expiresAt},{...alice,clientSessionId:"run-456"},{now:0}));
  assert.throws(()=>verifyScope({scope:alice,expiresAt},{...alice,scopeKind:"workspace",workspaceId:"work-123"},{now:0}));
});
test("expiry fails closed; only authorized cleanup may allow expiry",()=>{
  assert.throws(()=>verifyScope({scope:alice,expiresAt},alice,{now:Date.parse(expiresAt)}));
  assert.throws(()=>verifyScope({scope:alice,expiresAt:"invalid"},alice,{allowExpired:true}));
  assert.throws(()=>verifyScope({scope:alice,expiresAt},bob,{allowExpired:true}));
  assert.equal(verifyScope({scope:alice,expiresAt},alice,{allowExpired:true}).principalId,"alice-123");
});
test("network, deadlines, and unsupported operations fail closed",()=>{
  assert.equal(parseCreate({scope:alice}).networkPolicy,"off");
  assert.throws(()=>parseCreate({scope:alice,networkPolicy:"web"}));
  assert.throws(()=>parseCreate({scope:alice,ttlSeconds:NaN}));
  assert.throws(()=>parseToolArguments("web.fetch",{url:"https://example.org"}));
  assert.throws(()=>parseToolArguments("terminal.exec",{command:"echo ok",background:true}));
  assert.throws(()=>parseToolArguments("terminal.exec",{command:"echo ok",timeout_seconds:900}));
  assert.equal(parseToolArguments("terminal.exec",{command:"echo ok"}).timeout_seconds,30);
});
