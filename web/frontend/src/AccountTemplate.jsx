import React from "react";

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function AccountTemplate() {
  return (
    <>

<header className="top"><a href="/" className="brand"><img alt="" src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png"/>DragonZpyder</a><a href="/app.html">Personal AI <span aria-hidden="true">↗</span></a></header>
<main>
<section className="intro"><span className="eyebrow">ONE IDENTITY · YOUR INTELLIGENCE</span><h1>Always <em>yours.</em></h1><p>Your conversations, personal AI, and authorised connections—all in one account, without making you use a business workspace.</p></section>
<section className="account-card" aria-label="DragonZpyder account">
<div className="tabs" id="mode-tabs" role="group" aria-label="Account access"><button type="button" data-mode="login" className="selected">Sign in</button><button type="button" data-mode="signup">Create account</button></div>
<div className="message" id="account-message" role="status" aria-live="polite" hidden></div>
<section id="login-panel" className="account-panel"><h2>Welcome back.</h2><p className="muted">Continue to your personal DragonZpyder.</p><div id="google-provider" className="google-provider" aria-label="Google sign-in" hidden></div><div className="divider">or use your email</div><form id="login-form">
<label htmlFor="login-email">Email address</label><input id="login-email" type="email" required autoComplete="username"/>
<label htmlFor="login-password">Password</label><input id="login-password" type="password" required autoComplete="current-password"/>
<button className="submit" type="submit">Sign in</button></form><p className="links"><button type="button" data-mode="forgot">Forgot password?</button></p></section>
<section id="signup-panel" className="account-panel" hidden><h2>Create your account.</h2><p className="muted">Start personal. Connect workspaces when you choose.</p><form id="signup-form">
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
<section id="profile-panel" className="account-panel" hidden><span className="eyebrow">PERSONAL IDENTITY</span><h2>Your account.</h2><p className="muted" id="profile-email"></p><form id="profile-form"><label htmlFor="profile-name">Display name</label><input id="profile-name" required maxLength="200"/><button className="submit" type="submit">Save account details</button></form>
<div className="account-section"><h3>Sign-in methods</h3><div id="linked-identities" className="identity-list"></div><p className="footnote">Signing in with Google or Discord is different from connecting Gmail, Calendar or Discord tools.</p></div>
<div className="account-section"><h3>Workspaces</h3><p className="muted small">Your personal identity stays separate from business workspace permissions.</p><div id="workspace-list"></div><a className="business-link" href="https://operly.dragonzpyder.xyz/" target="_blank" rel="noopener noreferrer">Manage business workspaces in Operly ↗</a></div>
<p className="links"><a href="/app.html">Return to Personal AI</a> <button id="account-logout" type="button">Sign out</button></p></section>
</section>
<aside className="account-note"><strong>One account, clear boundaries.</strong><p>DragonZpyder is your personal AI environment. Operly powers authorised tasks, connectors, and business operations. Personal access does not grant business permissions.</p><p>Discord sign-in will appear here after its secure DragonZpyder callback is configured.</p></aside>
</main>
<footer>© DragonZpyder · <a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a></footer>

    </>
  );
}
