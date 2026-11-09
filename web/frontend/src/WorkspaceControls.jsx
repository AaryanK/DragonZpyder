import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Progressive disclosure for the existing Personal chat. Controls call existing
// production adapters; they never bypass permission checks or create new APIs.
const act = (id) => document.getElementById(id)?.click();
const focusSearch = () => {
  const input = document.getElementById("conversation-search");
  if (!input) return;
  act("open-sidebar");
  requestAnimationFrame(() => input.focus());
};
const openWorkspace = () => window.dispatchEvent(new Event("dragonzpyder:workspace-open"));

const COMMANDS = [
  { title: "Start a new conversation", hint: "Chat", words: "new create chat", run: () => act("new-chat") },
  { title: "Find a conversation", hint: "History", words: "search conversation history", run: focusSearch },
  { title: "Attach a file", hint: "Input", words: "upload file pdf document image", run: () => act("mesh-upload") },
  { title: "Capture a photo", hint: "Camera", words: "camera picture image photo", run: () => act("camera-capture-toggle") },
  { title: "Capture your screen", hint: "Input", words: "screenshot share screen", run: () => act("screen-capture-toggle") },
  { title: "Dictate a message", hint: "Voice", words: "microphone speech voice dictation", run: () => act("dictation-toggle") },
  { title: "Start live voice", hint: "Voice", words: "voice call audio", run: () => act("companion-open") },
  { title: "Choose Agent / AI Mesh", hint: "Mode", words: "model select agent mesh", run: () => document.getElementById("mesh-switch")?.focus() },
  { title: "Review pending approvals", hint: "Safety", words: "approve permissions actions", run: () => act("approvals-top") },
  { title: "Browse Personal tools", hint: "Capabilities", words: "personal tools integrations capabilities mcp", run: () => window.dispatchEvent(new Event("dragonzpyder:personal-capabilities-open")) },
  { title: "Open workspace navigation", hint: "Navigate", words: "agents jobs projects memory files automations", run: openWorkspace },
  { title: "Account and connections", hint: "Settings", words: "account settings connected apps", run: () => { window.location.href = "/account"; } },
];


/**
 * Confirm a destructive conversational context change without performing an
 * agent action. The promise is resolved on every close path, including Escape.
 */
/**
 * Dialogs must not strand keyboard or screen-reader users behind an overlay.
 * The first tabbable control receives focus; Tab cycles inside the modal and
 * closing restores focus to the element that opened it.
 */
export function useModalFocus(dialogRef, open) {
  useEffect(() => {
    if (!open) return;
    const origin = document.activeElement;
    let cancelled = false;
    const items = () => [...(dialogRef.current?.querySelectorAll(
      "a[href],button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),[tabindex='0']"
    ) || [])].filter(el => el.getClientRects().length>0);
    requestAnimationFrame(() => { if(!cancelled) items()[0]?.focus(); });
    const onKey = event => {
      if (event.key !== "Tab") return;
      const nodes = items();
      if (!nodes.length) { event.preventDefault(); return; }
      const first=nodes[0],last=nodes[nodes.length-1];
      if (event.shiftKey && (document.activeElement===first || !dialogRef.current?.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement===last || !dialogRef.current?.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener("keydown",onKey,true);
    return () => {
      cancelled=true;
      document.removeEventListener("keydown",onKey,true);
      requestAnimationFrame(()=>origin?.focus?.());
    };
  },[dialogRef,open]);
}

export function ModeSwitchConfirm() {
  const [request, setRequest] = useState(null);
  const dialogRef = useRef(null);
  useModalFocus(dialogRef,Boolean(request));
  const cancelRef = useRef(null);
  const originRef = useRef(null);
  useEffect(() => {
    const onRequest = event => {
      if (typeof event.detail?.resolve !== "function") return;
      event.detail.handled = true;
      originRef.current = document.activeElement;
      setRequest({ resolve: event.detail.resolve });
    };
    window.addEventListener("dragonzpyder:confirm-mesh-switch", onRequest);
    return () => window.removeEventListener("dragonzpyder:confirm-mesh-switch", onRequest);
  }, []);
  useEffect(() => {
    if (!request) return;
    cancelRef.current?.focus();
    const onKey = event => {
      if (event.key === "Escape") {
        event.preventDefault(); event.stopPropagation();
        request.resolve(false); setRequest(null);
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [request]);
  const choose = decision => {
    request?.resolve(decision);
    setRequest(null);
    requestAnimationFrame(() => originRef.current?.focus?.());
  };
  return request && createPortal(
    <div className="dz-overlay dz-confirm-overlay" onMouseDown={event => {
      if (event.target === event.currentTarget) choose(false);
    }}>
      <section ref={dialogRef} className="dz-confirm-panel" role="alertdialog" aria-modal="true"
        aria-labelledby="dz-confirm-title" aria-describedby="dz-confirm-description">
        <span className="dz-kicker">Before you attach</span>
        <h2 id="dz-confirm-title">Switch to AI Mesh?</h2>
        <p id="dz-confirm-description">Files are currently handled by AI Mesh.
          Switching starts a separate conversation; the Agent conversation and its connected tools won't carry over.
          Your previous Agent conversations remain saved.</p>
        <div className="dz-confirm-actions">
          <button ref={cancelRef} type="button" onClick={() => choose(false)}>Keep Agent chat</button>
          <button type="button" onClick={() => choose(true)}>Switch and attach</button>
        </div>
      </section>
    </div>, document.body
  );
}

/** One keyboard and touch target for showing/hiding the full desktop sidebar. */
export function SidebarToggle() {
  const [expanded, setExpanded] = useState(true);
  useEffect(() => {
    let collapsed = false;
    try { collapsed = localStorage.getItem("dragonzpyder:sidebar-collapsed") === "yes"; } catch {}
    document.documentElement.classList.toggle("dz-sidebar-collapsed", collapsed);
    setExpanded(!collapsed);
  }, []);
  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    document.documentElement.classList.toggle("dz-sidebar-collapsed", !next);
    try { localStorage.setItem("dragonzpyder:sidebar-collapsed", next ? "no" : "yes"); } catch {}
  };
  return <button className="dz-sidebar-toggle" type="button" onClick={toggle}
    aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
    title={expanded ? "Hide sidebar" : "Show sidebar"} aria-expanded={expanded}
    aria-controls="sidebar">☷</button>;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);
  const dialogRef = useRef(null);
  const previousFocusRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement;
    const trap = event => {
      if (event.key !== "Tab" || !dialogRef.current) return;
      const nodes = [...dialogRef.current.querySelectorAll("button:not(:disabled),input:not(:disabled),[tabindex='0']")];
      if (!nodes.length) return;
      const first=nodes[0], last=nodes[nodes.length-1];
      if(event.shiftKey && document.activeElement===first) {event.preventDefault(); last.focus();}
      else if(!event.shiftKey && document.activeElement===last) {event.preventDefault(); first.focus();}
    };
    document.addEventListener("keydown",trap,true);
    return () => {document.removeEventListener("keydown",trap,true);previousFocusRef.current?.focus?.();};
  }, [open]);
  useEffect(() => {
    const onShortcut = event => {
      if ((event.metaKey || event.ctrlKey) && !event.shiftKey &&
          (event.key.toLowerCase() === "k" || event.key === "/")) {
        event.preventDefault(); setQuery(""); setOpen(value => !value);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    const onOpen = () => { setQuery(""); setOpen(true); };
    window.addEventListener("keydown", onShortcut);
    window.addEventListener("dragonzpyder:command-open", onOpen);
    return () => {
      window.removeEventListener("keydown", onShortcut);
      window.removeEventListener("dragonzpyder:command-open", onOpen);
    };
  }, []);
  useEffect(() => { if (open) requestAnimationFrame(() => inputRef.current?.focus()); }, [open]);
  const matching = useMemo(() => {
    const q = query.trim().toLowerCase();
    return COMMANDS.filter(command => !q || [command.title, command.hint, command.words].join(" ").toLowerCase().includes(q));
  }, [query]);
  const choose = command => { setOpen(false); command.run(); };
  return <>
    {open && createPortal(<div className="dz-overlay" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section ref={dialogRef} className="dz-command-panel" role="dialog" aria-modal="true" aria-labelledby="dz-command-title">
        <div className="dz-command-top"><strong id="dz-command-title">What would you like to do?</strong><button type="button" onClick={() => setOpen(false)} aria-label="Close commands">Esc ×</button></div>
        <input ref={inputRef} aria-label="Search DragonZpyder commands" value={query} onChange={event => setQuery(event.target.value)}
          placeholder="Search features, actions, settings…" onKeyDown={event => {
            if (event.key === "Enter" && matching[0]) { event.preventDefault(); choose(matching[0]); }
          }}/>
        <div className="dz-command-results" aria-label="Available commands">
          {matching.length ? matching.map(command =>
            <button type="button" key={command.title} onClick={() => choose(command)}>
              <span>{command.title}</span><small>{command.hint}</small>
            </button>) : <p>No matching actions. Try “camera”, “voice”, or “jobs”.</p>}
        </div>
        <div className="dz-command-foot">Windows: <kbd>Ctrl K</kbd> or <kbd>Ctrl /</kbd> · macOS: <kbd>⌘ K</kbd>. Unavailable services are not presented as working commands.</div>
      </section>
    </div>, document.body)}
  </>;
}

export function ScreenCapture() {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const video = useRef(null), current = useRef(null), generation = useRef(0);
  const dialogRef = useRef(null);
  useModalFocus(dialogRef,open);
  const stop = useCallback(() => {
    generation.current++;
    current.current?.getTracks().forEach(track => track.stop());
    current.current = null;
    setOpen(false);
  }, []);
  // getDisplayMedia must be invoked directly within the user gesture, not a
  // later React effect; otherwise browsers reject it with InvalidStateError.
  const begin = async () => {
    const request = ++generation.current;
    setError("");
    setOpen(true);
    try {
      if (!navigator.mediaDevices?.getDisplayMedia) throw new Error("unsupported");
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      if (request !== generation.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      current.current = stream;
      stream.getVideoTracks()[0]?.addEventListener("ended", stop, { once: true });
      requestAnimationFrame(() => {
        if (video.current) {
          video.current.srcObject = stream;
          video.current.play().catch(() => {});
        } else {
          stream.getTracks().forEach(track => track.stop());
        }
      });
    } catch (cause) {
      if (request === generation.current) setError(cause?.name === "NotAllowedError"
        ? "Screen selection was cancelled or denied." : "Screen capture is unavailable in this browser.");
    }
  };
  useEffect(() => () => { current.current?.getTracks().forEach(track => track.stop()); }, []);
  useEffect(() => {
    if (!open) return;
    const onEscape = event => { if (event.key === "Escape") stop(); };
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [open, stop]);
  const capture = async () => {
    const element = video.current, upload = document.getElementById("mesh-upload");
    if (!element?.videoWidth || !upload) { setError("Screen preview is still starting."); return; }
    const canvas = document.createElement("canvas");
    const factor = Math.min(1, 1600 / Math.max(element.videoWidth, element.videoHeight));
    canvas.width = Math.max(1, Math.round(element.videoWidth * factor));
    canvas.height = Math.max(1, Math.round(element.videoHeight * factor));
    canvas.getContext("2d")?.drawImage(element, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.8));
    if (!blob) { setError("Unable to capture this screen."); return; }
    const transfer = new DataTransfer();
    transfer.items.add(new File([blob], "screen-capture.jpg", { type: "image/jpeg" }));
    upload.files = transfer.files;
    upload.dispatchEvent(new Event("change", { bubbles: true }));
    stop();
  };
  return <>
    <button id="screen-capture-toggle" type="button" className="dz-menu-action"
      onClick={begin}>
      <span aria-hidden="true">▣</span><span><strong>Capture screen</strong><small>Preview and attach a screenshot</small></span>
    </button>
    {open && createPortal(<div className="dz-overlay dz-screen-overlay" onMouseDown={event => { if (event.target === event.currentTarget) stop(); }}>
      <section ref={dialogRef} className="dz-screen-panel" role="dialog" aria-modal="true" aria-labelledby="dz-screen-title">
        <div className="dz-screen-head"><div><span className="dz-kicker">Local screen preview</span><h2 id="dz-screen-title">Capture your screen</h2></div>
          <button aria-label="Close screen preview" type="button" onClick={stop}>×</button></div>
        <video ref={video} autoPlay muted playsInline />
        {error && <p className="dz-screen-error" role="alert">{error}</p>}
        <p>Only a screenshot you explicitly capture is added to the message. Nothing is sent until you submit; the existing attachment flow switches to AI Mesh.</p>
        <div className="dz-screen-actions"><button type="button" onClick={stop}>Cancel</button>
          <button type="button" onClick={capture} disabled={!!error}>Attach screenshot</button></div>
      </section>
    </div>, document.body)}
  </>;
}

export function QuickAddMenu({ camera }) {
  const [open, setOpen] = useState(false);
  const parent = useRef(null);
  useEffect(() => {
    if (!open) return;
    const away = event => { if (parent.current && !parent.current.contains(event.target)) setOpen(false); };
    const esc = event => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  return <div ref={parent} className="dz-add-wrap">
    <button type="button" id="dz-add-toggle" className="dz-add-button" title="Add a file, photo, or screen"
      aria-expanded={open} aria-controls="dz-add-menu" aria-haspopup="true"
      onClick={() => setOpen(value => !value)} aria-label="Open attachment and input menu">＋</button>
    <div className="dz-add-menu" id="dz-add-menu" role="group" aria-label="Input options" hidden={!open}>
      <div className="dz-menu-label">Add to this conversation</div>
      <label id="mesh-file-label" className="dz-menu-action" role="button" tabIndex={open ? 0 : -1}
        title="Attach an image or document">
        <span aria-hidden="true">▤</span><span><strong>Attach files</strong><small>Images, documents, audio</small></span>
        <input id="mesh-upload" type="file" multiple
          accept="image/png,image/jpeg,image/webp,.pdf,.docx,.txt,.md,.csv,.json,.py,.log,audio/*"
          aria-label="Choose files to attach" onChange={() => setOpen(false)}/>
      </label>
      {camera}
      <ScreenCapture />
      <button type="button" className="dz-menu-action" onClick={() => { setOpen(false); openWorkspace(); }}>
        <span aria-hidden="true">◈</span><span><strong>More capabilities</strong><small>Agents, projects and tools</small></span>
      </button>
      <p className="dz-menu-foot">Files and screenshots use AI Mesh. Agent tools require their own permissions.</p>
    </div>
  </div>;
}

const HUB_SECTIONS = [
  { title: "Conversations", icon: "▣", status: "Available", detail: "Search your saved chats and start a new conversation.", action: focusSearch },
  { title: "Approvals", icon: "◉", status: "Available", detail: "Review actions before DragonZpyder is allowed to execute them.", action: () => act("approvals-top") },
  { title: "Connections", icon: "⌘", status: "Available", detail: "Manage your account and supported integrations.", action: () => { window.location.href = "/account"; } },
  { title: "Personal tools", icon: "⌕", status: "Available", detail: "Search only capabilities currently authorized for your Personal account.", action: () => window.dispatchEvent(new Event("dragonzpyder:personal-capabilities-open")) },
  { title: "Models", icon: "✦", status: "Available in Mesh", detail: "Switch to AI Mesh to select a supported model and see its pricing.", action: () => document.getElementById("mesh-switch")?.focus() },
  { title: "Agents", icon: "◇", status: "Integration planned", detail: "Agent-team configuration and orchestration are not wired into this chat yet." },
  { title: "Jobs & automations", icon: "◷", status: "Integration planned", detail: "Background worker infrastructure is being tested separately; there is no live jobs UI here yet." },
  { title: "Projects & files", icon: "▤", status: "Planned", detail: "Permanent projects and a cross-chat artifact library are not yet released." },
  { title: "Memory", icon: "◈", status: "Planned", detail: "A dedicated memory review and controls page is not yet available." },
];

/**
 * Install the current HTTPS origin as a desktop web app in Chromium browsers.
 * Windows Edge can also install from its Apps menu if no prompt is available.
 * No service worker: authenticated requests are never cached for offline use.
 */
export function DesktopInstallAction({ pendingPrompt, consumePrompt }) {
  const [platform, setPlatform] = useState("unknown");
  const [installed, setInstalled] = useState(false);
  const [help, setHelp] = useState("");
  useEffect(() => {
    const os = navigator.userAgentData?.platform || navigator.platform || navigator.userAgent || "";
    setPlatform(/win(dows|32|64)/i.test(os) ? "windows" : "other");
    setInstalled(window.matchMedia("(display-mode: standalone)").matches);
    const done = () => setInstalled(true);
    window.addEventListener("appinstalled", done);
    return () => window.removeEventListener("appinstalled", done);
  }, []);
  const install = async () => {
    if (!pendingPrompt) {
      setHelp("On Windows, open Microsoft Edge ··· → Apps → Install this site as an app. In Chrome, open the browser menu → Cast, save and share → Install page as app (wording varies).");
      return;
    }
    const event = pendingPrompt;
    consumePrompt();
    try {
      await event.prompt();
      const result = await event.userChoice;
      if (result?.outcome !== "accepted") setHelp("Installation cancelled. You can also use your browser’s Install app menu.");
    } catch {
      setHelp("The install prompt could not open. Use your browser's Install app menu instead.");
    }
  };
  if (platform !== "windows") return null;
  return <section className="dz-desktop-install" aria-label="Windows desktop installation">
    <div className="dz-desktop-install-head"><span aria-hidden="true">⊞</span><div>
      <strong>{installed ? "DragonZpyder desktop app" : "DragonZpyder for Windows"}</strong>
      <small>{installed ? "Running in the installed app window" :
        "Use the same chat and tools in an app-style Edge or Chrome window"}</small></div>
    </div>
    {!installed && <button type="button" onClick={install}>
      {pendingPrompt ? "Install desktop app" : "How to install on Windows"} <span aria-hidden="true">↗</span>
    </button>}
    {help && <p className="dz-desktop-install-help" role="status">{help}</p>}
    <p className="dz-desktop-install-note">Requires internet and a supported browser. Not a native .exe or an offline assistant.</p>
  </section>;
}

export function WorkspaceHub() {
  const [open, setOpen] = useState(false);
  const dialogRef = useRef(null);
  useModalFocus(dialogRef,open);
  // Listen from initial page mount; Chrome/Edge may fire before the drawer opens.
  const [pendingPrompt, setPendingPrompt] = useState(null);
  useEffect(() => {
    const handlePrompt = event => { event.preventDefault(); setPendingPrompt(event); };
    window.addEventListener("beforeinstallprompt", handlePrompt);
    return () => window.removeEventListener("beforeinstallprompt", handlePrompt);
  }, []);
  useEffect(() => {
    const show = () => setOpen(true);
    const keys = event => { if (event.key === "Escape") setOpen(false); };
    window.addEventListener("dragonzpyder:workspace-open", show);
    window.addEventListener("keydown", keys);
    return () => { window.removeEventListener("dragonzpyder:workspace-open", show); window.removeEventListener("keydown", keys); };
  }, []);
  return <>
    <button type="button" className="dz-workspace-trigger" id="dz-workspace-trigger" onClick={() => setOpen(true)}>
      <span>◈</span> Explore workspace <span aria-hidden="true">↗</span>
    </button>
    {open && createPortal(<div className="dz-hub-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setOpen(false); }}>
      <aside ref={dialogRef} className="dz-hub" role="dialog" aria-modal="true" aria-labelledby="dz-hub-title">
        <div className="dz-hub-top"><div><span className="dz-kicker">DragonZpyder / Workspace</span><h2 id="dz-hub-title">Everything, in one place.</h2></div>
          <button type="button" aria-label="Close workspace navigation" onClick={() => setOpen(false)}>×</button></div>
        <p className="dz-hub-lead">The chat stays minimal. Find your tools, jobs, and settings here without filling the conversation screen.</p>
        <div className="dz-hub-list">{HUB_SECTIONS.map(section => {
          const actionable = !!section.action;
          return <button key={section.title} type="button" className="dz-hub-row"
            disabled={!actionable} onClick={() => { setOpen(false); section.action?.(); }}>
            <span className="dz-hub-icon" aria-hidden="true">{section.icon}</span>
            <span className="dz-hub-rowcopy"><strong>{section.title}</strong><small>{section.detail}</small></span>
            <span className={"dz-hub-status" + (actionable ? " ready" : "")}>{section.status}</span>
          </button>;
        })}</div>
        <DesktopInstallAction pendingPrompt={pendingPrompt} consumePrompt={() => setPendingPrompt(null)} />
        <button type="button" className="dz-hub-command" onClick={() => { setOpen(false); window.dispatchEvent(new Event("dragonzpyder:command-open")); }}>⌘ Search all available commands</button>
      </aside>
    </div>, document.body)}
  </>;
}
