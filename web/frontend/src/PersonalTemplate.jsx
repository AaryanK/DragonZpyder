import React from "react";

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
      <button className="new-chat" id="new-chat">＋ New conversation</button>
      <div className="sidebar-label">Recent</div>
      <nav className="conversation-list" id="conversation-list" aria-label="Recent conversations"></nav>
      <div className="sidebar-spacer"></div>
      <button className="side-action" id="approvals-button"><span>Approvals</span><span className="badge-count" id="approval-count" hidden>0</span></button>
      <a className="side-action" href="/">About DragonZpyder</a>
      <a className="side-action" href="https://operly.dragonzpyder.xyz/" target="_blank" rel="noreferrer">Open Operly ↗</a>
    </aside>
    <section className="workspace">
      <header className="workspace-head">
        <button className="icon-btn mobile-only" id="open-sidebar" aria-label="Open sidebar">☰</button>
        <div className="runtime-status"><span className="status-dot" id="status-dot"></span><span id="status-text">Checking runtime…</span></div>
        <div className="head-actions"><button className="companion-launch" id="companion-open" type="button" aria-haspopup="dialog" aria-controls="companion-panel" aria-expanded="false" aria-label="Start live AI voice conversation" title="Start a realtime two-way voice conversation"><span className="live-voice-bars" aria-hidden="true"><i></i><i></i><i></i></span><span>Live voice</span></button><button className="ghost-btn" id="approvals-top">Approvals</button><button className="profile-btn" id="profile-button" aria-label="Account menu"><span id="profile-initial">D</span></button></div>
      </header>
      <main className="chat-main" id="chat-main">
        <section className="empty-state" id="empty-state">
          <img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" alt="" className="hero-logo"/>
          <div className="eyebrow">DragonZpyder / Personal</div>
          <h1>Make progress on what matters.</h1>
          <p>Think through an idea, work with connected information, or prepare your next step. DragonZpyder acts through permissions you control—not invisible authority.</p>
          <div className="prompt-grid">
            <button className="prompt-chip">Find a good time next week for a meeting.</button>
            <button className="prompt-chip">Help me draft an email I can review.</button>
            <button className="prompt-chip">Show me which connected tools I can use.</button>
            <button className="prompt-chip">Help me make a clear plan for this week.</button>
          </div>
        </section>
        <section className="messages" id="messages" aria-live="polite"></section>
      </main>
      <footer className="composer-wrap">
      <div className="mesh-tools">
        <button type="button" id="mesh-switch" className="mesh-switch" aria-pressed="false" title="Switch between tool-using Agent and OpenRouter AI Mesh"><span>✦</span> Agent</button>
        <div id="mesh-controls" className="mesh-controls" hidden>
          <select id="mesh-task" className="mesh-select" aria-label="AI Mesh task">
            <option value="chat">Text & vision</option><option value="image">Create image</option>
            <option value="transcribe">Transcribe audio</option><option value="speech">Create speech</option><option value="video">Create video</option>
          </select>
          <select id="mesh-model" className="mesh-select" aria-label="OpenRouter model"><option value="">Loading models…</option></select>
          <label id="mesh-file-label" className="mesh-input-label" title="Attach an image or audio file">＋ Attach<input id="mesh-upload" type="file" accept="image/png,image/jpeg,image/webp,audio/*"/></label>
        </div>
      </div>
      <div id="mesh-attachments" className="mesh-attachments" hidden></div>
      <div id="mesh-status" className="mesh-status" role="status" aria-live="polite" hidden></div>
      <span id="dictation-feedback" className="dictation-feedback" role="status" aria-live="polite" hidden></span><form className="composer" id="composer"><textarea id="message-input" rows="1" maxLength="12000" placeholder="Message DragonZpyder…" aria-label="Message DragonZpyder"></textarea><button className="dictation-button" id="dictation-toggle" type="button" title="Dictate into message" aria-label="Start dictation" aria-pressed="false"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"></rect><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"></path></svg></button><button className="send-button" id="send-button" type="submit" aria-label="Send message">↑</button></form><div className="composer-note">Personal scope · Connected capabilities are permissioned · Review significant actions before approving.</div></footer>
    </section>
  </div>
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
