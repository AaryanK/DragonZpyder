import React,{useCallback,useEffect,useRef,useState} from "react";
import {UiIcon} from "./UiIcon.jsx";

// Owner-scoped readback and explicit cancellation. No guessed progress,
// client scheduling, legacy tool execution, or caller-selected user ID.
const validId=id=>typeof id==="string"&&/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(id);
async function requestGoal(id=null,cancel=false,signal) {
  if(id!==null&&!validId(id))throw Error("Invalid goal identifier.");
  const headers={Accept:"application/json"};
  if(cancel){
    const cookie=document.cookie.split(";").map(s=>s.trim()).find(s=>s.startsWith("__Host-dz_csrf="));
    if(!cookie)throw Error("Secure session missing. Sign in again.");
    headers["X-DZ-CSRF"]=decodeURIComponent(cookie.slice("__Host-dz_csrf=".length));
  }
  const response=await fetch("/dz/v2/personal/goals"+(id?"/"+id:"")+(cancel?"/cancel":""),{method:cancel?"POST":"GET",headers,credentials:"same-origin",cache:"no-store",redirect:"error",signal});
  const result=await response.json().catch(()=>null);
  if(!response.ok||!result)throw Error([404,503].includes(response.status)?"Goal management is unavailable for this session.":typeof result?.detail==="string"?result.detail:"Goal request could not be completed.");
  return result;
}
const stamp=v=>typeof v==="string"&&Number.isFinite(Date.parse(v))?new Date(v).toLocaleString():"Time unavailable";
const label=v=>typeof v==="string"&&v?v.replace(/_/g," "):"Unknown";
export function NativeGoals(){
  const [goals,setGoals]=useState([]),[detail,setDetail]=useState(null),[selected,setSelected]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState(""),[cancelTarget,setCancelTarget]=useState(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState("");
  const list=useRef(null),lookup=useRef(null),mounted=useRef(true);
  const refresh=useCallback(async()=>{
    list.current?.abort();const c=new AbortController();list.current=c;
    setLoading(true);setError("");
    try{const r=await requestGoal(null,false,c.signal);if(!Array.isArray(r.goals))throw Error("Invalid goal list.");if(!c.signal.aborted)setGoals(r.goals.filter(g=>validId(g.goal_id)));}
    catch(err){if(!c.signal.aborted){setGoals([]);setError(err.message);}}
    finally{if(!c.signal.aborted)setLoading(false);}
  },[]);
  useEffect(()=>{mounted.current=true;void refresh();return()=>{mounted.current=false;list.current?.abort();lookup.current?.abort();};},[refresh]);
  async function inspect(id){
    lookup.current?.abort();const c=new AbortController();lookup.current=c;
    setSelected(id);setDetail(null);setError("");
    try{const r=await requestGoal(id,false,c.signal);if(r.goal_id!==id)throw Error("Goal detail did not match request.");if(!c.signal.aborted)setDetail(r);}
    catch(err){if(!c.signal.aborted)setError(err.message);}
  }
  async function cancel(){
    const id=cancelTarget;if(!validId(id)||busy)return;
    setBusy(true);setError("");setNotice("");
    try{const r=await requestGoal(id,true);if(r.goal_id!==id||r.state!=="cancelled")throw Error("Cancellation was not confirmed.");if(!mounted.current)return;setCancelTarget(null);setNotice("Cancellation confirmed by DragonZpyder.");await refresh();if(mounted.current&&selected===id)await inspect(id);}
    catch(err){if(mounted.current)setError(err.message);}
    finally{if(mounted.current)setBusy(false);}
  }
  const progress=g=>Number.isInteger(g.completed_wakes)&&Number.isInteger(g.total_wakes)&&g.total_wakes>0&&g.completed_wakes>=0&&g.completed_wakes<=g.total_wakes;
  return <div className="dz-center-stack">
    <div className="dz-center-intro"><h2>Tasks &amp; goals</h2><p>View persistent Personal goals and recorded execution receipts. Progress comes from the service.</p></div>
    <div className="dz-center-section-header"><h3>Your goals</h3><button type="button" disabled={loading||busy} onClick={()=>void refresh()}>Refresh</button></div>
    {loading&&<p role="status">Loading goals…</p>}{error&&<div className="dz-center-error" role="alert">{error}</div>}{notice&&<p className="dz-center-info" role="status">{notice}</p>}
    {!loading&&!error&&!goals.length&&<div className="dz-center-empty"><strong>No goals found</strong><p>No persistent goals were returned for your Personal account.</p></div>}
    {goals.length>0&&<div className="dz-center-list">{goals.map(g=><article className="dz-center-row" key={g.goal_id}><span className="dz-center-provider"><UiIcon name="tasks"/></span><div className="dz-center-row-body"><strong>Goal {g.goal_id.slice(0,8)}</strong><small>{label(g.state)} · {stamp(g.updated_at)}</small>
    {progress(g)&&<><progress aria-label="Completed scheduled wakes" value={g.completed_wakes} max={g.total_wakes}/><small>{g.completed_wakes} of {g.total_wakes} scheduled wakes</small></>}{g.state==="blocked"&&g.blocked_reason&&<p>{g.blocked_reason}</p>}</div>
    <div className="dz-center-row-actions"><button type="button" onClick={()=>void inspect(g.goal_id)}>Details</button>{["preparing","active"].includes(g.state)&&<button type="button" disabled={busy} onClick={()=>setCancelTarget(g.goal_id)}>Cancel goal</button>}</div></article>)}</div>}
    {cancelTarget&&<section className="dz-center-info" aria-label="Confirm goal cancellation"><strong>Cancel this goal?</strong><p>This requests cancellation of future goal wakes. Completed actions are not undone.</p><div className="dz-center-row-actions"><button type="button" disabled={busy} onClick={()=>setCancelTarget(null)}>Keep goal</button><button type="button" disabled={busy} onClick={()=>void cancel()}>Confirm cancellation</button></div></section>}
    {selected&&<section className="dz-center-detail" aria-label="Goal execution details"><div className="dz-center-section-header"><h3>Execution receipts</h3><button type="button" onClick={()=>{lookup.current?.abort();setSelected(null);setDetail(null);}}>Close details</button></div>{detail?<><p>{label(detail.state)}</p>{Array.isArray(detail.receipts)&&detail.receipts.length?detail.receipts.map((r,i)=><div className="dz-center-row" key={i}><div className="dz-center-row-body"><strong>Wake {r.sequence} · {label(r.status)}</strong><small>{stamp(r.at)}</small>{Array.isArray(r.tool_names)&&<p>{r.tool_names.join(", ")}</p>}</div></div>):<p>No execution receipts returned.</p>}</>:!error&&<p role="status">Loading execution details…</p>}</section>}
    <p className="dz-center-fineprint">Goal identifiers and scheduled wakes reflect the existing API. Task creation and editable scheduling require additional backend contracts.</p>
  </div>;
}
