import React from "react";
import { RuntimeDot, RuntimeText, RuntimeYear } from "./runtime.jsx";

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function HomeTemplate() {
  return (
    <>

  <header className="topbar" id="topbar"><div className="wrap nav">
  <a className="brand" href="#top" aria-label="DragonZpyder home"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" alt="" width="32" height="32"/><span>DragonZpyder</span></a>
  <nav className="navlinks" aria-label="Main navigation"><a href="#thesis">The thesis</a><a href="#mesh">AI Mesh</a><a href="#credits">Project IC</a><a href="#ecosystem">Ecosystem</a><a className="nav-cta" href="/app.html">Personal AI <span aria-hidden="true">↗</span></a></nav>
</div></header>
  <main id="top">
  <section className="hero" aria-labelledby="hero-title"><div className="wrap hero-grid">
    <div>
      <div className="eyebrow hero-eyebrow"><span className="ember" aria-hidden="true"></span> DragonZpyder / The connected AI ecosystem</div>
      <h1 id="hero-title">The best of AI.<br/><em>Connected.</em></h1>
      <p className="lead">Exceptional intelligence is everywhere—in reasoning models, coding tools, image and video engines, and specialist apps. It's scattered across different platforms and paywalls. <strong>DragonZpyder is building the connection layer</strong>: one place to bring compatible AI capabilities together and make them work for you.</p>
      <div className="actions"><a className="button primary" href="#mesh">Explore the AI Mesh <span aria-hidden="true">↘</span></a><a className="button" href="#credits">Discover Project IC <span aria-hidden="true">↓</span></a></div>
      <p className="scope-note">Vision and product development. The multi-model Mesh and shared AI Credits wallet are not yet released. <a href="#personal" style={{ textDecoration: "underline", textUnderlineOffset: "3px", color: "var(--soft)" }}>Our Personal AI is in early access.</a></p>
    </div>
    <aside className="network" aria-label="Illustration of proposed DragonZpyder architecture">
      <div className="network-header"><strong>One connected experience</strong><span>Architecture / planned</span></div>
      <div className="network-inner">
        <div className="network-label">Independent sources of intelligence</div>
        <div className="source-rows">
          <div className="source"><i aria-hidden="true"></i> Reasoning &amp; research</div>
          <div className="source"><i aria-hidden="true"></i> Coding &amp; agents</div>
          <div className="source"><i aria-hidden="true"></i> Image &amp; video</div>
          <div className="source"><i aria-hidden="true"></i> Voice &amp; sound</div>
          <div className="source"><i aria-hidden="true"></i> Third-party AI applications</div>
        </div>
        <div className="network-wire" aria-hidden="true">↓</div>
        <div className="network-hub"><span className="micro">Connection / choice / orchestration</span><b>DragonZpyder</b><p>Different strengths. One coherent place to use them.</p></div>
        <div className="network-wire" aria-hidden="true">↓</div>
        <div className="network-label">The intended experience</div>
      </div>
      <div className="network-footer"><div><b>AI Mesh</b><span>Connect the capabilities</span></div><div><b>Project IC / AIC</b><span>One proposed spending layer</span></div></div>
      <div className="network-caption">Conceptual system map · No provider integration or partner is implied.</div>
    </aside>
  </div></section>
  <div className="proof-strip"><div className="wrap proof-grid">
    <div className="proof"><b>Many exceptional AI services</b><span>Different creators, strengths and interfaces.</span></div>
    <div className="proof"><b>One coherent experience</b><span>Choose, coordinate and compose permitted tools.</span></div>
    <div className="proof"><b>One flexible AI budget</b><span>AIC aims to replace unnecessary payment fragmentation.</span></div>
  </div></div>
  <section className="section" id="thesis"><div className="wrap">
    <div className="section-head"><div className="section-id">01 / Why DragonZpyder</div><div><h2>We don't need to rebuild every breakthrough.<br/>We need to <span className="serif-em">connect them.</span></h2><p className="section-summary">No company can—or needs to—make every exceptional model, creative engine and specialised application. The industry is generating remarkable individual capabilities. But people still move manually between accounts, interfaces, files and separate bills. DragonZpyder's thesis is that connecting those capabilities can unlock more agency than leaving each one isolated.</p></div></div>
    <div className="thesis-points">
      <article className="thesis-point"><span className="micro">01 / Choice</span><h3>Use the right intelligence.</h3><p>A reasoning system for analysis, a coding model for implementation, a creative model for video. The task should determine the tool, not the brand you happened to subscribe to.</p></article>
      <article className="thesis-point"><span className="micro">02 / Connection</span><h3>Turn isolated results into work.</h3><p>A useful outcome may span research, writing, design, media and specialised apps. Coordinate permitted systems instead of copy-pasting between disconnected products.</p></article>
      <article className="thesis-point"><span className="micro">03 / Access</span><h3>Pay for what you use.</h3><p>Under the planned AIC model, one account would meter usage across participating services. Low-volume experimentation should not require separate subscriptions everywhere.</p></article>
    </div>
  </div></section>
  <section className="section mesh-section" id="mesh"><div className="wrap">
    <div className="section-head"><div className="section-id">02 / AI Mesh · Planned</div><div><h2>The dots are there.<br/>We build the <span className="serif-em">connections.</span></h2><p className="section-summary">AI Mesh is the proposed independent coordination layer. It's not a claim that every AI provider has agreed to join: each connection requires a permitted API or partner arrangement, and every capability retains its own constraints.</p></div></div>
    <div className="mesh-table">
      <div className="mesh-row"><span className="count">01</span><h3>Find and select</h3><p>Understand which supported models and applications can handle a task, what they cost and what permissions they require.</p></div>
      <div className="mesh-row"><span className="count">02</span><h3>Delegate and combine</h3><p>With explicit bounds, one service can produce inputs for another: research into scripts, scripts into scenes, scenes into video, and audio into a finished experience.</p></div>
      <div className="mesh-row"><span className="count">03</span><h3>Keep control</h3><p>Maintain context, view activity and estimated usage, impose spending ceilings, and approve meaningful external actions before execution.</p></div>
    </div>
    <div className="mesh-example"><div className="micro">Illustrative creative chain</div><p>Research → story concept → screenplay → visual generation → voice → edit. Different specialist services could contribute to one creative outcome wherever the integrations and rights allow.</p></div>
  </div></section>
  <section className="section credits-section" id="credits"><div className="wrap credits-grid">
    <div><div className="section-id">03 / Project IC · AIC · Research</div><h2>One budget.<br/><span className="serif-em">More possibilities.</span></h2><p className="section-summary">Imagine adding $20 to DragonZpyder, then using small portions for a coding task, a video generation, a voice clip or a story experience—without first committing to a separate monthly subscription for every supported service. That's the idea behind <strong style={{ color: "var(--text)" }}>Project IC, or AIC (AI Credits).</strong></p><p className="section-summary" style={{ marginTop: "17px" }}>Participating applications would price their own usage; DragonZpyder would show the amount before charging a common balance. You control where the budget goes.</p><p className="credit-note">Research concept only. No universal wallet, issued AIC currency or partner settlement network is live. Existing third-party subscriptions and credits cannot be transferred automatically. Future use requires legitimate API access, commercial agreements and suitable payment compliance.</p></div>
    <div className="wallet" aria-label="Illustrative allocation of twenty dollars in proposed AI Credits">
      <div className="wallet-header"><div><span className="micro">Example AIC balance</span><strong>$20.00</strong></div><span className="status">Concept only</span></div>
      <div className="wallet-lines">
        <div className="wallet-line"><span>Reasoning &amp; research</span><strong>$3.00</strong></div>
        <div className="wallet-line"><span>Coding assistance</span><strong>$4.00</strong></div>
        <div className="wallet-line"><span>Video generation</span><strong>$8.00</strong></div>
        <div className="wallet-line"><span>Storytelling experience</span><strong>$5.00</strong></div>
      </div>
      <div className="wallet-meter" aria-hidden="true"><i style={{ width: "15%" }}></i><i style={{ width: "20%" }}></i><i style={{ width: "40%" }}></i><i style={{ width: "25%" }}></i></div>
      <p className="wallet-foot">Illustrative spending allocation, not actual vendor rates, service availability or a functioning payment wallet.</p>
    </div>
  </div></section>
  <section className="section" id="ecosystem"><div className="wrap">
    <div className="section-head"><div className="section-id">04 / The platform</div><div><h2>An ecosystem, not another isolated AI island.</h2><p className="section-summary">The longer-term ambition includes independent third-party applications—storytelling, animation, education, engineering and more—not merely a grid of chat models. The current products below are the foundation, not the completed marketplace.</p></div></div>
    <div className="product-grid">
      <article className="product-card planned"><span className="status-key">Planned / Ecosystem layer</span><h3>AI Mesh + AIC</h3><p>One experience for compatible intelligence services and participating apps, joined by transparent orchestration and a future unified spending system.</p><div style={{ marginTop: "auto" }}><span className="model-pill">Models</span><span className="model-pill">Creative engines</span><span className="model-pill">Third-party apps</span><span className="model-pill">Usage credits</span></div></article>
      <a className="product-card" href="https://operly.dragonzpyder.xyz/" rel="noopener noreferrer"><span className="status-key">Separate product / Execution backbone</span><h3>Operly</h3><p>Governed access to tools and workflows: permissions, approvals, integrations, durable tasks, and agent execution where authority has been granted.</p><div className="card-bottom"><span>Explore Operly</span><span aria-hidden="true">↗</span></div></a>
    </div>
  </div></section>
  <section className="section mesh-section" id="personal"><div className="wrap">
    <div className="section-head"><div className="section-id">05 / Available now · Early access</div><div><h2>Start with DragonZpyder Personal.</h2><p className="section-summary">Today's product is deliberately narrower than the vision: a personal interface with conversations, permitted connected tools and reviewed actions, powered by Operly. It's a starting point for continuity and agency—not yet the multi-provider model marketplace or AIC wallet.</p><div className="actions" style={{ marginTop: "26px" }}><a className="button primary" href="/app.html">Try the current Personal AI <span aria-hidden="true">↗</span></a><a className="button" href="https://github.com/AaryanK/DragonZpyder">Explore the repository <span aria-hidden="true">↗</span></a></div><div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "22px", color: "var(--dim)", fontSize: "11px" }}><RuntimeDot /><RuntimeText /></div></div></div>
  </div></section>
  <section className="principle"><div className="wrap principle-grid"><div className="section-id">The name / Our philosophy</div><div><blockquote>Fire creates possibility.<br/>The spider weaves connection.<br/><em>Neither should be trapped.</em></blockquote><p>The dragon represents creative energy; the spider represents weaving independently existing things into a connected whole. DragonZpyder isn't trying to own every intelligence. It seeks to let people harness them together without becoming captive to any one system.</p></div></div></section>
  <section className="closing"><div className="wrap closing-inner"><div><div className="section-id">The direction is clear</div><h2>All that intelligence.<br/><span className="serif-em">One place to put it to work.</span></h2><p className="disclaimer">AI Mesh and AIC remain planned/research initiatives. Try the existing Personal experience or follow the development of the broader platform.</p></div><a className="button primary" href="/app.html">Open Personal AI <span aria-hidden="true">↗</span></a></div></section>
</main>
  <footer><div className="wrap footer-row"><a className="brand" href="#top"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" width="27" height="27" alt=""/><span>DragonZpyder</span></a><div className="footer-links"><a href="#thesis">Why DragonZpyder</a><a href="#mesh">AI Mesh</a><a href="#credits">Project IC</a><a href="/app.html">Personal AI</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="https://github.com/AaryanK/DragonZpyder">GitHub</a></div><span>© <RuntimeYear /> DragonZpyder</span></div></footer>
  
    </>
  );
}
