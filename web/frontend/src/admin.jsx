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
function Operations({source}) {
  const [data,setData] = useState(null), [error,setError] = useState(""), [loading,setLoading] = useState(true);
  const [revision,setRevision] = useState(0);
  useEffect(()=>{
    const controller = new AbortController();
    setData(null); setError(""); setLoading(true);
    fetch("/admin/api/operations?" + new URLSearchParams({source}), {credentials:"same-origin",cache:"no-store",signal:controller.signal})
      .then(async r=>{const v=await r.json(); if(!r.ok) throw new Error(typeof v.detail==="string"?v.detail:"Source unavailable"); return v;})
      .then(v=>{if(!controller.signal.aborted)setData(v);})
      .catch(e=>{if(!controller.signal.aborted)setError(e.message);})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[source,revision]);
  const t=data?.traffic;
  return <section>
    <div className="ops-heading"><p className="data-note">{data ? "Retrieved " + new Date(data.retrieved_at).toLocaleString() : "Live provider data; no simulated metrics."}</p>
      <button onClick={()=>setRevision(v=>v+1)} disabled={loading}>Refresh</button></div>
    {loading && <p role="status">Loading operations data…</p>}{error && <p role="alert" className="error">{error}</p>}
    {data && source==="railway" && <><p className="data-note">Deployment status is not runtime health. No deployment changes are made here.</p>
      {data.projects.map(project=><div key={project.project}><OpsTable title={project.project+" · "+project.state} rows={project.services}
        columns={[["service","Service"],["status","Latest deployment status"],["deployment","Deployment ID"]]}/></div>)}</>}
    {t && <><p className="data-note">{data.scope} Edge region is not visitor country. Counts are requests, not users.</p>
      <section className="stats">{[["Sample requests",t.sample_requests],["P95 duration (ms)",t.p95_duration_ms],["Received bytes",t.received_bytes],["Sent bytes",t.sent_bytes]].map(([label,value])=><article key={label} className="stat"><span>{label}</span><strong>{formatInteger(value)}</strong></article>)}</section>
      <p className="data-note">{t.first_timestamp || "Unknown"} — {t.last_timestamp || "Unknown"}</p>
      <div className="ops-distributions"><Distribution title="Edge regions" values={t.edge_regions}/><Distribution title="Route groups" values={t.routes}/><Distribution title="HTTP status" values={t.statuses}/></div></>}
    {data && source==="github" && <><p className="data-note">Latest 20 records per category; develop commit and workflow history. <a href="https://github.com/AaryanK/DragonZpyder" target="_blank" rel="noreferrer">Open repository</a></p>
      <OpsTable title="Commits" rows={data.commits} columns={[["sha","Commit SHA"],["date","Committed"]]}/>
      <OpsTable title="Pull requests" rows={data.pull_requests} columns={[["number","PR"],["title","Title"],["state","State"],["updated_at","Updated"],["merged_at","Merged"]]}/>
      <OpsTable title="CI runs" rows={data.workflow_runs} columns={[["id","Run ID"],["name","Workflow"],["status","Status"],["conclusion","Conclusion"],["head_sha","SHA"],["updated_at","Updated"]]}/></>}
    {data && source==="langfuse" && <><p className="data-note">Latest 50 observations; additional records: {data.more_available?"yes":"not reported"}. No prompts, responses, raw metadata, user identifiers or tool arguments are exposed.</p>
      <OpsTable title="Trace observations" rows={data.observations} columns={[["traceId","Trace ID"],["id","Observation ID"],["parentObservationId","Parent"],["type","Type"],["model","Model"],["level","Level"],["startTime","Started"],["latency","Latency"],["inputUsage","Input"],["outputUsage","Output"],["totalCost","Cost"]]}/></>}
  </section>;
}

function AdminPage() {
  const [tab, setTab] = useState("usage");
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
      <nav className="ops-tabs" aria-label="Operations sections">{[["usage","Model usage"],["railway","Infrastructure"],["traffic","Traffic"],["github","Engineering"],["langfuse","Traces"]].map(([key,label])=><button key={key} aria-pressed={tab===key} onClick={()=>setTab(key)}>{label}</button>)}</nav>
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
    </main>
  );
}
createRoot(document.getElementById("admin-root")).render(<AdminPage />);
