import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./admin.css";

function formatInteger(value) {
  return value === null || value === undefined ? "Unknown" : Number(value).toLocaleString();
}
function formatUsd(value) {
  return value === null || value === undefined ? "Unknown" : "$" + Number(value).toFixed(6);
}
function AdminPage() {
  const [days, setDays] = useState(30);
  const [filter, setFilter] = useState("");
  const [applied, setApplied] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
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
  }, [days, applied]);
  const totals = data?.totals;
  return (
    <main className="admin-layout">
      <header className="admin-header">
        <div><a href="/" className="brand">✦ DragonZpyder</a>
          <div className="eyebrow">Private operations</div><h1>Model usage and traces</h1>
          <p>Server-recorded inference usage, attributed by application and model.</p></div>
        <a href="/account" className="account-link">Account ↗</a>
      </header>
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
    </main>
  );
}
createRoot(document.getElementById("admin-root")).render(<AdminPage />);
