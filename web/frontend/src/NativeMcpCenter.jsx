import React, { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** Browser UI for DragonZpyder's own OAuth MCP store. No bearer credentials
 * enter React. Agent tools use only the explicitly selected opaque aliases.
 */
function csrf() {
  const found = document.cookie.split(";").map(p => p.trim())
    .find(part => part.startsWith("__Host-dz_csrf="));
  return found ? decodeURIComponent(found.slice("__Host-dz_csrf=".length)) : "";
}
async function nativeRequest(path, options = {}) {
  if (!path.startsWith("/dz/internal/mcp/")) throw Error("Invalid MCP request");
  const method = options.method || "GET";
  const headers = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    headers["X-DZ-CSRF"] = csrf();
  }
  const res = await fetch(path, {
    method, headers, credentials: "same-origin", cache: "no-store",
    redirect: "error", ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Error(
    typeof data.detail === "string" ? data.detail
      : data.detail?.message || "MCP request was rejected (" + res.status + ")"
  );
  return data;
}
function broadcast(ids) {
  const safe = Array.isArray(ids)
    ? [...new Set(ids.filter(v => typeof v === "string" && /^c[a-f0-9]{30}$/.test(v)))].slice(0, 10)
    : [];
  window.dragonzpyderSelectedMcpAccounts = safe;
  window.dispatchEvent(new CustomEvent("dragonzpyder:mcp-selection", { detail: { ids: safe } }));
}

export function NativeMcpCenter({ onClose, page = "connections" }) {
  const [providers, setProviders] = useState([]);
  const [connections, setConnections] = useState([]);
  const [selection, setSelection] = useState(
    () => window.dragonzpyderSelectedMcpAccounts || []
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const [p, c] = await Promise.all([
        nativeRequest("/dz/internal/mcp/providers"),
        nativeRequest("/dz/internal/mcp/connections"),
      ]);
      const active = (Array.isArray(c.connections) ? c.connections : [])
        .filter(x => x.status === "active" && /^c[a-f0-9]{30}$/.test(x.connection_id));
      setProviders(Array.isArray(p.providers) ? p.providers : []);
      setConnections(active);
      const valid = new Set(active.map(x => x.connection_id));
      setSelection(old => {
        const checked = old.filter(id => valid.has(id));
        broadcast(checked);
        return checked;
      });
    } catch (e) {
      setError(e.message || "Could not read DragonZpyder connections.");
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const connect = async (provider) => {
    setBusy(true); setError("");
    try {
      const response = await nativeRequest(
        "/dz/internal/mcp/connections/" + encodeURIComponent(provider) + "/start",
        { method: "POST", body: { label: "" } }
      );
      const url = response.authorization_url;
      if (typeof url !== "string" || !url.startsWith("https://"))
        throw Error("OAuth provider did not supply an approved authorization link.");
      window.location.assign(url);
    } catch (e) { setError(e.message); setBusy(false); }
  };
  const disconnect = async (connection) => {
    if (!window.confirm("Disconnect this MCP account? This revokes its authorization for future Agent work."))
      return;
    setBusy(true); setError("");
    try {
      await nativeRequest("/dz/internal/mcp/connections/" +
        encodeURIComponent(connection.connection_id), { method: "DELETE" });
      setSuccess("Disconnected; future tool calls are no longer authorized.");
      await refresh();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  const toggle = (id, checked) => {
    const next = checked
      ? [...new Set([...selection, id])].slice(0, 10)
      : selection.filter(x => x !== id);
    setSelection(next); broadcast(next);
  };
  return createPortal(<div className="dz-center-scrim" onMouseDown={e => {
    if (e.target === e.currentTarget) onClose();
  }}>
    <section className="dz-center-shell" role="dialog" aria-modal="true"
      aria-label="DragonZpyder MCP connections">
      <aside className="dz-center-rail">
        <div className="dz-center-brand"><strong>DragonZpyder</strong></div>
        <p className="dz-center-rail-caption">FIRST-PARTY CONNECTIONS</p>
        <nav><button className="selected" type="button">⌘ Connected tools</button>
          <a href="/account">◎ Account</a></nav>
        <div className="dz-center-rail-foot">External services are optional.</div>
      </aside>
      <div className="dz-center-content">
        <header className="dz-center-top"><strong>Connections & tools</strong>
          <button type="button" onClick={onClose}>Close ×</button></header>
        <div className="dz-center-body">
          <p>DragonZpyder owns this Agent session. Connect providers individually,
            then choose which accounts the Agent may use for this conversation.</p>
          {error && <div className="dz-center-error" role="alert">{error}</div>}
          {success && <p role="status">{success}</p>}
          {page !== "connections" && <p>Other legacy workspace controls are not
            available in first-party mode. Business operations remain inside
            the linked provider's explicit MCP permissions.</p>}
          <div className="dz-center-section-header">
            <h3>Your authorized MCP accounts</h3>
            <button type="button" disabled={busy} onClick={() => void refresh()}>Refresh</button>
          </div>
          {connections.length === 0 && <p>No connected MCP accounts. You can still
            use DragonZpyder's core agent without an Operly account.</p>}
          {connections.map(account => <div className="dz-center-row" key={account.connection_id}>
            <label className="dz-center-row-body">
              <input type="checkbox" disabled={busy}
                checked={selection.includes(account.connection_id)}
                onChange={e => toggle(account.connection_id, e.target.checked)}/>
              {" "}<strong>{account.label || account.provider_id}</strong>
              <small> {account.provider_id} · Use only when selected</small>
            </label>
            <button type="button" disabled={busy} onClick={() => void disconnect(account)}>
              Disconnect
            </button>
          </div>)}
          <div className="dz-center-section-header"><h3>Add a provider</h3></div>
          {providers.length === 0 && <p>No reviewed OAuth providers are enabled
            for this deployment.</p>}
          {providers.map(p => <div className="dz-center-row" key={p.provider_id}>
            <div className="dz-center-row-body"><strong>{p.provider_id}</strong>
              <small>{p.description || "MCP provider"} · Scope approved by provider</small></div>
            <button type="button" disabled={busy} onClick={() => void connect(p.provider_id)}>Connect</button>
          </div>)}
          <p className="dz-center-fineprint">Read-only capabilities require a reviewed tool
            policy. Mutating business actions require independent authorization
            and approval. Connecting does not grant all provider permissions.</p>
        </div>
      </div>
    </section>
  </div>, document.body);
}
