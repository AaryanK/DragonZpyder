import React, { useCallback, useEffect, useState } from "react";
import "./TaskPanel.css";

function cookie(name) {
  const pair = document.cookie.split(";").map(v => v.trim())
    .find(v => v.startsWith(name + "="));
  return pair ? decodeURIComponent(pair.slice(name.length + 1)) : "";
}
function csrf() {
  return cookie("__Host-operly_csrf") || cookie("operly_csrf");
}

async function taskApi(path, { method = "GET", body, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    const token = csrf();
    if (!token) throw new Error("Your secure session token is missing. Sign in again.");
    headers["X-CSRF-Token"] = token;
  }
  const response = await fetch(path, {
    method, headers, signal, cache: "no-store", credentials: "same-origin",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Sign in to your Personal account.");
    if (response.status === 403) throw new Error("Your session is not authorized for this task.");
    if (response.status === 503) throw new Error("The harness task worker is not enabled in this environment.");
    throw new Error("Task request failed (" + response.status + ").");
  }
  return response.json();
}

function when(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}
const terminal = new Set(["completed", "incomplete", "failed", "cancelled"]);

export function TaskPanel() {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [goal, setGoal] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);

  const refresh = useCallback(async (signal) => {
    const response = await taskApi("/api/harness/tasks", { signal });
    if (signal?.aborted) return;
    const items = Array.isArray(response.tasks) ? response.tasks : [];
    setTasks(items);
    setConnected(true);
    const id = selected?.task_id || items[0]?.task_id;
    if (!id) return;
    const detail = await taskApi("/api/harness/tasks/" + encodeURIComponent(id), { signal });
    if (!signal?.aborted) setSelected(detail);
  }, [selected?.task_id]);

  useEffect(() => {
    if (!open) return;
    const abort = new AbortController();
    let running = false;
    const poll = async () => {
      if (running || abort.signal.aborted) return;
      running = true;
      try {
        await refresh(abort.signal);
        if (!abort.signal.aborted) setError("");
      } catch (err) {
        if (!abort.signal.aborted) { setConnected(false); setError(err.message); }
      } finally { running = false; }
    };
    poll();
    const interval = setInterval(poll, 2000);
    return () => { abort.abort(); clearInterval(interval); };
  }, [open, refresh]);

  async function start(kind) {
    if (sending) return;
    const prompt = kind === "probe"
      ? "Verify the Hatchet worker and activity ledger. Do not call a model."
      : goal.trim();
    if (!prompt) { setError("Enter a goal for DragonZpyder."); return; }
    setSending(true);
    setError("");
    try {
      const created = await taskApi("/api/harness/tasks", {
        method: "POST",
        body: { request_id: crypto.randomUUID(), kind, goal: prompt },
      });
      const details = await taskApi("/api/harness/tasks/" + encodeURIComponent(created.task_id));
      setSelected(details);
      if (kind === "agent") setGoal("");
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setSending(false); }
  }

  async function cancel() {
    if (!selected || terminal.has(selected.status)) return;
    try {
      await taskApi("/api/harness/tasks/" + encodeURIComponent(selected.task_id) + "/cancel",
        { method: "POST", body: {} });
      await refresh();
    } catch (err) { setError(err.message); }
  }

  return <>
    <button type="button" className="side-action" aria-expanded={open}
      aria-controls="dz-task-panel" onClick={() => setOpen(v => !v)}>
      <span><span aria-hidden="true">◷</span> Tasks &amp; activity</span>
      <span aria-hidden="true">↗</span>
    </button>
    {open && <div className="dz-task-backdrop" onMouseDown={e => {
      if (e.target === e.currentTarget) setOpen(false);
    }}>
      <section id="dz-task-panel" className="dz-task-panel" aria-label="DragonZpyder tasks">
        <div className="dz-task-head">
          <div><div className="dz-task-eyebrow">DRAGONZPYDER / HARNESS</div>
            <h2>Tasks <span className={connected ? "dz-live-dot online" : "dz-live-dot"} aria-label={connected ? "Connected" : "Disconnected"}/></h2>
            <p>See your agent work and operational events. Refreshes every 2 seconds.</p></div>
          <button type="button" className="dz-task-close" onClick={() => setOpen(false)} aria-label="Close tasks">×</button>
        </div>
        <div className="dz-task-body">
          <div className="dz-task-left">
            <form onSubmit={e => { e.preventDefault(); start("agent"); }} className="dz-task-compose">
              <label htmlFor="dz-goal">Give the harness a goal</label>
              <textarea id="dz-goal" placeholder="Research a problem, explain the evidence, and prepare a plan…"
                value={goal} onChange={e => setGoal(e.target.value)} maxLength={5000} rows={3}/>
              <p>Agent mode uses a bounded LangGraph run. External account actions are disabled.</p>
              <div className="dz-task-actions">
                <button type="submit" disabled={sending || !goal.trim()} className="dz-task-primary">
                  {sending ? "Submitting…" : "Run agent"}
                </button>
                <button type="button" onClick={() => start("probe")} disabled={sending}>Test worker</button>
              </div>
            </form>
            <div className="dz-task-list-header">Recent tasks <span>{tasks.length}</span></div>
            <div className="dz-task-list">
              {tasks.length === 0 && <div className="dz-task-muted">No tasks yet. Test the worker to check connectivity.</div>}
              {tasks.map(item => <button key={item.task_id} type="button"
                className={"dz-task-item" + (item.task_id === selected?.task_id ? " chosen" : "")}
                onClick={() => { setSelected(item); }}>
                <span className="dz-task-kind">{item.kind === "agent" ? "Agent task" : "Worker test"}</span>
                <span className={"dz-task-status status-" + item.status}>{item.status.replace("_", " ")}</span>
                <small>{when(item.created_at)}</small>
              </button>)}
            </div>
          </div>
          <div className="dz-task-right">
            {error && <div className="dz-task-error" role="alert">{error}</div>}
            {selected ? <>
              <div className="dz-task-detail-head">
                <div><div className="dz-task-eyebrow">EXECUTION <code>{selected.task_id?.slice(0, 8)}</code></div>
                  <h3>{selected.kind === "agent" ? "Agent execution" : "Worker readiness"}</h3>
                  <p>Status: <strong>{selected.status}</strong> · Attempts: {selected.attempts ?? 0}</p>
                </div>
                {!terminal.has(selected.status) && <button type="button" onClick={cancel}>Cancel</button>}
              </div>
              <div className="dz-task-timeline" aria-live="polite">
                {(selected.events || []).map(ev => <div key={ev.event_id} className="dz-task-event">
                  <span className="dz-task-event-dot"/>
                  <div><strong>{ev.message}</strong><small>{when(ev.at)} · {ev.kind.replaceAll("_", " ")}</small></div>
                </div>)}
                {!selected.events?.length && <div className="dz-task-muted">Waiting for the first execution event…</div>}
              </div>
              {selected.answer && <div className="dz-task-result">
                <h4>Result</h4><p>{selected.answer}</p>
                {selected.objective_verified !== true && <small>Agent output; independent goal verification is not yet complete.</small>}
              </div>}
              {selected.trace_id && <p className="dz-task-trace">Trace ID: <code>{selected.trace_id}</code></p>}
            </> : <div className="dz-task-muted">Choose a task to inspect its activity.</div>}
          </div>
        </div>
      </section>
    </div>}
  </>;
}
