import React from "react";
import { createPortal } from "react-dom";
import { CommandPalette, QuickAddMenu, WorkspaceHub, SidebarToggle, ModeSwitchConfirm, useModalFocus } from "./WorkspaceControls.jsx";
import { WorkspaceCenter } from "./WorkspaceCenter.jsx";
import { VoiceOrb } from "./VoiceOrb.jsx";
import "./workspace-center.css";
import { UiIcon } from "./UiIcon.jsx";


/**
 * Browser-only camera attachment.
 * Capture stays in the browser until the user explicitly sends the draft;
 * it enters the already governed AI Mesh attachment handler.
 */
function CameraAttachment() {
  const [open, setOpen] = React.useState(false);
  const dialogRef = React.useRef(null);
  useModalFocus(dialogRef,open);
  const [error, setError] = React.useState("");
  const preview = React.useRef(null);
  const stream = React.useRef(null);
  const close = React.useCallback(() => {
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    setOpen(false);
  }, []);
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const start = async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera access is not supported in this browser.");
        const media = await navigator.mediaDevices.getUserMedia({
          audio: false, video: { facingMode: { ideal: "environment" } },
        });
        if (cancelled) { media.getTracks().forEach(track => track.stop()); return; }
        stream.current = media;
        if (preview.current) {
          preview.current.srcObject = media;
          await preview.current.play().catch(() => {});
        }
      } catch (cause) {
        if (!cancelled) setError(cause?.name === "NotAllowedError"
          ? "Camera permission was declined. You can attach an image instead."
          : "Could not start the camera. Check browser permissions and device availability.");
      }
    };
    start();
    return () => { cancelled = true; stream.current?.getTracks().forEach(track => track.stop()); stream.current = null; };
  }, [open]);
  React.useEffect(() => {
    const handleKeys = (event) => {
      if (event.key === "Escape" && open) close();
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "c") {
        event.preventDefault();
        setError("");
        if (open) close(); else setOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeys);
    return () => window.removeEventListener("keydown", handleKeys);
  }, [open, close]);
  const capture = async () => {
    const video = preview.current;
    const upload = document.getElementById("mesh-upload");
    if (!video || !upload || !video.videoWidth || !video.videoHeight) {
      setError("Camera is still starting. Try again when the image is visible.");
      return;
    }
    const canvas = document.createElement("canvas");
    const maxSide = 1500;
    const scale = Math.min(1, maxSide / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const image = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.78));
    if (!image) { setError("Could not capture an image."); return; }
    const file = new File([image], "camera-capture.jpg", { type: "image/jpeg" });
    const files = new DataTransfer();
    files.items.add(file);
    upload.files = files.files;
    upload.dispatchEvent(new Event("change", { bubbles: true }));
    close();
  };
  return <>
    <button className="camera-button" id="camera-capture-toggle" type="button"
      aria-label="Capture image from camera" title="Capture a photo to attach · Ctrl/⌘+Shift+C"
      aria-controls="camera-capture-panel" aria-expanded={open}
      onClick={() => { setError(""); setOpen(true); }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M3 7h4l2-3h6l2 3h4v13H3z" /><circle cx="12" cy="13" r="4"/>
      </svg>
      <span>Capture photo<small>Preview and attach an image</small></span>
    </button>
    {open && createPortal(<div className="camera-capture-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <section ref={dialogRef} id="camera-capture-panel" className="camera-capture-panel"
        role="dialog" aria-modal="true" aria-labelledby="camera-capture-title">
        <div className="camera-capture-header"><div><div className="eyebrow">Camera / local preview</div>
          <h2 id="camera-capture-title">Capture an image</h2></div>
          <button type="button" onClick={close} aria-label="Close camera">×</button>
        </div>
        <div className="camera-capture-view"><video ref={preview} muted autoPlay playsInline /></div>
        {error && <p className="camera-capture-error" role="alert">{error}</p>}
        <p className="camera-capture-note">The preview stays on your device. Capturing attaches one image to your draft; nothing is sent until you submit it. This may switch the composer to AI Mesh.</p>
        <div className="camera-capture-actions">
          <button type="button" className="camera-cancel" onClick={close}>Cancel</button>
          <button type="button" className="camera-capture-action" onClick={capture} disabled={Boolean(error)}>Capture photo</button>
        </div>
      </section></div>, document.body)}
  </>;
}

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function PersonalTemplate() {
  return (
    <>

  <div className="app-shell" id="app-shell">
    <aside className="sidebar" id="sidebar">
      <div className="sidebar-head">
        <a className="brand" href="/" aria-label="DragonZpyder home"><img src="/brand-icon.png" alt=""/><span>DragonZpyder</span></a>
        <button className="icon-btn mobile-only" id="close-sidebar" aria-label="Close sidebar"><UiIcon name="close"/></button>
      </div>
      <button className="new-chat" id="new-chat"><UiIcon name="edit"/> New chat</button>
      <div className="sidebar-search-wrap"><UiIcon name="search"/><input type="search" id="conversation-search" placeholder="Search chats" aria-label="Find conversations" autoComplete="off"/></div>
      <div className="sidebar-navigation" aria-label="Navigation">
        <button type="button" className="nav-link dz-center-nav-link" onClick={() => window.dispatchEvent(new CustomEvent("dragonzpyder:center-open", { detail: { page: "connections" } }))}><span className="nav-glyph"><UiIcon name="plug"/></span> Connections &amp; tools</button>
        <button type="button" className="nav-link dz-center-nav-link" onClick={() => window.dispatchEvent(new CustomEvent("dragonzpyder:center-open", { detail: { page: "tasks" } }))}><span className="nav-glyph"><UiIcon name="tasks"/></span> Tasks &amp; goals</button>
      </div>
      <div className="sidebar-label">Chats</div>
      <nav className="conversation-list" id="conversation-list" aria-label="Recent conversations"></nav>
      <div className="sidebar-spacer"></div>
      <WorkspaceHub />
      <button className="side-action dz-mobile-commands" type="button" onClick={() => { document.getElementById("close-sidebar")?.click(); window.dispatchEvent(new Event("dragonzpyder:command-open")); }}><span className="dz-footer-icon"><UiIcon name="search"/></span><span>Commands</span></button>
      <button className="side-action" id="approvals-button"><span className="dz-footer-icon"><UiIcon name="shield"/></span><span>Approvals</span><span className="badge-count" id="approval-count" hidden>0</span></button>
      <a className="side-action" href="/account"><span className="dz-footer-icon"><UiIcon name="user"/></span><span>Settings</span></a>
    </aside>
    <section className="workspace">
      <header className="workspace-head">
        <button className="icon-btn mobile-only" id="open-sidebar" aria-label="Open sidebar"><UiIcon name="menu"/></button>
        <SidebarToggle />
        <div className="workspace-heading"><div className="workspace-breadcrumb"><strong>Personal</strong></div><div className="runtime-status"><span className="status-dot" id="status-dot"></span><span id="status-text">Checking runtime…</span></div></div>
        <div className="head-actions"><button type="button" className="dz-command-trigger" id="dz-command-trigger" title="Search commands · Ctrl/⌘ K" aria-label="Open command palette" onClick={() => window.dispatchEvent(new Event("dragonzpyder:command-open"))}><UiIcon name="search"/></button><button className="theme-toggle" id="workspace-theme-toggle" type="button" aria-label="Switch to dark appearance" title="Toggle appearance"><span id="workspace-theme-icon" aria-hidden="true"><UiIcon name="moon" className="dz-theme-moon"/><UiIcon name="sun" className="dz-theme-sun"/></span></button><button className="ghost-btn" id="approvals-top">Approvals</button><button type="button" className="dz-mobile-new" aria-label="New conversation" onClick={() => document.getElementById("new-chat")?.click()}><UiIcon name="edit"/></button><button className="profile-btn" id="profile-button" aria-label="Account menu" aria-expanded="false"><span id="profile-initial">?</span><img id="profile-avatar" alt="" hidden referrerPolicy="no-referrer"/></button></div>
      </header>
      <main className="chat-main" id="chat-main">
        <section className="empty-state" id="empty-state">
          <div className="welcome-emblem"><img src="/brand-icon.png" alt="" className="hero-logo"/></div>
          
          <h1>What shall we work on?</h1>
          <p>Ask a question or give DragonZpyder a task.</p>
          <div className="welcome-section-title">Get started</div>
          <div className="prompt-grid">
            <button className="prompt-chip" data-prompt="Help me think through a new idea."><UiIcon name="idea"/>Explore an idea</button>
            <button className="prompt-chip" data-prompt="Help me plan a project from scratch."><UiIcon name="plan"/>Plan a project</button>
            <button className="prompt-chip" data-prompt="Help me turn my notes into a clear draft."><UiIcon name="edit"/>Write something</button>
          </div>
        </section>
        <section className="messages" id="messages" aria-live="polite"></section>
      </main>
      <button type="button" id="dz-jump-latest" className="dz-jump-latest" aria-label="Jump to latest message" hidden><span aria-hidden="true">↓</span> Latest messages</button>
      <footer className="composer-wrap">
        <div id="dz-runtime-notice" role="status" className="dz-runtime-notice" hidden>Chat is currently unavailable. You are signed in; you can edit your draft, but sending is disabled.</div>
        <span id="dictation-feedback" className="dictation-feedback" role="status" aria-live="polite" hidden></span>
        <form className="composer unified-composer" id="composer" aria-label="Chat message composer">
          <div id="mesh-attachments" className="mesh-attachments" hidden></div>
          <textarea id="message-input" rows="2" maxLength="12000" placeholder="Message DragonZpyder…" aria-label="Message DragonZpyder"></textarea>
          <div className="composer-toolbar">
            <div className="composer-left">
              <QuickAddMenu camera={<CameraAttachment />} />
              <label className="mesh-switch native-consent" hidden><input id="native-computer-consent" type="checkbox" /> Use isolated computer</label>
              <label className="mesh-switch native-consent" hidden><input id="native-media-consent" type="checkbox" /> Use media tools</label>
              <label className="mesh-switch native-consent" hidden><input id="native-durable-consent" type="checkbox" /> Allow scheduled work</label>
              <button type="button" id="mesh-switch" className="mesh-switch" aria-pressed="false" title="Switch between permissioned Agent and direct AI Mesh"><span aria-hidden="true">✦</span> Agent</button>
              <div id="mesh-controls" className="mesh-controls" hidden>
                <select id="mesh-task" className="mesh-select task-select" aria-label="AI Mesh task">
                  <option value="chat">Text &amp; files</option>
                  <option value="image">Create image</option>
                  <option value="transcribe">Transcribe audio</option>
                  <option value="speech">Create speech</option>
                  <option value="video">Create video</option>
                </select>
                <select id="mesh-model" className="mesh-select model-select" aria-label="OpenRouter model"><option value="">Loading models…</option></select>
              </div>
            </div>
            <div className="composer-right">
              <button className="dictation-button" id="dictation-toggle" type="button" title="Dictate into message" aria-label="Start dictation" aria-pressed="false">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"></rect><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"></path></svg>
              </button>
              <button className="companion-launch composer-voice" id="companion-open" type="button" aria-haspopup="dialog" aria-controls="companion-panel" aria-expanded="false" aria-label="Start live AI voice conversation" title="Start a realtime two-way voice conversation"><span className="live-voice-bars" aria-hidden="true"><i></i><i></i><i></i></span><span>Live voice</span></button>
              <button className="send-button" id="send-button" type="submit" aria-label="Send message" hidden><UiIcon name="send"/></button>
            </div>
          </div>
        </form>
        <div id="mesh-status" className="mesh-status" role="status" aria-live="polite" hidden></div>
        <div className="composer-note" id="composer-note">DragonZpyder can make mistakes. Important actions need your review. Use Ctrl/⌘+Shift+C for the camera.</div>
      </footer>
    </section>
  </div>
  <CommandPalette />
  <WorkspaceCenter />
  <ModeSwitchConfirm />
  <section className="companion-panel dz-voice-orb-panel" id="companion-panel" role="dialog" aria-modal="true" aria-label="Live companion" hidden>
    <VoiceOrb />
  </section>
  <div className="modal-backdrop" id="auth-modal" hidden><section className="modal auth-card dz-session-error" role="dialog" aria-modal="true" aria-labelledby="auth-title"><img className="dz-session-mark" src="/brand-icon.png" alt="DragonZpyder"/><h2 id="auth-title">Unable to connect</h2><p className="form-error" id="login-error" role="alert" hidden></p><button type="button" id="retry-session" className="primary-btn">Try again</button><a id="dragonzpyder-central-signin-modal" href="/login">Go to sign in</a></section></div>
  <div className="drawer-backdrop" id="approvals-drawer" hidden><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="approvals-title"><div className="drawer-head"><div><div className="eyebrow">Human boundary</div><h2 id="approvals-title">Pending approvals</h2></div><button className="icon-btn" id="close-approvals" aria-label="Close approvals">×</button></div><p className="modal-copy">Review the exact action and content before allowing DragonZpyder to execute it.</p><div id="approval-list" className="approval-list"></div></aside></div>
  <div className="menu" id="profile-menu" hidden><div className="menu-title" id="session-label">Personal session</div><button type="button" onClick={() => document.getElementById("workspace-theme-toggle")?.click()}>Appearance</button><a className="menu-account-link" href="/account">Settings</a><button id="logout-button">Sign out</button></div>
  <div className="toast" id="toast" hidden></div>
  
    </>
  );
}
