import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useModalFocus } from "./WorkspaceControls.jsx";

/**
 * The account-scoped API lives behind DragonZpyder's same-origin /api proxy.
 * No provider secrets, raw account tokens or workspace authority enter React.
 */
const asArray = value => Array.isArray(value) ? value : [];
const asString = value => typeof value === "string" ? value : "";
const errorText = error => error instanceof Error ? error.message : "This action could not be completed.";
function csrfCookie() {
  const entries = document.cookie.split(";").map(v => v.trim());
  for (const name of ["__Host-operly_csrf", "operly_csrf"]) {
    const found = entries.find(v => v.startsWith(name + "="));
    if (found) return decodeURIComponent(found.slice(name.length + 1));
  }
  return "";
}
let bootstrapToken = "";
async function request(path, options = {}) {
  if (!path.startsWith("/api/")) throw new Error("Invalid API route.");
  const method = options.method || "GET";
  const headers = { accept: "application/json" };
  if (method !== "GET" && method !== "HEAD") {
    headers["content-type"] = "application/json";
    // Operly's browser CSRF bootstrap is intentionally served through DragonZpyder.
    if (!csrfCookie() && !bootstrapToken) {
      const boot = await fetch("/api/auth/bootstrap", { credentials: "same-origin", cache: "no-store" });
      if (boot.ok) bootstrapToken = asString((await boot.json()).csrf_token);
    }
    headers["X-CSRF-Token"] = csrfCookie() || bootstrapToken;
  }
  const response = await fetch(path, {
    method, credentials: "same-origin", cache: "no-store", redirect: "error", headers,
    ...(method !== "GET" && method !== "HEAD" ? { body: JSON.stringify(options.body ?? {}) } : {}),
    signal: options.signal,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : asString(detail?.message) || `Request failed (${response.status})`);
  }
  return body;
}
const pages = [
  { id: "connections", label: "Connections", glyph: "⌘" },
  { id: "capabilities", label: "Tools", glyph: "✦" },
  { id: "approvals", label: "Approvals", glyph: "◉" },
  { id: "workspaces", label: "Workspaces", glyph: "▦" },
  { id: "identity", label: "Identity", glyph: "◎" },
  { id: "tasks", label: "Tasks", glyph: "◷" },
];
const userToolName = tool => asString(tool.display_name || tool.name || tool.id || tool.capability_id) || "Unnamed tool";
const providerName = provider => ({google:"Google",canva:"Canva",discord:"Discord"})[provider] || provider || "Service";
const boundId = id => encodeURIComponent(asString(id));
const toRecord = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};
function Tag({ children, variant = "" }) { return <span className={`dz-center-tag ${variant}`}>{children}</span>; }
function Empty({ title, children }) { return <div className="dz-center-empty"><strong>{title}</strong><p>{children}</p></div>; }

export function WorkspaceCenter() {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState("connections");
  const [data, setData] = useState({});
  const [pending, setPending] = useState({});
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [search, setSearch] = useState("");
  const [selectedTool, setSelectedTool] = useState(null);
  const [googleTier, setGoogleTier] = useState("basic");
  const [workspaceName, setWorkspaceName] = useState("");
  const [sessions, setSessions] = useState([]);
  const dialogRef = useRef(null);
  useModalFocus(dialogRef, open);

  const routes = {
    connections: "/api/personal-connectors",
    capabilities: "/api/personal-tools",
    approvals: "/api/personal-tools/approvals",
    workspaces: "/api/auth/workspaces",
    identity: "/api/auth/me",
  };

  const load = useCallback(async (key, force = false) => {
    if (!routes[key]) return;
    setPending(state => ({ ...state, [key]: true }));
    setErrors(state => ({ ...state, [key]: "" }));
    try {
      const result = await request(routes[key]);
      setData(state => ({ ...state, [key]: result }));
      if (key === "identity") {
        try { setSessions(asArray(await request("/api/auth/sessions"))); }
        catch { setSessions([]); }
      }
    } catch (error) {
      setErrors(state => ({ ...state, [key]: errorText(error) }));
    } finally {
      setPending(state => ({ ...state, [key]: false }));
    }
  }, []);

  useEffect(() => {
    const show = event => {
      const requested = event.detail?.page;
      setPage(pages.some(item => item.id === requested) ? requested : "connections");
      setOpen(true);
    };
    window.addEventListener("dragonzpyder:center-open", show);
    return () => window.removeEventListener("dragonzpyder:center-open", show);
  }, []);

  const loadTasks = useCallback(async () => {
    setPending(state => ({ ...state, tasks: true }));
    setErrors(state => ({ ...state, tasks: "" }));
    try {
      const catalog = await request("/api/personal-tools?query=workflow&limit=100");
      const ids = new Set(asArray(catalog.tools).map(tool => tool.id));
      if (!ids.has("workflow.list")) {
        setData(state => ({ ...state, tasks: { available: false, workflows: [], runs: [], ids: [] } }));
        return;
      }
      const read = async (id, argumentsValue) => {
        if (!ids.has(id)) return {};
        const response = await request(`/api/personal-tools/${boundId(id)}/execute`, {
          method: "POST", body: { arguments: argumentsValue, goal: "View my Personal workflow activity" },
        });
        if (response.done === false || response.status === "failed") throw new Error(`Cannot read ${id}; check the governed execution record.`);
        const result = toRecord(response.result);
        return toRecord(result.value || result);
      };
      const [definitions, activity] = await Promise.all([
        read("workflow.list", { limit: 100 }),
        read("workflow.run.list", { limit: 100 }),
      ]);
      setData(state => ({ ...state, tasks: {
        available: true, workflows: asArray(definitions.workflows), runs: asArray(activity.runs), ids: [...ids],
      } }));
    } catch (error) {
      setErrors(state => ({ ...state, tasks: errorText(error) }));
    } finally {
      setPending(state => ({ ...state, tasks: false }));
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    if (page === "tasks") void loadTasks();
    else if (routes[page]) void load(page);
  }, [open, page, load, loadTasks]);

  useEffect(() => {
    if (!open) return;
    const esc = event => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open]);

  const choose = next => { setPage(next); setMessage(""); setSearch(""); setSelectedTool(null); };
  const act = async (name, fn, refresh = page) => {
    if (busy) return;
    setBusy(name); setMessage("");
    try {
      const result = await fn();
      if (refresh && routes[refresh]) await load(refresh, true);
      setMessage(`${name} completed.`);
      return result;
    } catch (error) {
      setMessage(errorText(error));
      return null;
    } finally { setBusy(""); }
  };

  const connectors = asArray(data.connections?.connectors || data.connections);
  const workspaces = asArray(data.workspaces?.workspaces || data.workspaces);
  const tools = asArray(data.capabilities?.tools || data.capabilities?.capabilities || data.capabilities);
  const approvals = asArray(data.approvals?.approvals || data.approvals?.items || data.approvals);
  const identity = toRecord(data.identity);
  const current = pages.find(item => item.id === page);

  const visibleTools = useMemo(() => tools.filter(tool => {
    const needle = [tool.id, tool.display_name, tool.description, tool.provider_id].join(" ").toLowerCase();
    return needle.includes(search.trim().toLowerCase());
  }), [tools, search]);

  const connect = provider => act(`Connect ${providerName(provider)}`, async () => {
    const path = provider === "google"
      ? `/api/personal-connectors/google/connect?tier=${googleTier}`
      : "/api/personal-connectors/canva/connect";
    const result = await request(path, { method: "POST" });
    const url = asString(result.authorization_url);
    if (!url || !url.startsWith("https://")) throw new Error("The provider did not return a valid HTTPS authorization URL.");
    window.location.assign(url);
  }, null);

  const test = connector => act(`Test ${providerName(connector.provider)}`, () =>
    request(`/api/personal-connectors/${boundId(connector.id)}/test`, { method: "POST" }), "connections");

  const disconnect = connector => {
    if (!window.confirm(`Disconnect ${providerName(connector.provider)}? Agents will lose this connector's authorization.`)) return;
    void act(`Disconnect ${providerName(connector.provider)}`, () =>
      request(`/api/personal-connectors/${boundId(connector.id)}`, { method: "DELETE" }), "connections");
  };

  const renderConnections = () => <div className="dz-center-stack">
    <div className="dz-center-intro"><span className="dz-center-eyebrow">Your connected world</span><h2>Connections</h2><p>Choose which services DragonZpyder can use. Signing in with a provider is not permission to read or change its data.</p></div>
    <div className="dz-center-feature-grid">
      {[["google","G","Google","Email and calendar capabilities"],["canva","C","Canva","Design and publishing tools"]].map(([id,icon,name,detail]) => {
        const linked = connectors.some(c => c.provider === id);
        return <article key={id} className="dz-center-feature">
          <span className="dz-center-provider" aria-hidden="true">{icon}</span><strong>{name}</strong><p>{detail}</p>
          {id === "google" && !linked && <fieldset className="dz-center-google-tiers"><legend>Access level</legend>
            <label><input type="radio" name="google-tier" checked={googleTier==="basic"} onChange={() => setGoogleTier("basic")} /> Read-only</label>
            <label><input type="radio" name="google-tier" checked={googleTier==="assistant"} onChange={() => setGoogleTier("assistant")} /> Assistant access</label>
          </fieldset>}
          <button type="button" className="dz-center-small-button" onClick={() => void connect(id)} disabled={!!busy || linked}>{linked ? "Linked — manage below" : "Connect"} <span aria-hidden="true">↗</span></button>
        </article>;
      })}
    </div>
    <div className="dz-center-section-header"><h3>Authorized accounts</h3><button type="button" onClick={() => void load("connections", true)} disabled={pending.connections}>Refresh</button></div>
    {pending.connections ? <p className="dz-center-muted">Checking connection status…</p> : errors.connections
      ? <div className="dz-center-error" role="alert">{errors.connections}</div>
      : connectors.length ? <div className="dz-center-list">{connectors.map(c => <article key={c.id} className="dz-center-row">
        <span className="dz-center-provider" aria-hidden="true">{providerName(c.provider)[0]}</span>
        <div className="dz-center-row-body"><strong>{c.displayName || providerName(c.provider)}</strong>
          <small>{c.account || "Account details unavailable"} · {c.healthStatus || c.status || "Status unavailable"}</small>
          {!!asArray(c.capabilities).length && <p>{asArray(c.capabilities).slice(0,4).join(" · ")}</p>}
          {c.lastError && <p className="dz-center-error-inline">{c.lastError}</p>}
        </div>
        <div className="dz-center-row-actions"><Tag variant={c.enabled ? "active" : ""}>{c.enabled ? "Enabled" : "Disabled"}</Tag>
          <button type="button" disabled={!!busy} onClick={() => void test(c)}>Test</button>
          <button type="button" disabled={!!busy} onClick={() => disconnect(c)}>Disconnect</button>
        </div>
      </article>)}</div> : <Empty title="No connected accounts">Connect a service to expose the capabilities you explicitly authorize.</Empty>}
    <p className="dz-center-fineprint">Connections are account-owned. Your agents still need appropriate scopes and approvals to perform actions.</p>
  </div>;

  const renderCapabilities = () => <div className="dz-center-stack">
    <div className="dz-center-intro"><span className="dz-center-eyebrow">Discover what is available</span><h2>Your tools</h2><p>This catalog comes from the authenticated Personal capability registry. Discovery never grants permission to execute.</p></div>
    <label className="dz-center-search"><span aria-hidden="true">⌕</span><input type="search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Find a capability" aria-label="Find a capability" /></label>
    {pending.capabilities ? <p className="dz-center-muted">Discovering available tools…</p> : errors.capabilities ? <div className="dz-center-error" role="alert">{errors.capabilities}</div>
      : visibleTools.length ? <div className="dz-center-list">{visibleTools.map(tool => <button className="dz-center-tool" type="button" key={tool.id || tool.capability_id}
        onClick={() => setSelectedTool(tool)} aria-pressed={selectedTool?.id === tool.id}>
        <span className="dz-center-tool-name"><strong>{userToolName(tool)}</strong><small>{asString(tool.description)}</small></span>
        <Tag>{tool.risk || "Scoped"}</Tag><span aria-hidden="true">›</span></button>)}</div> : <Empty title="No matching tools">{search ? "Try a different search." : "The current Personal session has no discoverable capabilities."}</Empty>}
    {selectedTool && <section className="dz-center-detail"><div className="dz-center-section-header"><h3>{userToolName(selectedTool)}</h3><button onClick={() => setSelectedTool(null)} aria-label="Close tool detail">Close</button></div>
      <p>{selectedTool.description || "No description is available."}</p>
      <dl><dt>Capability ID</dt><dd>{selectedTool.id || selectedTool.capability_id}</dd><dt>Risk</dt><dd>{selectedTool.risk || "Not specified"}</dd>
      <dt>Approval</dt><dd>{selectedTool.approval_required ? "Required" : "Determined by policy"}</dd></dl>
      <p className="dz-center-fineprint">Execution is deliberately not exposed here until a safe, typed invocation contract has been verified. Use the existing permissioned Agent experience for actual work.</p>
    </section>}
  </div>;

  const decideApproval = (approval, approved) => {
    if (approval.status !== "pending") return;
    const label = approval.capability_id || "this action";
    if (!window.confirm(approved ? `Allow ${label} once? Check its arguments and Personal scope first.` : `Deny ${label}?`)) return;
    void act(approved ? "Approval" : "Denial", () => request(
      `/api/personal-tools/approvals/${boundId(approval.id)}/decision`,
      { method: "POST", body: { approved } }
    ), "approvals");
  };

  const workflowAction = (workflow, capability) => {
    const ids = new Set(asArray(data.tasks?.ids));
    if (!ids.has(capability) || busy) return;
    const label = capability === "workflow.run.start" ? "Run" : capability === "workflow.disable" ? "Pause" : "Enable";
    if (!window.confirm(`${label} Personal workflow "${workflow.name}"?`)) return;
    setBusy(capability); setMessage("");
    void (async () => {
      try {
        const response = await request(`/api/personal-tools/${boundId(capability)}/execute`, {
          method: "POST", body: { arguments: { workflow_id: workflow.id }, goal: `${label} workflow ${workflow.name}` },
        });
        setMessage(response.done === false
          ? "Action has not finished. Check approvals or execution status."
          : response.status === "failed" ? "Operation failed. Inspect execution record."
          : "Operation completed.");
        await loadTasks();
      } catch (error) { setMessage(errorText(error)); }
      finally { setBusy(""); }
    })();
  };

  const renderApprovals = () => <div className="dz-center-stack">
    <div className="dz-center-intro"><span className="dz-center-eyebrow">Human control</span><h2>Approvals</h2><p>Review requested actions before an agent is allowed to perform them. Only the existing governed approval route can authorize execution.</p></div>
    <div className="dz-center-section-header"><h3>Personal approvals</h3><button type="button" onClick={() => void load("approvals", true)}>Refresh</button></div>
    {pending.approvals ? <p className="dz-center-muted">Checking pending approvals…</p> : errors.approvals ? <div className="dz-center-error" role="alert">{errors.approvals}</div>
    : approvals.length ? <div className="dz-center-list">{approvals.map((approval, index) =>
      <article key={approval.id || index} className="dz-center-row">
        <span className="dz-center-provider" aria-hidden="true">◇</span><div className="dz-center-row-body">
        <strong>{approval.capability_id || approval.title || "Capability approval"}</strong>
        <small>{approval.status || "Status unavailable"}</small>
        <p>{approval.summary || approval.reason || "Review the action in your existing approvals interface."}</p></div>
        <div className="dz-center-row-actions">
          {approval.arguments && <details className="dz-center-arguments"><summary>Arguments</summary><pre>{JSON.stringify(approval.arguments, null, 2)}</pre></details>}
          {approval.status === "pending" ? <>
            <button type="button" disabled={!!busy} onClick={() => decideApproval(approval, false)}>Deny</button>
            <button type="button" disabled={!!busy} onClick={() => decideApproval(approval, true)}>Allow once</button>
          </> : <Tag>{approval.status || "Resolved"}</Tag>}
        </div>
      </article>)}</div> : <Empty title="No Personal approvals found">There are no approvals returned for this session.</Empty>}
  </div>;

  const createWorkspace = event => {
    event.preventDefault();
    const name = workspaceName.trim();
    if (name.length < 2 || name.length > 160) { setMessage("Enter a workspace name between 2 and 160 characters."); return; }
    if (!window.confirm(`Create a business workspace named "${name}"? This creates a separate governed workspace.`)) return;
    void act("Create workspace", async () => {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      const result = await request("/api/auth/workspaces", { method: "POST", body: { name, timezone } });
      if (!result?.workspace?.id) throw new Error("The workspace creation response was incomplete.");
      setWorkspaceName("");
    }, "workspaces");
  };

  const renderWorkspaces = () => <div className="dz-center-stack">
    <div className="dz-center-intro"><span className="dz-center-eyebrow">Permission boundaries</span><h2>Workspaces</h2><p>Your Personal identity stays separate from business memberships. Workspace actions require the corresponding workspace authority.</p></div>
    {pending.workspaces ? <p className="dz-center-muted">Loading memberships…</p> : errors.workspaces ? <div className="dz-center-error" role="alert">{errors.workspaces}</div>
      : workspaces.length ? <div className="dz-center-list">{workspaces.map(w => <article key={w.id} className="dz-center-row">
        <span className="dz-center-provider" aria-hidden="true">▦</span><div className="dz-center-row-body"><strong>{w.name}</strong><small>{w.role || "Membership"}</small></div><Tag>Workspace</Tag>
      </article>)}</div> : <Empty title="No business workspaces">Your Personal account remains usable without joining a business workspace.</Empty>}
    <form className="dz-center-create-workspace" onSubmit={createWorkspace}>
      <label htmlFor="dz-workspace-name">Create a workspace</label>
      <div><input id="dz-workspace-name" value={workspaceName} maxLength={160} onChange={event => setWorkspaceName(event.target.value)}
        placeholder="Workspace name" required minLength={2} /><button type="submit" disabled={!!busy || workspaceName.trim().length < 2}>Create</button></div>
      <p>Workspace creation is an explicit action and requires the signed-in account's authorization. Business tools remain governed by workspace membership.</p>
    </form>
  </div>;

  const renderIdentity = () => <div className="dz-center-stack">
    <div className="dz-center-intro"><span className="dz-center-eyebrow">Your account</span><h2>Identity</h2><p>Manage your verified account and sign-in methods, without exposing authentication tokens to agent tools.</p></div>
    {pending.identity ? <p className="dz-center-muted">Checking your account…</p> : errors.identity ? <div className="dz-center-error" role="alert">{errors.identity}</div>
      : <div className="dz-center-list"><div className="dz-center-row"><span className="dz-center-provider" aria-hidden="true">◎</span><div className="dz-center-row-body">
        <strong>{identity.display_name || "Your account"}</strong><small>{identity.email || "Email unavailable"}</small>
        <p>{asArray(identity.auth_identities).map(i=>providerName(i.provider)).join(" · ") || "No linked sign-in providers listed"}</p>
      </div><a className="dz-center-small-button" href="/account">Manage account ↗</a></div></div>}
    <div className="dz-center-section-header"><h3>Active sessions</h3><span className="dz-center-muted">Reported by the identity service</span></div>
    {sessions.length ? <div className="dz-center-list">{sessions.map((session,index) =>
      <div className="dz-center-row" key={session.id || index}><span className="dz-center-provider" aria-hidden="true">◇</span>
      <div className="dz-center-row-body"><strong>{session.device || session.device_name || "Session"}</strong>
      <small>{session.scope || "Scope unavailable"}{session.current ? " · Current session" : ""}</small></div><Tag>{session.current ? "Current" : "Active"}</Tag>
      </div>)}</div> : <Empty title="Session details unavailable">No session details were returned by the identity service.</Empty>}
    <div className="dz-center-info">Google sign-in is separate from authorizing Gmail or Calendar. For password changes and sign-out, use the existing Account page.</div>
  </div>;

  const renderTasks = () => {
    const taskData = toRecord(data.tasks), workflows = asArray(taskData.workflows), runs = asArray(taskData.runs);
    const ids = new Set(asArray(taskData.ids));
    return <div className="dz-center-stack">
      <div className="dz-center-intro"><span className="dz-center-eyebrow">Persistent intelligence</span><h2>Tasks & goals</h2>
        <p>Your Personal workflows and recent executions, retrieved through the same scoped Kernel used by authorized agents.</p></div>
      <div className="dz-center-section-header"><h3>My workflows</h3><button type="button" onClick={() => void loadTasks()} disabled={pending.tasks}>Refresh</button></div>
      {pending.tasks ? <p className="dz-center-muted">Loading workflows and executions…</p>
        : errors.tasks ? <div className="dz-center-error" role="alert">{errors.tasks}</div>
        : taskData.available === false ? <Empty title="Personal workflows unavailable">This session has no authorized workflow-list capability. Scheduling infrastructure alone does not grant access.</Empty>
        : workflows.length ? <div className="dz-center-list">{workflows.map(w => <article className="dz-center-row" key={w.id}>
          <span className="dz-center-provider" aria-hidden="true">◷</span>
          <div className="dz-center-row-body"><strong>{w.name || "Unnamed workflow"}</strong>
            <small>{w.status || "Unknown"} {w.next_run_at ? " · Next: " + new Date(w.next_run_at).toLocaleString() : ""}</small>
            {w.description && <p>{w.description}</p>}</div>
          <div className="dz-center-row-actions">
            {ids.has("workflow.run.start") && <button type="button" disabled={!!busy} onClick={() => workflowAction(w, "workflow.run.start")}>Run now</button>}
            {w.status === "enabled" && ids.has("workflow.disable")
              ? <button type="button" disabled={!!busy} onClick={() => workflowAction(w, "workflow.disable")}>Pause</button>
              : ids.has("workflow.enable") && <button type="button" disabled={!!busy} onClick={() => workflowAction(w, "workflow.enable")}>Enable</button>}
          </div>
        </article>)}</div>
        : <Empty title="No Personal workflows found">Your account has no workflow definitions visible to its current permissions.</Empty>}
      {!!runs.length && <><div className="dz-center-section-header"><h3>Recent execution</h3><span className="dz-center-muted">{runs.length} runs returned</span></div>
      <div className="dz-center-list">{runs.slice(0,20).map((run,index) => <div className="dz-center-row" key={run.id || index}>
        <span className="dz-center-provider" aria-hidden="true">◈</span>
        <div className="dz-center-row-body"><strong>{workflows.find(w => w.id === run.workflow_id)?.name || "Workflow execution"}</strong>
          <small>{run.status || "Unknown"} · {run.created_at ? new Date(run.created_at).toLocaleString() : "Time unavailable"}</small></div>
        <Tag>{run.status || "Unknown"}</Tag></div>)}</div></>}
      <p className="dz-center-fineprint">Run, pause and enable use live Personal capabilities. Some actions may require a separate human approval. Creating or editing workflow definitions needs a validated workflow builder.</p>
    </div>;
  };

  if (!open) return null;
  return createPortal(<div className="dz-center-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)setOpen(false);}}>
    <section ref={dialogRef} className="dz-center-shell" role="dialog" aria-modal="true" aria-labelledby="dz-center-title">
      <aside className="dz-center-rail"><div className="dz-center-brand"><span className="dz-center-mark">✳</span><strong id="dz-center-title">Your DragonZpyder</strong></div>
        <p className="dz-center-rail-caption">PERSONAL WORKSPACE</p>
        <nav aria-label="Capability center">{pages.map(item => <button key={item.id} className={page===item.id?"selected":""} aria-current={page===item.id?"page":undefined} onClick={()=>choose(item.id)}>
          <span aria-hidden="true">{item.glyph}</span>{item.label}</button>)}</nav>
        <div className="dz-center-rail-foot">Everything here is scoped to your signed-in account.</div>
      </aside>
      <div className="dz-center-content"><header className="dz-center-top"><span>Personal <span aria-hidden="true">/</span> {current?.label}</span><button type="button" onClick={()=>setOpen(false)} aria-label="Close capability center">Close <span aria-hidden="true">×</span></button></header>
        <div className="dz-center-body">
        {page==="connections" && renderConnections()}
        {page==="capabilities" && renderCapabilities()}
        {page==="approvals" && renderApprovals()}
        {page==="workspaces" && renderWorkspaces()}
        {page==="identity" && renderIdentity()}
        {page==="tasks" && renderTasks()}
        {message && <p className="dz-center-message" role="status">{message}</p>}
        </div>
      </div>
    </section>
  </div>, document.body);
}
