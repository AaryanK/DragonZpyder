import React from "react";
import { CommandPalette, QuickAddMenu, WorkspaceHub } from "./WorkspaceControls.jsx";


/**
 * Browser-only camera attachment.
 * Capture stays in the browser until the user explicitly sends the draft;
 * it enters the already governed AI Mesh attachment handler.
 */
function CameraAttachment() {
  const [open, setOpen] = React.useState(false);
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
    {open && <div className="camera-capture-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) close(); }}>
      <section id="camera-capture-panel" className="camera-capture-panel"
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
      </section></div>}
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
        <a className="brand" href="/" aria-label="DragonZpyder home"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" alt=""/><span>DragonZpyder</span></a>
        <button className="icon-btn mobile-only" id="close-sidebar" aria-label="Close sidebar">×</button>
      </div>
      <div className="workspace-switcher" aria-label="Current workspace">
        <span className="workspace-switcher-icon" aria-hidden="true">✦</span>
        <span><strong>Personal</strong><small>Conversations & tools</small></span>
        <span className="workspace-switcher-check" aria-hidden="true">✓</span>
      </div>
      <div className="sidebar-navigation" aria-label="Navigation">
        <a className="nav-link selected" href="/app" aria-current="page"><span className="nav-glyph" aria-hidden="true">▣</span> Conversations <span className="nav-current">Current</span></a>
        <a className="nav-link" href="/account"><span className="nav-glyph" aria-hidden="true">◎</span> Account &amp; connections</a>
      </div>
      <button className="new-chat" id="new-chat"><span aria-hidden="true">＋</span> New chat</button>
      <div className="sidebar-search-wrap"><span aria-hidden="true">⌕</span><input type="search" id="conversation-search" placeholder="Find conversations" aria-label="Find conversations" autoComplete="off"/></div>
      <div className="sidebar-label">Your conversations</div>
      <nav className="conversation-list" id="conversation-list" aria-label="Recent conversations"></nav>
      <div className="sidebar-spacer"></div>
      <div className="sidebar-footer-label">WORKSPACE</div>
      <WorkspaceHub />
      <button className="side-action" id="approvals-button"><span>Approvals</span><span className="badge-count" id="approval-count" hidden>0</span></button>
      <a className="side-action" href="https://operly.dragonzpyder.xyz/" target="_blank" rel="noreferrer"><span>Open Operly</span><span aria-hidden="true">↗</span></a>
      <a className="side-action" href="/"><span>About DragonZpyder</span><span aria-hidden="true">↗</span></a>
    </aside>
    <section className="workspace">
      <header className="workspace-head">
        <button className="icon-btn mobile-only" id="open-sidebar" aria-label="Open sidebar">☰</button>
        <div className="workspace-heading"><div className="workspace-breadcrumb"><span>DragonZpyder</span><span aria-hidden="true">/</span><strong>Personal AI</strong></div><div className="runtime-status"><span className="status-dot" id="status-dot"></span><span id="status-text">Checking runtime…</span></div></div>
        <div className="head-actions"><button type="button" className="dz-command-trigger" id="dz-command-trigger" title="Search commands · Ctrl/⌘ K" aria-label="Open command palette" onClick={() => window.dispatchEvent(new Event("dragonzpyder:command-open"))}>⌘</button><button className="theme-toggle" id="workspace-theme-toggle" type="button" aria-label="Switch to dark appearance" title="Toggle appearance"><span id="workspace-theme-icon" aria-hidden="true">☾</span></button><span className="head-privacy"><span aria-hidden="true">◈</span> Your private workspace</span><button className="ghost-btn" id="approvals-top">Approvals</button><button className="profile-btn" id="profile-button" aria-label="Account menu"><span id="profile-initial">D</span></button></div>
      </header>
      <main className="chat-main" id="chat-main">
        <section className="empty-state" id="empty-state">
          <div className="welcome-emblem"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" alt="" className="hero-logo"/></div>
          <div className="eyebrow">YOUR INTELLIGENCE WORKSPACE</div>
          <h1>What will we <em>create today?</em></h1>
          <p>Talk through an idea, analyze something complex, or put your AI agents to work. Your tools are right here when you need them.</p>
          <div className="welcome-section-title">Explore what you can do <span aria-hidden="true">↗</span></div>
          <div className="prompt-grid">
            <button className="prompt-chip" data-prompt="Help me understand a new idea."><span className="prompt-icon" aria-hidden="true">✧</span><span><strong>Research &amp; analyze</strong><small>Dig deeper into an idea.</small></span><span className="prompt-arrow" aria-hidden="true">↗</span></button>
            <button className="prompt-chip" data-prompt="Help me make a clear plan for this week."><span className="prompt-icon" aria-hidden="true">⌘</span><span><strong>Plan with me</strong><small>Make a clear plan for this week.</small></span><span className="prompt-arrow" aria-hidden="true">↗</span></button>
            <button className="prompt-chip" data-prompt="Help me draft an email I can review."><span className="prompt-icon" aria-hidden="true">✉</span><span><strong>Create something</strong><small>Draft, design or work on a project.</small></span><span className="prompt-arrow" aria-hidden="true">↗</span></button>
            <button className="prompt-chip" data-prompt="Show me which connected tools I can use."><span className="prompt-icon" aria-hidden="true">◎</span><span><strong>Use agents &amp; tools</strong><small>See what tools you can connect.</small></span><span className="prompt-arrow" aria-hidden="true">↗</span></button>
          </div>
        </section>
        <section className="messages" id="messages" aria-live="polite"></section>
      </main>
      <footer className="composer-wrap">
        <span id="dictation-feedback" className="dictation-feedback" role="status" aria-live="polite" hidden></span>
        <form className="composer unified-composer" id="composer" aria-label="Chat message composer">
          <div id="mesh-attachments" className="mesh-attachments" hidden></div>
          <textarea id="message-input" rows="2" maxLength="12000" placeholder="Ask, create, or give DragonZpyder a task…" aria-label="Message DragonZpyder"></textarea>
          <div className="composer-toolbar">
            <div className="composer-left">
              <QuickAddMenu camera={<CameraAttachment />} />
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
              <button className="send-button" id="send-button" type="submit" aria-label="Send message" hidden>↑</button>
            </div>
          </div>
        </form>
        <div id="mesh-status" className="mesh-status" role="status" aria-live="polite" hidden></div>
        <div className="composer-note" id="composer-note">DragonZpyder can make mistakes. Important actions need your review. Use Ctrl/⌘+Shift+C for the camera.</div>
      </footer>
    </section>
  </div>
  <CommandPalette />
  <section className="companion-panel" id="companion-panel" role="dialog" aria-modal="true" aria-label="Live companion" hidden>
    <div className="companion-card"><div className="eyebrow">DragonZpyder / Live companion</div><h2>Let's talk.</h2>
    <div className="companion-bars" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
    <p id="companion-status" role="status" aria-live="polite">Ready</p>
    <div className="companion-transcript" id="companion-transcript" aria-label="Live transcript"></div>
    <div className="companion-actions"><button type="button" id="companion-mute" disabled>Mute</button><button type="button" id="companion-end">End conversation</button></div>
    <p className="companion-foot">Voice is streamed to the provider. Connected actions still require Operly permissions and approvals.</p>
    </div><audio id="companion-audio" autoPlay playsInline></audio></section>
  <div className="modal-backdrop" id="auth-modal" hidden><section className="modal auth-card" role="dialog" aria-modal="true" aria-labelledby="auth-title"><a className="brand auth-brand" href="/"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" alt=""/><span>DragonZpyder</span></a><div className="eyebrow">Private personal runtime</div><h2 id="auth-title">Sign in to your Personal AI</h2><p className="modal-copy">DragonZpyder uses your existing Operly account and converts the session to Personal-only authority before running tasks.</p><form id="login-form" className="login-form"><label>Email<input id="login-email" type="email" autoComplete="email" required/></label><label>Password<input id="login-password" type="password" autoComplete="current-password" required/></label><button className="primary-btn" id="login-button" type="submit">Sign in</button></form><div className="form-error" id="login-error" hidden></div><p className="small-copy">New to DragonZpyder? <a href="/account?mode=signup">Create an account</a> · <a href="/account">Continue with Google</a> · <a href="/account?mode=forgot">Forgot password?</a></p></section></div>
  <div className="drawer-backdrop" id="approvals-drawer" hidden><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="approvals-title"><div className="drawer-head"><div><div className="eyebrow">Human boundary</div><h2 id="approvals-title">Pending approvals</h2></div><button className="icon-btn" id="close-approvals" aria-label="Close approvals">×</button></div><p className="modal-copy">Review the exact action and content before allowing DragonZpyder to execute it.</p><div id="approval-list" className="approval-list"></div></aside></div>
  <div className="menu" id="profile-menu" hidden><div className="menu-title" id="session-label">Personal session</div><a className="menu-account-link" href="/account">My account & connections ↗</a><button id="logout-button">Sign out</button></div>
  <div className="toast" id="toast" hidden></div>
  
    </>
  );
}
