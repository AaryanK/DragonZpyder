import React, { useEffect, useState } from "react";
import "./admin.css";

const fmt = (n) => n === null || n === undefined ? "—" : Number(n).toLocaleString();
const money = (n) => n === null || n === undefined ? "Unknown" : "$" + Number(n).toFixed(6);
const when = (s) => s ? new Date(s).toLocaleString() : "—";

async function readJSON(path) {
  const response = await fetch("/admin/api/" + path, {
    headers: { accept: "application/json" }, credentials: "same-origin", cache: "no-store",
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(result.error?.message || result.error || "Request failed (" + response.status + ")");
  return result;
}

export function AdminPage() {
  const [days, setDays] = useState(7);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);

  async function refresh() {
    setBusy(true); setError("");
    try {
      const [s, e] = await Promise.all([
        readJSON("summary?days=" + days), readJSON("events?limit=60"),
      ]);
      setSummary(s);
      setEvents(e.events || []);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { refresh(); }, [days]);

  async function inspect(id, reveal = false) {
    if (reveal && !window.confirm("This accesses encrypted model content and creates an administrator audit record. Continue?")) return;
    setBusy(true); setError("");
    try {
      const result = await readJSON("events/" + encodeURIComponent(id) + (reveal ? "?reveal=true" : ""));
      setSelected(result);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  const t = summary?.totals;
  return <div className="dz-admin">
    <header className="dz-admin-header">
      <div><a href="/" className="dz-admin-brand">DragonZpyder</a><span className="dz-admin-kicker">/ Administrator</span></div>
      <a href="/app">Personal AI ↗</a>
    </header>
    <main className="dz-admin-content">
      <div className="dz-admin-intro">
        <div><div className="dz-admin-eyebrow">Inference Observatory</div>
          <h1>Model operations.</h1>
          <p>Private, attributed usage from the DragonZpyder inference gateway. Counts are provider reported; unavailable tokens and prices are never estimated.</p></div>
        <div className="dz-admin-actions"><label>Window
          <select value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value="1">24 hours</option><option value="7">7 days</option>
            <option value="30">30 days</option><option value="90">90 days</option>
          </select></label><button onClick={refresh} disabled={busy}>{busy ? "Loading…" : "Refresh"}</button></div>
      </div>
      {error && <div className="dz-admin-error" role="alert">{error}</div>}
      {summary && !summary.configured && <div className="dz-admin-warning">Durable usage collection is not configured. The dashboard will populate after the PostgreSQL ledger is connected.</div>}
      <div className="dz-admin-stats">
        {[
          ["Recorded requests", t?.calls], ["Input tokens", t?.input_tokens],
          ["Output tokens", t?.output_tokens], ["Provider-reported cost", t ? money(t.cost_usd) : null],
          ["Unresolved requests", t?.pending], ["Unknown usage", t?.unknown_usage],
        ].map(([name, value]) => <div className="dz-admin-stat" key={name}>
          <span>{name}</span><strong>{typeof value === "string" ? value : fmt(value)}</strong></div>)}
      </div>
      <div className="dz-admin-columns">
        {[
          ["Usage by application", summary?.by_app || []],
          ["Usage by requested model", summary?.by_model || []],
        ].map(([title, rows]) => <section className="dz-admin-panel" key={title}>
          <h2>{title}</h2><div className="dz-admin-table-scroll">
            <table><thead><tr><th>Application / model</th><th>Calls</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead>
              <tbody>{rows.map(row => <tr key={row.key}>
                <td title={row.key}>{row.key}</td><td>{fmt(row.calls)}</td>
                <td>{fmt(row.input_tokens)}</td><td>{fmt(row.output_tokens)}</td>
                <td>{money(row.cost_usd)}</td></tr>)}</tbody></table>
            {!rows.length && <p className="dz-admin-empty">No attributed usage records in this window.</p>}
          </div>
        </section>)}
      </div>
      <section className="dz-admin-panel">
        <h2>Recent inference requests</h2>
        <p className="dz-admin-hint">Select a request to inspect trace IDs, model selection, provider generation IDs and exact reported usage.</p>
        <div className="dz-admin-table-scroll"><table><thead><tr>
          <th>Timestamp</th><th>Application</th><th>Model</th><th>Status</th><th>Tokens</th><th>Cost</th>
        </tr></thead><tbody>{events.map(item => <tr key={item.request_id}>
          <td><button className="dz-admin-link" onClick={() => inspect(item.request_id)}>{when(item.started_at)}</button></td>
          <td>{item.app_id}</td><td>{item.actual_model || item.requested_model}</td>
          <td>{item.status}</td><td>{fmt(item.total_tokens)}</td><td>{money(item.cost_usd)}</td>
        </tr>)}</tbody></table>
        {!events.length && <p className="dz-admin-empty">No inference requests recorded yet.</p>}</div>
      </section>
      {selected && <section className="dz-admin-panel" aria-label="Selected trace details">
        <div className="dz-admin-panel-heading"><h2>Request inspection</h2><button onClick={() => setSelected(null)}>Close</button></div>
        <dl className="dz-admin-details">
          {[
            ["Request ID",selected.request_id],["Trace ID",selected.trace_id],
            ["App",selected.app_id],["Requested model",selected.requested_model],
            ["Actual model",selected.actual_model],["OpenRouter generation",selected.generation_id],
            ["Status",selected.status],["Latency",selected.duration_ms == null ? null : selected.duration_ms + " ms"],
          ].map(([label, value]) => <React.Fragment key={label}><dt>{label}</dt><dd>{value ?? "Not reported"}</dd></React.Fragment>)}
        </dl>
        <h3>Provider usage</h3><pre>{JSON.stringify(selected.usage ?? {},null,2)}</pre>
        {selected.request !== undefined || selected.response !== undefined
          ? <><h3>Encrypted payload inspection</h3><pre>{JSON.stringify({request:selected.request,response:selected.response},null,2)}</pre></>
          : <button disabled={busy} onClick={() => inspect(selected.request_id,true)}>Reveal encrypted request/response (audited)</button>}
      </section>}
      <footer>Operator access only · No token estimates · Langfuse provides deeper linked spans when configured</footer>
    </main>
  </div>;
}
