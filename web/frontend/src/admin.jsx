import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./design-tokens.css";
import "./admin.css";

function formatInteger(value) {
  return value === null || value === undefined ? "Unknown" : Number(value).toLocaleString();
}
function formatUsd(value) {
  return value === null || value === undefined ? "Unknown" : "$" + Number(value).toFixed(6);
}

function OpsTable({ title, rows, columns }) {
  return <section className="table-box"><h2>{title}</h2><div className="table-scroll">
    <table><thead><tr>{columns.map(([key,label]) => <th key={key}>{label}</th>)}</tr></thead>
      <tbody>{rows.map((row,i) => <tr key={i}>{columns.map(([key]) => <td key={key}>{row[key] == null ? "Unknown" : String(row[key])}</td>)}</tr>)}
        {!rows.length && <tr><td colSpan={columns.length}>No records returned.</td></tr>}</tbody></table></div></section>;
}
function Distribution({title, values}) {
  const entries = Object.entries(values || {}).sort((a,b)=>b[1]-a[1]);
  const max = Math.max(1,...entries.map(x=>x[1]));
  return <section className="table-box"><h2>{title}</h2>{entries.length ? entries.map(([name,count]) =>
    <div className="ops-bar" key={name}><span>{name}</span><meter min={0} max={max} value={count}/><strong>{count}</strong></div>
  ) : <p>No records returned.</p>}</section>;
}


function SeriesChart({title, rows, field, unit=""}) {
  const data=(rows||[]).filter(r=>typeof r[field]==="number" && Number.isFinite(r[field]));
  const width=680,height=164,left=56,right=12,top=16,bottom=28;
  const max=Math.max(0.000001,...data.map(r=>r[field]));
  const x=i=>left+i*(width-left-right)/Math.max(1,data.length-1);
  const y=v=>top+(1-v/max)*(height-top-bottom);
  const labels=data.length?[data[0],data[data.length-1]]:[];
  const timestamp=r=>r.day||new Date(r.ts*1000).toLocaleString();
  return <section className="table-box"><h2>{title}</h2>
    {data.length ? <><svg className="ops-series" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title+" trend"}>
      {[0,.5,1].map(t=><g key={t}><line x1={left} x2={width-right} y1={y(max*t)} y2={y(max*t)} className="ops-gridline"/><text x={left-7} y={y(max*t)+4} textAnchor="end">{Number((max*t).toPrecision(3))}</text></g>)}
      <polyline points={data.map((r,i)=>x(i)+","+y(r[field])).join(" ")} className="ops-line"/>
      {data.length===1&&<circle cx={x(0)} cy={y(data[0][field])} r="4" className="ops-point"/>}
      <text x={left} y={height-6}>{timestamp(labels[0])}</text><text x={width-right} y={height-6} textAnchor="end">{timestamp(labels[1])}</text>
    </svg><p className="data-note">{data.length} reported samples{unit?" · "+unit:""}; missing intervals are not inferred as zero.</p></> : <p>No reported samples.</p>}
  </section>;
}
function ResourceMetrics({data}) {
  const [service,setService]=useState("");
  const names=[...new Set((data.metrics||[]).map(r=>r.service))];
  const selected=names.includes(service)?service:names[0]||"";
  const metrics=(data.metrics||[]).filter(r=>r.service===selected);
  return <><p className="data-note">Railway provider-reported metrics; last reported sample may not be current. Network values are sample quantities, not billed cost.</p>
    <OpsTable title="Service resource summary" rows={data.metrics||[]} columns={[["service","Service"],["measurement","Measurement"],["current","Latest"],["average","Mean"],["maximum","Maximum"]]}/>
    {names.length>0&&<label className="data-note">Service detail <select value={selected} onChange={e=>setService(e.target.value)}>{names.map(n=><option key={n}>{n}</option>)}</select></label>}
    <div className="ops-distributions">{metrics.map(m=><SeriesChart key={m.measurement} title={m.measurement+" · "+m.service} rows={m.samples} field="value"/>)}</div>
  </>;
}
function TrafficHistory({report}) {
  return <><p className="data-note">Historical Railway edge request metrics across deployments for the Web and API services. These are HTTP requests, not unique people or page views. Provider retention and missing intervals limit coverage.</p>
    {(report.services||[]).map(s=><section key={s.service}><h2 className="ops-subtitle">{s.service} · {s.state}</h2>
      {s.state==="available"&&<><section className="stats"><article className="stat"><span>Reported requests</span><strong>{formatInteger(s.total_requests)}</strong></article></section>
        <SeriesChart title="Request counts by time bucket" rows={s.requests} field="value"/>
        <div className="ops-distributions"><Distribution title="Status codes" values={s.status_counts}/><SeriesChart title="P95 request duration" rows={s.latency} field="p95" unit="ms"/></div>
        <OpsTable title="Latency percentiles" rows={(s.latency||[]).map(r=>({...r,time:new Date(r.ts*1000).toLocaleString()}))} columns={[["time","Time"],["p50","P50 (ms)"],["p90","P90 (ms)"],["p95","P95 (ms)"],["p99","P99 (ms)"]]}/>
      </>}
    </section>)}</>;
}

function Activity({report}) {
  if (!report) return null;
  const data=report;
  const groups=[["requests","Request states"],["workflows","Native workflow states"],["goals","Personal MCP goal states"]];
  const con=data.conversations?.rows?.[0], mem=data.memory?.rows?.[0];
  const accounts=data.identity?.accounts, sessions=data.identity?.sessions;
  return <>
    <p className="data-note">Identity inventory and native request activity over {data.days} days. Account and live-session totals are current snapshots, not period counts. Workflow groups include current active or uncertain records even if older.</p>
    <h2 className="ops-subtitle">Accounts and sessions · {data.identity?.state||"unavailable"}</h2>
    <section className="stats">{[["Registered non-test accounts",accounts?.total_accounts],["Enabled accounts",accounts?.active_accounts],["Pending accounts",accounts?.pending_accounts],["Disabled accounts",accounts?.disabled_accounts],["Native signups in period",accounts?.native_signups],["Unexpired sessions",sessions?.live_sessions],["Accounts with unexpired sessions",sessions?.session_holders],["Distinct request owners in period",data.request_owners?.rows?.[0]?.distinct_request_owners]].map(([label,value])=>
      <article className="stat" key={label}><span>{label}</span><strong>{formatInteger(value)}</strong></article>)}</section>
    <p className="data-note">Registered includes pending imported accounts. Native signups exclude imports and operator tests. An unexpired session is not an online user or unique device. Request owners may include test activity. For request-level device and browser estimates, see Recent traffic. Visitor country and acquisition attribution are not collected by these stores.</p>
    <h2 className="ops-subtitle">Product usage</h2>
    <section className="stats">{[["Active conversations",con?.active_conversations],["Conversation owners",con?.conversation_owners],["New saved memory entries",mem?.saved_entries],["Memory owners (new entries)",mem?.memory_owners],["New recall-enabled entries",mem?.recall_enabled_entries]].map(([label,value])=>
      <article className="stat" key={label}><span>{label}</span><strong>{formatInteger(value)}</strong></article>)}</section>
    <div className="ops-distributions">{groups.map(([key,label])=><Distribution key={key} title={label+" · "+(data[key]?.state||"unavailable")} values={Object.fromEntries((data[key]?.rows||[]).map(r=>[r.state||r.status,r.count]))}/>)}</div>
    <Distribution title={"Requests by UTC day · "+(data.daily?.state||"unavailable")} values={Object.fromEntries((data.daily?.rows||[]).map(r=>[r.day,r.requests]))}/>
    <OpsTable title="Daily activity (UTC)" rows={data.daily?.rows||[]} columns={[["day","Day"],["requests","Accepted requests"],["active_users","Distinct request owners"],["completed","Completed"]]}/>
    <OpsTable title="Runtime initialization" rows={Object.entries(data.runtime||{}).map(([name,enabled])=>({name,status:enabled?"Ready / initialized":"Not ready / not initialized"}))} columns={[["name","Component"],["status","Reported state"]]}/>
    <p className="data-note">Capability values indicate configuration eligibility, not proof of end-to-end execution.</p>
    <OpsTable title="Capability configuration" rows={Object.entries(data.capabilities||{}).map(([name,enabled])=>({name,status:enabled?"Enabled":"Disabled"}))} columns={[["name","Capability"],["status","Configured"]]}/>
  </>;
}

function Configuration({report,onRefresh}) {
  const [message,setMessage]=useState(""), [busy,setBusy]=useState(false);
  const [service,setService]=useState("API");
  const live=service==="API"?report.api_runtime:service==="Web"?report.web_runtime:null;
  const desired=report.desired?.[service];
  const keys=[...new Set([...Object.keys(live?.flags||{}),...Object.keys(desired?.flags||{})])];
  async function change(flag,current,enabled) {
    if(!window.confirm("Change "+flag+" on "+service+" in production? Railway may redeploy the service. Existing data is not deleted.")) return;
    const csrf=document.cookie.split("; ").find(x=>x.startsWith("__Host-dz_csrf="))?.split("=").slice(1).join("=")||"";
    setBusy(true);setMessage("");
    try {
      const r=await fetch("/admin/api/config",{method:"POST",credentials:"same-origin",cache:"no-store",
        headers:{"content-type":"application/json","x-dz-csrf":csrf},
        body:JSON.stringify({service,flag,expected:current,enabled,confirm:true})});
      const data=await r.json(); if(!r.ok)throw Error(data.detail||"Change unavailable");
      setMessage(data.message);onRefresh();
    } catch(e) {setMessage(e.message);} finally {setBusy(false);}
  }
  return <><p className="data-note">Source-reviewed configuration gates. Live values come from the running process; desired values come from Railway. An enabled gate is not a passed capability test. Worker live values are not instrumented. Changes affect new deployments, not existing data.</p>
    <OpsTable title="Railway integrations" rows={Object.entries(report.integration||{}).map(([project,present])=>({project,status:present?"Credential present; provider access not proven":"Missing project token"}))} columns={[["project","Project"],["status","Configuration"]]}/>
    <label className="data-note">Service <select value={service} onChange={e=>setService(e.target.value)}>{["API","Web","Worker"].map(s=><option key={s}>{s}</option>)}</select></label>
    <p className="data-note">Running commit: {live?.deployed_sha||"Unknown"} · Railway desired state: {desired?.state||"unavailable"}</p>
    {message&&<p role="status">{message}</p>}
    <section className="table-box"><h2>Capability gates</h2><div className="table-scroll"><table><thead><tr><th>Source gate</th><th>Running</th><th>Railway desired</th><th>Control</th></tr></thead><tbody>{keys.map(flag=>{
      const current=desired?.flags?.[flag];
      const editable=report.editable?.[service]?.includes(flag)&&["on","off","unset"].includes(current);
      return <tr key={flag}><td>{flag.replace("DRAGONZPYDER_","")}</td><td>{live?.flags?.[flag]||"Unknown"}</td><td>{current||"Unknown"}</td><td>{editable?<><button disabled={busy||current==="on"} onClick={()=>change(flag,current,true)}>Enable</button>{" "}<button disabled={busy||current==="off"} onClick={()=>change(flag,current,false)}>Disable</button></>: "Read only"}</td></tr>;
    })}</tbody></table></div></section>
    <p className="data-note">Memory recall controls access by the chat agent, not saved-memory management or consent. API search controls do not alter Worker monitor registration. Identity, credentials, budget, isolation and coupled workflow settings are intentionally not editable here.</p>
    {service==="API"&&<OpsTable title="Discovered source gate references (running API image)" rows={(live?.source_gates||[]).map(g=>({flag:g.flag,runtime:g.runtime,references:g.references.map(r=>r.path+":"+r.line).join(", ")}))} columns={[["flag","Source flag"],["runtime","Runtime value"],["references","Source references"]]}/>}
    {service==="API"&&<OpsTable title="API dependency presence (not health)" rows={Object.entries(live?.dependencies||{}).map(([name,present])=>({name,status:present?"Present":"Missing"}))} columns={[["name","Dependency"],["status","State"]]}/>}
  </>;
}


function RepositoryInventory({report}) {
  const [query,setQuery]=useState(""), [page,setPage]=useState(0);
  const matches=report.files.filter(f=>f.path.toLowerCase().includes(query.toLowerCase()));
  const pages=Math.max(1,Math.ceil(matches.length/50));
  const selected=Math.min(page,pages-1);
  return <><p className="data-note">GitHub develop tree at <a href={"https://github.com/AaryanK/DragonZpyder/tree/"+report.head} target="_blank" rel="noreferrer">{report.head}</a>. Tracked paths are not proof of implementation or deployment. {report.partial?"Partial tree coverage.":"Complete returned tree."}</p>
    <section className="stats"><article className="stat"><span>Tracked files</span><strong>{formatInteger(report.total_files)}</strong></article><article className="stat"><span>Root groups</span><strong>{Object.keys(report.folders).length}</strong></article></section>
    <Distribution title="Tracked files by root" values={report.folders}/>
    <label className="data-note">Filter paths <input value={query} onChange={e=>{setQuery(e.target.value);setPage(0);}} placeholder="api/agent_platform"/></label>
    <OpsTable title={"Source inventory · "+matches.length+" matches"} rows={matches.slice(selected*50,selected*50+50)} columns={[["path","Tracked path"],["bytes","Bytes"]]}/>
    <div className="toolbar"><button disabled={selected===0} onClick={()=>setPage(selected-1)}>Previous</button><span>{selected+1} / {pages}</span><button disabled={selected===pages-1} onClick={()=>setPage(selected+1)}>Next</button></div>
  </>;
}

function Overview({checks}) {
  return <><p className="data-note">Independent read-only integration checks. Available with zero records means no returned samples, not successful end-to-end capability execution.</p>
    <section className="stats">{[["Available sources",checks.filter(c=>c.state==="available").length],["Unconfigured",checks.filter(c=>c.state==="unconfigured").length],["Unavailable",checks.filter(c=>c.state==="unavailable").length]].map(([label,value])=><article className="stat" key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
    <OpsTable title="Live data coverage" rows={checks} columns={[["source","Data source"],["state","Read status"],["records","Reported records / series"]]}/>
    <p className="data-note">Use Infrastructure for deployment metadata, Configuration for runtime gates, Repository for source inventory and Product & harness for native activity. No model calls are made by these checks.</p>
  </>;
}

function Operations({source}) {
  const [data,setData] = useState(null), [error,setError] = useState(""), [loading,setLoading] = useState(true);
  const [revision,setRevision] = useState(0);
  const [period,setPeriod] = useState(source==="activity"?30:1), [project,setProject] = useState("DragonZpyder"), [traceInput,setTraceInput] = useState(""), [trace,setTrace] = useState(""), [cursor,setCursor] = useState("");
  useEffect(()=>{
    const controller = new AbortController();
    setData(null); setError(""); setLoading(true);
    fetch("/admin/api/operations?" + new URLSearchParams({source, ...(["activity","resources","traffic_history"].includes(source)?{days:String(period)}:{}), ...(source==="resources"?{project}:{}), ...(source==="langfuse"?{trace,cursor}:{})}), {credentials:"same-origin",cache:"no-store",signal:controller.signal})
      .then(async r=>{const v=await r.json(); if(!r.ok) throw new Error(typeof v.detail==="string"?v.detail:"Source unavailable"); return v;})
      .then(v=>{if(!controller.signal.aborted)setData(v);})
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[source,revision,period,project,trace,cursor]);
  const t=data?.traffic;
  return <section>
    <div className="ops-heading"><p className="data-note">{data ? "Retrieved " + new Date(data.retrieved_at).toLocaleString() : "Live provider data; no simulated metrics."}</p>
      <button onClick={()=>setRevision(v=>v+1)} disabled={loading}>Refresh</button></div>
    {["activity","resources","traffic_history"].includes(source) && <label className="data-note">Period <select value={period} onChange={e=>setPeriod(Number(e.target.value))}><option value={1}>24 hours</option><option value={7}>7 days</option><option value={30}>30 days</option>{source==="activity"&&<option value={90}>90 days</option>}</select></label>}
    {source==="resources"&&<label className="data-note"> Project <select value={project} onChange={e=>setProject(e.target.value)}><option>DragonZpyder</option><option>Operly</option></select></label>}
    {data && source==="resources"&&<ResourceMetrics data={data}/>}
    {data && source==="traffic_history"&&<TrafficHistory report={data.history}/>}
    {source==="langfuse" && <form className="toolbar" onSubmit={e=>{e.preventDefault();setCursor("");setTrace(traceInput.trim());setRevision(v=>v+1);}}><label>Trace ID<input value={traceInput} maxLength={128} onChange={e=>setTraceInput(e.target.value)} placeholder="All traces"/></label><button>Search</button><button type="button" onClick={()=>{setTraceInput("");setTrace("");setCursor("");}}>Clear</button></form>}
    {data && source==="overview" && <Overview checks={data.checks}/>}
    {data && source==="repository" && <RepositoryInventory report={data.repository}/>}
    {data && source==="activity" && <Activity report={data.activity}/>}
    {data && source==="configuration" && <Configuration report={data.configuration} onRefresh={()=>setRevision(v=>v+1)}/>}
    {loading && <p role="status">Loading operations data…</p>}{error && <p role="alert" className="error">{error}</p>}
    {data && source==="railway" && <><p className="data-note">Deployment status is not runtime health. No deployment changes are made here.</p>
      {data.projects.map(project=><div key={project.project}><OpsTable title={project.project+" · "+project.state} rows={project.services}
        columns={[["service","Service"],["status","Latest deployment status"],["deployment","Deployment ID"],["commit","Deployed commit"],["created_at","Created"],["metadata_state","Metadata"]]}/></div>)}</>}
    {t && <><p className="data-note">{data.scope} Edge region is not visitor country. Counts are requests, not users. Device/OS/browser are coarse user-agent estimates, not unique devices or verified installations; missing or misleading clients remain unknown.</p>
      <section className="stats">{[["Sample requests",t.sample_requests],["P95 duration (ms)",t.p95_duration_ms],["Received bytes",t.received_bytes],["Sent bytes",t.sent_bytes]].map(([label,value])=><article key={label} className="stat"><span>{label}</span><strong>{formatInteger(value)}</strong></article>)}</section>
      <p className="data-note">{t.first_timestamp || "Unknown"} — {t.last_timestamp || "Unknown"}</p>
      <div className="ops-distributions"><Distribution title="Edge regions (not visitor countries)" values={t.edge_regions}/><Distribution title={"Visitor country estimate · "+t.geo_state} values={t.countries}/><Distribution title="UTM source tags (requests, not referrals)" values={t.campaign_sources}/><Distribution title="Device classes (requests)" values={t.devices}/><Distribution title="Operating systems (requests)" values={t.operating_systems}/><Distribution title="Browsers and clients (requests)" values={t.browsers}/><Distribution title="Route groups" values={t.routes}/><Distribution title="HTTP status" values={t.statuses}/></div></>}
    {data && source==="github" && <><p className="data-note">Latest 20 records per category; develop commit and workflow history. <a href="https://github.com/AaryanK/DragonZpyder" target="_blank" rel="noreferrer">Open repository</a></p>
      <OpsTable title="Commits" rows={data.commits} columns={[["sha","Commit SHA"],["date","Committed"]]}/>
      <OpsTable title="Pull requests" rows={data.pull_requests} columns={[["number","PR"],["title","Title"],["state","State"],["updated_at","Updated"],["merged_at","Merged"]]}/>
      <OpsTable title="CI runs" rows={data.workflow_runs} columns={[["id","Run ID"],["name","Workflow"],["status","Status"],["conclusion","Conclusion"],["head_sha","SHA"],["updated_at","Updated"]]}/></>}
    {data && source==="langfuse" && <><p className="data-note">Latest 50 observations; additional records: {data.more_available?"yes":"not reported"}. No prompts, responses, raw metadata, user identifiers or tool arguments are exposed.</p>
      <OpsTable title="Trace observations" rows={data.observations} columns={[["traceId","Trace ID"],["id","Observation ID"],["parentObservationId","Parent"],["type","Type"],["model","Model"],["level","Level"],["startTime","Started"],["latency","Latency"],["inputUsage","Input"],["outputUsage","Output"],["totalCost","Cost"]]}/><div className="toolbar"><button disabled={!cursor} onClick={()=>setCursor("")}>First page</button><button disabled={!data.next_cursor} onClick={()=>setCursor(data.next_cursor)}>Next page</button></div></>}
  </section>;
}

function AdminPage() {
  const [tab, setTab] = useState("overview");
  const [days, setDays] = useState(30);
  const [filter, setFilter] = useState("");
  const [applied, setApplied] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (tab !== "usage") return;
    const abort = new AbortController();
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ days: String(days) });
    if (applied) params.set("app", applied);
    fetch("/admin/api/usage?" + params, {
      credentials: "same-origin", headers: { accept: "application/json" },
      cache: "no-store", signal: abort.signal,
    }).then(async r => {
      if (!r.ok) {
        const value = await r.json().catch(() => ({}));
        throw new Error(value.detail?.message || value.detail || "Usage data unavailable (" + r.status + ")");
      }
      return r.json();
    }).then(setData).catch(err => {
      if (err.name !== "AbortError") {
        setData(null);
        setError(String(err.message || err));
      }
    }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [days, applied, tab]);
  const totals = data?.totals;
  return (
    <main className="admin-layout">
      <header className="admin-header">
        <div><a href="/" className="brand"><img src="/brand-icon.png" alt="" width="28" height="28"/> DragonZpyder</a>
          <div className="eyebrow">Private operations</div><h1>Operations control center</h1>
          <p>Production inventory, traffic samples, engineering activity and AI observability.</p></div>
        <a href="/account" className="account-link">Account ↗</a>
      </header>
      <div className="ops-shell"><nav className="ops-tabs" aria-label="Operations sections">{[["overview","Overview"],["activity","Product & harness"],["usage","Model usage"],["configuration","Configuration"],["railway","Infrastructure"],["resources","Resources"],["traffic_history","Traffic history"],["traffic","Recent traffic"],["github","Engineering"],["repository","Repository"],["langfuse","Traces"]].map(([key,label])=><button key={key} aria-pressed={tab===key} onClick={()=>setTab(key)}>{label}</button>)}</nav><div className="ops-content">
      {tab!=="usage" ? <Operations key={tab} source={tab}/> : <>
      <form className="toolbar" onSubmit={e => {
        e.preventDefault();
        if (!filter || /^[a-z0-9_-]{2,60}$/.test(filter)) setApplied(filter);
        else setError("Application names must contain 2–60 lowercase letters, digits, hyphens or underscores.");
      }}>
        <label>Period <select value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={1}>24 hours</option><option value={7}>7 days</option>
          <option value={30}>30 days</option><option value={90}>90 days</option>
        </select></label>
        <label>Application <input value={filter} onChange={e => setFilter(e.target.value)}
          placeholder="All applications" maxLength={60}/></label>
        <button type="submit">Apply</button>
        <button type="button" onClick={() => { setFilter(""); setApplied(""); setError(""); }}>Clear</button>
      </form>
      {loading && <p role="status" className="status">Loading recorded usage…</p>}
      {error && <div className="error" role="alert">{error}</div>}
      {!loading && data && <>
        <section className="stats" aria-label="Usage totals">
          {[
            ["Model calls", totals?.calls], ["Failed calls", totals?.failures],
            ["Input tokens", totals?.input_tokens], ["Output tokens", totals?.output_tokens],
            ["Total tokens", totals?.total_tokens],
          ].map(([name, value]) => <article className="stat" key={name}>
            <span>{name}</span><strong>{formatInteger(value)}</strong></article>)}
          <article className="stat"><span>Provider-reported cost</span>
            <strong>{formatUsd(totals?.provider_cost_usd)}</strong></article>
        </section>
        <p className="data-note">
          Missing token reports: {formatInteger(totals?.missing_token_usage)} · Missing cost reports: {formatInteger(totals?.missing_cost)}.
          These are not assumed to be zero. Costs shown are provider-reported, not customer billing amounts.
        </p>
        {data.daily && <><Distribution title="Model calls by UTC day" values={Object.fromEntries(data.daily.map(r=>[r.day,r.calls]))}/><OpsTable title="Daily usage" rows={data.daily} columns={[["day","Day"],["calls","Calls"],["failures","Failures"],["total_tokens","Tokens"],["provider_cost_usd","Provider cost (USD)"],["missing_cost","Missing cost"],["p95_duration_ms","P95 (ms)"]]}/></>}
        <section className="table-box"><h2>Usage by application and model</h2>
          <div className="table-scroll"><table><thead><tr>
            <th>Application</th><th>Requested model</th><th>Calls</th><th>Input</th>
            <th>Output</th><th>Total tokens</th><th>Provider cost</th>
          </tr></thead><tbody>
            {(data.groups || []).map((row, i) => <tr key={row.app_id + ":" + row.requested_model + ":" + i}>
              <td>{row.app_id}</td><td className="model-name">{row.requested_model}</td>
              <td>{formatInteger(row.calls)}</td><td>{formatInteger(row.input_tokens)}</td>
              <td>{formatInteger(row.output_tokens)}</td><td>{formatInteger(row.total_tokens)}</td>
              <td>{formatUsd(row.provider_cost_usd)}</td></tr>)}
            {!data.groups?.length && <tr><td colSpan={7}>No recorded calls for this period.</td></tr>}
          </tbody></table></div>
        </section>
        <p className="data-note">Trace correlation IDs are recorded per request. Detailed inspection requires the configured Langfuse workspace and a trace viewer with appropriate permissions.</p>
      </>}
      </>}
      </div></div>
    </main>
  );
}
createRoot(document.getElementById("admin-root")).render(<AdminPage />);
