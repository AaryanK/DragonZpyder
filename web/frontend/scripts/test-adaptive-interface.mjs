import test from "node:test";
import assert from "node:assert/strict";
import {initialInterface,inspectInterface,patchInterface,resetInterface,DEFAULT_PREFERENCES} from "../src/adaptive-interface.js";
test("atomic multi-property patch, revision, inspect and reset",()=>{
  const initial=initialInterface();
  const next=patchInterface(initial,{expectedRevision:0,changes:{accent:"blue",font:"serif",messageSize:18,contentWidth:"wide",motion:"reduced"}});
  assert.equal(next.revision,1);
  assert.equal(inspectInterface(next).preferences.messageSize,18);
  assert.equal(initial.preferences.accent,"default");
  assert.equal(resetInterface(next).revision,2);
  assert.deepEqual(resetInterface(next).preferences,DEFAULT_PREFERENCES);
  assert.equal(resetInterface(initial),initial);
});
test("reject untrusted, stale and mixed valid/invalid patches without mutation",()=>{
  const state=initialInterface();
  for(const changes of [
    {accent:"url(https://evil.example)"},{font:"<script>"},{messageSize:200},
    {contentWidth:"100vw"},{hideApprovals:true},{identity:"admin"},
    {accent:"blue",permission:"admin"},JSON.parse('{"__proto__":{"admin":true}}'),
    {constructor:"blue"},{},null,["blue"]
  ]) assert.throws(()=>patchInterface(state,{expectedRevision:0,changes}));
  assert.throws(()=>patchInterface(state,{expectedRevision:1,changes:{accent:"blue"}}));
  assert.throws(()=>patchInterface(state,{expectedRevision:0,changes:{accent:"blue"},owner:"someone"}));
  assert.deepEqual(state.preferences,DEFAULT_PREFERENCES);
});
test("semantic snapshots cannot mutate runtime state or security catalog",()=>{
  const state=initialInterface();
  const snapshot=inspectInterface(state);
  snapshot.preferences.accent="blue";
  assert.equal(state.preferences.accent,"default");
  assert.deepEqual(snapshot.components.find(c=>c.id==="approval").properties,[]);
  assert.throws(()=>snapshot.components.push({id:"unsafe"}));
  assert.throws(()=>snapshot.choices.accent.push("unsafe"));
});
