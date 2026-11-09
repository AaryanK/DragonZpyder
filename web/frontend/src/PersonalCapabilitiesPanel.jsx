import React, { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useModalFocus } from "./WorkspaceControls.jsx";

// The canonical Personal tool list comes from Operly's permission-filtered
// runtime. This UI never invokes tools or broadens session authority.
export function PersonalCapabilitiesPanel() {
  const [open, setOpen] = useState(false);
  const [tools, setTools] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [generation, refresh] = useState(0);
  const dialogRef = useRef(null);
  useModalFocus(dialogRef, open);

  useEffect(() => {
    const show = () => { setSearch(""); setError(""); setOpen(true); };
    window.addEventListener("dragonzpyder:personal-capabilities-open", show);
    return () => window.removeEventListener("dragonzpyder:personal-capabilities-open", show);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onEscape = event => {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); }
    };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const abort = new AbortController();
    setLoading(true);
    setError("");
    fetch("/api/personal-tools?limit=100", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: { Accept: "application/json" },
      signal: abort.signal,
    }).then(async response => {
      if (!response.ok) {
        if (response.status === 401 || response.status === 403)
          throw new Error("Sign in to your Personal account to view available tools.");
        throw new Error("Personal tools are unavailable. Try again after reconnecting.");
      }
      const data = await response.json();
      if (data?.scope_kind !== "personal" || !Array.isArray(data.tools))
        throw new Error("The Personal capability service returned an invalid response.");
      return data.tools.filter(tool => tool && typeof tool.id === "string" &&
        typeof tool.display_name === "string");
    }).then(setTools).catch(cause => {
      if (cause.name !== "AbortError") { setTools([]); setError(cause.message); }
    }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => abort.abort();
  }, [open, generation]);

  const matching = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tools.filter(tool => !q ||
      [tool.display_name, tool.id, tool.description, ...(tool.tags || [])]
        .join(" ").toLowerCase().includes(q));
  }, [search, tools]);

  const draft = tool => {
    // Never silently switch away from a Mesh conversation or send an action.
    if (window.dragonzpyderMesh?.isActive?.()) {
      setError("Switch to Agent mode before drafting a tool-assisted task.");
      return;
    }
    const composer = document.getElementById("message-input");
    if (!composer) { setError("The Agent composer is unavailable."); return; }
    const suggestion = "Help me use " + tool.display_name + " to ";
    if (!composer.value.trim()) {
      composer.value = suggestion;
      composer.dispatchEvent(new Event("input", { bubbles: true }));
    }
    setOpen(false);
    requestAnimationFrame(() => composer.focus());
  };

  if (!open) return null;
  return createPortal(
    <div className="dz-overlay" onMouseDown={event => {
      if (event.target === event.currentTarget) setOpen(false);
    }}>
      <section className="dz-command-panel" ref={dialogRef} role="dialog"
        aria-modal="true" aria-labelledby="dz-personal-capabilities-title"
        style={{ width: "min(760px, 95vw)", maxHeight: "85vh", overflowY: "auto" }}>
        <div className="dz-command-top">
          <strong id="dz-personal-capabilities-title">Your Personal capabilities</strong>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close Personal tools">Esc ×</button>
        </div>
        <p style={{ margin: "0 0 12px", opacity: 0.8 }}>
          These are the tools your account is currently allowed to access.
          DragonZpyder's Agent can use supported tools through Operly's approvals and permissions.
        </p>
        <input aria-label="Filter Personal capabilities" value={search}
          placeholder="Search available tools" onChange={event => setSearch(event.target.value)} />
        <div role="status" aria-live="polite" style={{ margin: "12px 0" }}>
          {loading ? "Checking authorized capabilities…" :
            error || (matching.length + " of " + tools.length + " available tools")}
        </div>
        <div className="dz-command-results" aria-label="Available Personal tools"
          style={{ overflow: "visible", maxHeight: "none" }}>
          {!loading && !error && matching.length === 0 &&
            <p>No matching connected capabilities. Check Account & connections or try another task.</p>}
          {!loading && matching.slice(0, 30).map(tool =>
            <div key={tool.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              gap: 12, padding: "12px 4px", borderBottom: "1px solid var(--border, #8884)"
            }}>
              <div style={{ minWidth: 0 }}>
                <strong>{tool.display_name}</strong>
                <p style={{ margin: "4px 0", fontSize: 13, opacity: 0.8 }}>
                  {tool.description || tool.id}
                </p>
                <small>{tool.approval_required ? "Approval required" :
                  tool.risk === "read_only" ? "Read-only" : "Permission governed"}</small>
              </div>
              <button type="button" disabled={Boolean(error)}
                aria-label={"Draft an Agent task using " + tool.display_name}
                onClick={() => draft(tool)}>Use in Agent</button>
            </div>
          )}
          {matching.length > 30 && <p>Showing 30 tools. Narrow the search to see more.</p>}
        </div>
        <div className="dz-command-foot" style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span>Browsing tools never runs them. No new permission is granted.</span>
          <button type="button" onClick={() => refresh(value => value + 1)}>Refresh</button>
        </div>
      </section>
    </div>, document.body
  );
}
