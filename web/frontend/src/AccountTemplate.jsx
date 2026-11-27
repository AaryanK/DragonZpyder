import React from "react";
import { WorkspaceCenter } from "./WorkspaceCenter.jsx";
import { AppearanceSettings } from "./AppearanceSettings.jsx";
import { UiIcon } from "./UiIcon.jsx";
import "./workspace-center.css";

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function AccountTemplate() {
  return (
    <>
      <WorkspaceCenter />

<header className="top"><a href="/" className="brand"><img alt="" src="/brand-icon.png"/>DragonZpyder</a><a className="account-back" href="/app"><UiIcon name="chat" size={18}/> Back to chat</a></header>
<main>
<section className="account-card" aria-label="DragonZpyder account">
<div className="message" id="account-message" role="status" aria-live="polite" hidden></div>
<section id="login-panel" className="account-panel"><h2>Sign in</h2><p className="dz-auth-hint">Continue to DragonZpyder.</p><div id="google-provider" className="google-provider" aria-label="Google sign-in" hidden></div><div className="divider">or use your email</div><form id="login-form">
<label htmlFor="login-email">Email address</label><input id="login-email" type="email" required autoComplete="username"/>
<label htmlFor="login-password">Password</label><input id="login-password" type="password" required autoComplete="current-password"/>
<button className="submit" type="submit">Sign in</button></form><p className="links"><button type="button" data-mode="forgot" hidden>Forgot password?</button></p></section>
<section id="migration-panel" className="account-panel" hidden>
<h2>Verify your existing account.</h2><p className="muted">Confirm the sign-in method already attached to your account. This does not sign you in or change your account; activation requires a separate review.</p>
<div id="google-provider-migration" className="google-provider" aria-label="Google account migration verification" hidden></div>
<form id="migration-form">
<label htmlFor="migration-email">Email address</label><input id="migration-email" type="email" required maxLength="320" autoComplete="username"/>
<label htmlFor="migration-password">Existing password</label><input id="migration-password" type="password" required maxLength="1024" autoComplete="current-password"/>
<button className="submit" type="submit">Verify existing account</button>
</form><p className="links"><a id="migration-recovery-link" href="/account?mode=migration-recovery" hidden>Recover access using verified email</a><a href="/account">Return to regular account access</a></p>
</section>
<section id="migration-recovery-panel" className="account-panel" hidden>
<h2>Recover your existing account.</h2>
<p className="muted">For eligible existing accounts that do not have a password. We send a one-time code to the verified email already on file. Completing recovery does not activate your account.</p>
<form id="migration-recovery-start">
<label htmlFor="migration-recovery-email">Email address</label><input id="migration-recovery-email" type="email" required maxLength="320" autoComplete="username"/>
<button className="submit" type="submit">Request recovery code</button>
</form>
<form id="migration-recovery-complete" hidden>
<label htmlFor="migration-recovery-code">Recovery code</label><input id="migration-recovery-code" required minLength="43" maxLength="43" autoComplete="one-time-code"/>
<label htmlFor="migration-recovery-password">New password (at least 12 characters)</label><input id="migration-recovery-password" type="password" required minLength="12" maxLength="1024" autoComplete="new-password"/>
<label htmlFor="migration-recovery-confirm">Confirm new password</label><input id="migration-recovery-confirm" type="password" required minLength="12" maxLength="1024" autoComplete="new-password"/>
<button className="submit" type="submit">Establish password</button>
</form>
<p className="links"><a href="/account?mode=migration">Return to account verification</a></p>
</section>
<section id="signup-panel" className="account-panel" hidden><h2>Create account</h2><p className="dz-auth-hint">Use your Google account to get started.</p><div id="google-provider-signup" className="google-provider" aria-label="Google signup" hidden></div></section>
<section id="forgot-panel" className="account-panel" hidden><h2>Reset password</h2><p className="muted">We'll email reset instructions if there's an account using that address.</p><form id="forgot-form">
<label htmlFor="forgot-email">Email address</label><input id="forgot-email" type="email" required autoComplete="email"/>
<button className="submit" type="submit">Send reset instructions</button></form><p className="links"><button type="button" data-mode="reset">I have a reset code</button><button type="button" data-mode="login">Back to sign in</button></p></section>
<section id="reset-panel" className="account-panel" hidden><h2>Set a new password</h2><p className="muted">Use the six-digit code from your password-reset email.</p><form id="reset-form">
<label htmlFor="reset-email">Email address</label><input id="reset-email" type="email" required autoComplete="email"/>
<label htmlFor="reset-code">Reset code</label><input id="reset-code" inputMode="numeric" maxLength="6" pattern="[0-9]{6}" required/>
<label htmlFor="reset-password">New password</label><input id="reset-password" type="password" minLength="12" required autoComplete="new-password"/>
<button className="submit" type="submit">Update password</button></form><p className="links"><button type="button" data-mode="login">Back to sign in</button></p></section>
<section id="profile-panel" className="account-panel dz-account-dashboard" hidden>
<div className="dz-account-heading"><h2>Settings</h2></div>
<nav className="dz-account-shortcuts" aria-label="Account sections">
<a href="#dz-profile">Profile</a><a href="#dz-appearance">Appearance</a><a href="#dz-identities">Sign-in methods</a><a href="#dz-connections">Connections</a><a href="#dz-workspaces">Workspaces</a>
</nav>
<section className="dz-account-group" id="dz-profile"><div className="dz-account-group-heading"><div><h3>Profile</h3><p id="profile-email" className="muted small"></p></div><span className="dz-account-symbol dz-account-avatar"><span id="account-profile-fallback">?</span><img id="account-profile-avatar" alt="" hidden referrerPolicy="no-referrer"/></span></div>
<form id="profile-form" className="dz-account-form"><label htmlFor="profile-name">Display name</label><input id="profile-name" required maxLength="200" autoComplete="name"/><button className="submit" type="submit">Save changes</button></form></section>
<AppearanceSettings/>
<section className="dz-account-group" id="dz-identities"><div className="dz-account-group-heading"><div><h3>Sign-in methods</h3></div><span className="dz-account-symbol"><UiIcon name="shield"/></span></div>
<div id="linked-identities" className="identity-list"></div><p className="footnote">Google sign-in does not automatically grant Gmail or Calendar access. Connected services require separate authorization.</p></section>
<section className="dz-account-group" id="dz-connections"><div className="dz-account-group-heading"><div><h3>Connections &amp; tools</h3></div><span className="dz-account-symbol"><UiIcon name="plug"/></span></div>
<div className="dz-account-resource-list">
<div className="dz-account-resource"><span className="dz-account-resource-mark"><UiIcon name="plug"/></span><div><strong>Connected services</strong><small>Manage authorized apps and tools.</small></div><button className="dz-account-resource-action" type="button" onClick={() => window.dispatchEvent(new CustomEvent("dragonzpyder:center-open", { detail: { page: "connections" } }))}>Manage connections ↗</button></div>
<div className="dz-account-resource"><span className="dz-account-resource-mark"><UiIcon name="tasks"/></span><div><strong>Agent capabilities</strong><small>View supported actions and approvals from the workspace.</small></div><a href="/app">Open workspace ↗</a></div>
</div><p className="footnote">Connections are separate from sign-in.</p></section>
<section className="dz-account-group" id="dz-workspaces"><div className="dz-account-group-heading"><div><h3>Your workspaces</h3></div><span className="dz-account-symbol"><UiIcon name="panel"/></span></div>
<div id="workspace-list" className="dz-account-workspaces"></div><a className="business-link" href="https://operly.dragonzpyder.xyz/" target="_blank" rel="noopener noreferrer">Open business workspaces ↗</a></section>
<div className="dz-account-footer"><a href="/app">Back to chat</a><button id="account-logout" type="button">Sign out</button></div>
</section>
<div className="tabs" id="mode-tabs" role="group" aria-label="Account access"><button type="button" data-mode="login" className="selected">Sign in</button><button type="button" data-mode="signup">Create account</button></div>
</section>
</main>
<footer>© DragonZpyder · <a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a></footer>

    </>
  );
}
