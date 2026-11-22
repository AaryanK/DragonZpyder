import React from "react";
import { WorkspaceCenter } from "./WorkspaceCenter.jsx";
import "./workspace-center.css";

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function AccountTemplate() {
  return (
    <>
      <WorkspaceCenter />

<header className="top"><a href="/" className="brand"><img alt="" src="/brand-icon.png"/>DragonZpyder</a><a href="/app">Personal AI <span aria-hidden="true">↗</span></a></header>
<main>
<section className="intro"><span className="eyebrow">ONE IDENTITY · YOUR INTELLIGENCE</span><h1>Always <em>yours.</em></h1><p>Your conversations, personal AI, and authorised connections—all in one account, without making you use a business workspace.</p></section>
<section className="account-card" aria-label="DragonZpyder account">
<div className="tabs" id="mode-tabs" role="group" aria-label="Account access"><button type="button" data-mode="login" className="selected">Sign in</button><button type="button" data-mode="signup">Create account</button></div>
<div className="message" id="account-message" role="status" aria-live="polite" hidden></div>
<section id="login-panel" className="account-panel"><h2>Welcome back.</h2><p className="muted">Continue to your personal DragonZpyder.</p><a id="dragonzpyder-central-signin" className="submit" href="/api/auth/dragonzpyder/web/start" hidden>Continue with DragonZpyder</a><div id="google-provider" className="google-provider" aria-label="Google sign-in" hidden></div><div className="divider">or use your email</div><form id="login-form">
<label htmlFor="login-email">Email address</label><input id="login-email" type="email" required autoComplete="username"/>
<label htmlFor="login-password">Password</label><input id="login-password" type="password" required autoComplete="current-password"/>
<button className="submit" type="submit">Sign in</button></form><p className="links"><button type="button" data-mode="forgot">Forgot password?</button></p></section>
<section id="signup-panel" className="account-panel" hidden><h2>Create your account.</h2><p className="muted">Start personal. Connect workspaces when you choose.</p><div id="google-provider-signup" className="google-provider" aria-label="Google signup" hidden></div><form id="signup-form">
<label htmlFor="signup-name">Your name</label><input id="signup-name" required maxLength="200" autoComplete="name"/>
<label htmlFor="signup-email">Email address</label><input id="signup-email" type="email" required autoComplete="email"/>
<label htmlFor="signup-password">Password (at least 12 characters)</label><input id="signup-password" type="password" minLength="12" required autoComplete="new-password"/>
<label htmlFor="signup-confirm">Confirm password</label><input id="signup-confirm" type="password" minLength="12" required autoComplete="new-password"/>
<button className="submit" type="submit">Create account</button></form></section>
<section id="verify-panel" className="account-panel" hidden><h2>Verify your email.</h2><p className="muted">Enter the six-digit code emailed to you. Your email must be verified before you can sign in.</p><form id="verify-form">
<label htmlFor="verify-email">Email address</label><input id="verify-email" type="email" required autoComplete="email"/>
<label htmlFor="verify-code">Verification code</label><input id="verify-code" inputMode="numeric" pattern="[0-9]{6}" maxLength="6" required autoComplete="one-time-code"/>
<button className="submit" type="submit">Verify and continue</button></form>
<p className="links"><button type="button" id="resend">Resend code</button><button type="button" data-mode="login">Back to sign in</button></p></section>
<section id="forgot-panel" className="account-panel" hidden><h2>Reset your password.</h2><p className="muted">We'll email reset instructions if there's an account using that address.</p><form id="forgot-form">
<label htmlFor="forgot-email">Email address</label><input id="forgot-email" type="email" required autoComplete="email"/>
<button className="submit" type="submit">Send reset instructions</button></form><p className="links"><button type="button" data-mode="reset">I have a reset code</button><button type="button" data-mode="login">Back to sign in</button></p></section>
<section id="reset-panel" className="account-panel" hidden><h2>Set a new password.</h2><p className="muted">Use the six-digit code from your password-reset email.</p><form id="reset-form">
<label htmlFor="reset-email">Email address</label><input id="reset-email" type="email" required autoComplete="email"/>
<label htmlFor="reset-code">Reset code</label><input id="reset-code" inputMode="numeric" maxLength="6" pattern="[0-9]{6}" required/>
<label htmlFor="reset-password">New password</label><input id="reset-password" type="password" minLength="12" required autoComplete="new-password"/>
<button className="submit" type="submit">Update password</button></form><p className="links"><button type="button" data-mode="login">Back to sign in</button></p></section>
<section id="profile-panel" className="account-panel dz-account-dashboard" hidden>
<div className="dz-account-heading"><div><span className="eyebrow">YOUR DRAGONZPYDER</span><h2>Account &amp; connections.</h2><p className="muted">One identity, with clear boundaries around every connected service and workspace.</p></div><a className="dz-account-return" href="/app">Back to Personal AI <span aria-hidden="true">↗</span></a></div>
<nav className="dz-account-shortcuts" aria-label="Account sections">
<a href="#dz-profile">Profile</a><a href="#dz-identities">Sign-in methods</a><a href="#dz-connections">Connections</a><a href="#dz-workspaces">Workspaces</a>
</nav>
<section className="dz-account-group" id="dz-profile"><div className="dz-account-group-heading"><div><span className="eyebrow">01 / IDENTITY</span><h3>Your profile</h3><p id="profile-email" className="muted small"></p></div><span className="dz-account-symbol" aria-hidden="true">◎</span></div>
<form id="profile-form" className="dz-account-form"><label htmlFor="profile-name">Display name</label><input id="profile-name" required maxLength="200" autoComplete="name"/><button className="submit" type="submit">Save changes</button></form></section>
<section className="dz-account-group" id="dz-identities"><div className="dz-account-group-heading"><div><span className="eyebrow">02 / ACCESS</span><h3>Sign-in methods</h3><p className="muted small">How you prove your identity when signing in.</p></div><span className="dz-account-symbol" aria-hidden="true">◇</span></div>
<div id="linked-identities" className="identity-list"></div><p className="footnote">Google sign-in does not automatically grant Gmail or Calendar access. Connected services require separate authorization.</p></section>
<section className="dz-account-group" id="dz-connections"><div className="dz-account-group-heading"><div><span className="eyebrow">03 / CAPABILITIES</span><h3>Connections &amp; tools</h3><p className="muted small">Personal integrations and agent capabilities are permissioned independently of your login.</p></div><span className="dz-account-symbol" aria-hidden="true">⌘</span></div>
<div className="dz-account-resource-list">
<div className="dz-account-resource"><span className="dz-account-resource-mark" aria-hidden="true">G</span><div><strong>Connected services</strong><small>Authorize, test and revoke Google, Canva and other supported tools independently of sign-in.</small></div><button className="dz-account-resource-action" type="button" onClick={() => window.dispatchEvent(new CustomEvent("dragonzpyder:center-open", { detail: { page: "connections" } }))}>Manage connections ↗</button></div>
<div className="dz-account-resource"><span className="dz-account-resource-mark" aria-hidden="true">◈</span><div><strong>Agent capabilities</strong><small>View supported actions and approvals from the workspace.</small></div><a href="/app">Open workspace ↗</a></div>
</div><p className="footnote">Connection status and revocation controls will appear here only after DragonZpyder's dedicated connector API is available. No provider is shown as connected without verification.</p></section>
<section className="dz-account-group" id="dz-workspaces"><div className="dz-account-group-heading"><div><span className="eyebrow">04 / SCOPE</span><h3>Your workspaces</h3><p className="muted small">Business membership never follows automatically from your personal login.</p></div><span className="dz-account-symbol" aria-hidden="true">▦</span></div>
<div id="workspace-list" className="dz-account-workspaces"></div><a className="business-link" href="https://operly.dragonzpyder.xyz/" target="_blank" rel="noopener noreferrer">Manage existing business workspaces ↗</a></section>
<div className="dz-account-footer"><a href="/app">Return to Personal AI</a><button id="account-logout" type="button">Sign out</button></div>
</section>
</section>
<aside className="account-note"><strong>One account, clear boundaries.</strong><p>DragonZpyder is your personal AI environment. Operly powers authorised tasks, connectors, and business operations. Personal access does not grant business permissions.</p><p>Discord sign-in will appear here after its secure DragonZpyder callback is configured.</p></aside>
</main>
<footer>© DragonZpyder · <a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a></footer>

    </>
  );
}
