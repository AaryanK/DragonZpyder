import React from "react";
import { RuntimeDot, RuntimeText, RuntimeYear } from "./runtime.jsx";



const edCSS = "\n:root{color-scheme:light;--bg:#fbfaf8;--surface:#f6f4f0;--surface2:#ece8e2;--text:#151515;--soft:#484643;--muted:#68635e;--dim:#79736b;--line:#e2ded8;--accent:#f45612;--accent-light:#fb7b3b}\nbody{background:#fbfaf8;color:#151515}\n.dz-topbar{position:sticky;top:0;z-index:25;background:rgba(251,250,248,.96);backdrop-filter:blur(16px);border-bottom:1px solid #ece8e1}\n.dz-nav{max-width:1500px;width:calc(100% - 88px);margin:auto;display:flex;align-items:center;justify-content:space-between;gap:24px;height:75px}\n.dz-brand{display:inline-flex;align-items:center;gap:8px;font-size:22px;line-height:1;font-weight:850;letter-spacing:-.06em;white-space:nowrap}\n.dz-brand span:first-child{font-size:29px;color:#f45612}\n.dz-navlinks{display:flex;align-items:center;gap:28px;font-size:13px;font-weight:740}\n.dz-navlinks a:hover,.dz-header-link:hover{color:#f45612}\n.dz-nav-cta{display:flex;gap:10px;align-items:center;white-space:nowrap}\n.dz-header-link{padding:11px 14px;font-size:13px;font-weight:700}\n.dz-btn{background:#f45612;color:white;display:inline-flex;align-items:center;justify-content:center;gap:13px;border:1px solid #f45612;border-radius:10px;padding:15px 20px;font-size:13px;font-weight:790;min-height:48px;transition:background .2s,transform .2s}\n.dz-btn:hover{transform:translateY(-1px);background:#dc3f0a}\n.dz-btn.outline{background:#fff;color:#191919;border-color:#d6d1ca}\n.dz-btn.outline:hover{background:#fff2ec}\n.dz-hero{max-width:1500px;width:calc(100% - 88px);margin:0 auto;padding:58px 0 46px;display:grid;grid-template-columns:minmax(0, .95fr) minmax(0,1.05fr);gap:clamp(28px,4vw,64px);align-items:center}\n.dz-copy{min-width:0}\n.dz-eyebrow{font-size:11px;letter-spacing:.31em;font-weight:790}\n.dz-rule{width:62px;height:4px;background:#f45612;margin:17px 0 25px}\n.dz-copy h1{font-family:Inter,Arial,Helvetica,sans-serif;font-size:clamp(66px,8.35vw,130px);font-weight:900;line-height:.85;letter-spacing:-.095em;margin:0 0 30px;max-width:700px}\n.dz-copy h1 span{display:block}\n.dz-copy h2{font-family:Inter,Arial,sans-serif;font-size:clamp(24px,2.4vw,35px);font-weight:850;letter-spacing:-.06em;line-height:1.08;margin:0 0 8px}\n.dz-tag{font-size:clamp(18px,2vw,25px);letter-spacing:-.04em;line-height:1.2}\n.dz-desc{max-width:495px;color:#59534e;font-size:15px;line-height:1.75;margin:23px 0 26px}\n.dz-actions{display:flex;align-items:center;flex-wrap:wrap;gap:12px}\n.dz-checks{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin-top:27px;font-size:11px;font-weight:700;color:#514c47}\n.dz-checks span::before{content:\"✓\";color:#f45612;font-size:16px;margin-right:8px}\n.dz-stage{position:relative;min-height:580px;isolation:isolate}\n.dz-sweep{position:absolute;top:-48px;bottom:-25px;left:46%;width:150px;transform:skew(-32deg);background:linear-gradient(165deg,#ff9c11,#ff4b09 70%);z-index:-2}\n.dz-sigil{position:absolute;left:-67px;top:0;width:220px;height:400px;z-index:-1;opacity:.5;pointer-events:none}\n.dz-sigil svg{width:100%;height:100%;filter:drop-shadow(3px 10px 10px #c4541933)}\n.dz-card{color:#f6f3ee;background:#171718;border:1px solid #323135;border-radius:20px;box-shadow:0 25px 60px #1615152b;min-height:545px;overflow:hidden;display:flex;flex-direction:column;margin-top:18px}\n.dz-card-top{padding:19px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #3c3938;gap:16px}\n.dz-card-top strong{display:flex;gap:8px;align-items:center;font-size:15px;font-weight:800;letter-spacing:-.025em}\n.dz-symbol{color:#ff6a28;font-size:24px}\n.dz-card-top small{color:#aaa39d;font-size:10px;letter-spacing:.11em;font-weight:750}\n.dz-card-body{padding:29px 30px 23px;flex:1}\n.dz-card-kicker{font-size:10px;letter-spacing:.22em;font-weight:820;color:#f58c57}\n.dz-card-title{font-size:clamp(30px,3.3vw,47px);font-weight:830;letter-spacing:-.06em;line-height:1.04;max-width:500px;margin:15px 0 18px}\n.dz-card-title em{font-style:normal;color:#ff6c2b}\n.dz-card-text{color:#a9a5a2;font-size:12px;line-height:1.6;max-width:470px;margin-bottom:25px}\n.dz-process{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}\n.dz-process div{min-height:127px;border:1px solid #454040;background:#232225;border-radius:12px;padding:16px 13px 13px;position:relative}\n.dz-process div:not(:last-child):after{content:\"➜\";position:absolute;right:-13px;top:45%;z-index:2;background:#f45612;color:white;border-radius:50%;width:22px;height:22px;display:grid;place-items:center;font-size:12px}\n.dz-process b{display:block;color:#fb7132;font-size:17px;margin-bottom:13px}\n.dz-process h3{font-size:14px;font-family:Inter,Arial,sans-serif;color:white;letter-spacing:-.03em;font-weight:750;margin:0 0 8px}\n.dz-process p{color:#c2bdb9;font-size:11px;line-height:1.4;margin:0}\n.dz-capabilities{display:grid;grid-template-columns:1fr 1fr;gap:11px;padding-top:24px}\n.dz-cap{display:flex;align-items:flex-start;gap:10px;font-size:11px;color:#e7e4e0}\n.dz-cap-icon{font-size:15px;color:#ff7333}\n.dz-cap span:last-child{line-height:1.45}\n.dz-card-foot{display:flex;align-items:center;justify-content:space-between;gap:16px;border-top:1px solid #3e3938;padding:17px 24px;font-size:11px;color:#b2ada8}\n.dz-card-foot a{color:#ff8b55;font-weight:800}\n.dz-status-strip{max-width:1500px;width:calc(100% - 88px);margin:0 auto 64px;background:#f0ede8;border-radius:14px;padding:22px 27px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}\n.dz-status-strip>div{padding:0 25px;border-left:1px solid #d7d1ca}\n.dz-status-strip>div:first-child{padding-left:0;border-left:0}\n.dz-status-strip b{display:block;font-size:13px;margin-bottom:6px}\n.dz-status-strip p{font-size:11px;line-height:1.6;margin:0;color:#6b655f}\n.dz-status-strip small{color:#f45612;letter-spacing:.08em;font-size:10px;text-transform:uppercase}\n.proof-strip{background:#fff;border-color:#e5e2dc}.proof{border-color:#e5e2dc}.section{background:#fff}.mesh-section{background:#f4f2ee}\n.thesis-point+.thesis-point{border-color:#e3deda}.mesh-example,.wallet,.product-card{background:#fff!important;color:#191919!important;border-color:#dedad3!important}\n.wallet-line,.mesh-row{border-color:#dfdad3!important}\n.principle,.closing{background:#151515;color:white}.principle p,.closing .disclaimer{color:#c2bcb9}.footer-row{color:white}.footer-links a{color:#d4d1c8}\n@media(max-width:1150px){.dz-navlinks{gap:13px}.dz-hero{grid-template-columns:44% 56%;gap:24px}.dz-copy h1{font-size:clamp(62px,8.5vw,99px)}.dz-card-body{padding:22px}.dz-card-title{font-size:clamp(27px,3vw,40px)}.dz-process div{padding:13px 10px}}\n@media(max-width:900px){.dz-nav{width:calc(100% - 36px)}.dz-navlinks{display:none}.dz-hero{width:calc(100% - 36px);grid-template-columns:1fr;gap:12px;padding-top:44px}.dz-copy h1{font-size:clamp(71px,13vw,115px)}.dz-stage{min-height:0}.dz-card{margin:0}.dz-sweep{left:77%;opacity:.55}.dz-sigil{left:0;opacity:.35}.dz-status-strip{width:calc(100% - 36px);margin-bottom:37px}}\n@media(max-width:600px){.dz-nav{height:65px}.dz-brand{font-size:19px}.dz-brand span:first-child{font-size:25px}.dz-header-link{display:none}.dz-btn{font-size:11px;padding:11px 13px;min-height:41px}.dz-hero{padding-top:27px}.dz-copy h1{font-size:clamp(53px,13.5vw,81px)}.dz-copy h2{font-size:24px}.dz-tag{font-size:18px}.dz-desc{font-size:14px}.dz-checks{gap:11px}.dz-card{min-height:unset}.dz-card-body{padding:23px 15px}.dz-card-top{padding:15px}.dz-card-title{font-size:32px}.dz-process{gap:5px}.dz-process div{min-height:129px;padding:12px 7px}.dz-process h3{font-size:12px}.dz-process p{font-size:10px}.dz-process div:not(:last-child):after{right:-10px}.dz-card-foot{padding:14px 15px;flex-wrap:wrap}.dz-status-strip{grid-template-columns:1fr;gap:13px;padding:17px}.dz-status-strip>div{padding:13px 0 0;border-left:none;border-top:1px solid #d7d1ca}.dz-status-strip>div:first-child{padding-top:0;border-top:none}}\n@media(prefers-reduced-motion:reduce){.dz-btn{transition:none}}\n";
function EditorialDragonMark() {
  return <svg viewBox="0 0 240 380" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M206 11L143 91 82 49 105 130 30 160 85 181 12 247 87 230 27 294 66 323 47 367 122 304 180 367 183 280 237 213 184 191 236 122 189 128Z" fill="#121212" stroke="#ef5913" strokeWidth="9" strokeLinejoin="round" />
    <path d="M178 124 140 168 95 172 53 270 109 254 96 295 163 250 202 186Z" fill="#303034" />
    <path d="M82 206 136 199 120 220 82 206Z" fill="#ff840b" stroke="#ffb052" strokeWidth="7" />
    <path d="M166 119 214 59 174 152 213 142 169 192M115 275 152 315 130 355" fill="none" stroke="#ff5a12" strokeWidth="7" />
  </svg>;
}
function EditorialHeader(){
  return <header className="dz-topbar" id="topbar"><div className="dz-nav">
    <a className="dz-brand" href="#top" aria-label="DragonZpyder homepage"><span aria-hidden="true">✺</span>DragonZpyder™</a>
    <nav className="dz-navlinks" aria-label="Main navigation"><a href="#thesis">Product</a><a href="#mesh">AI Mesh</a><a href="#credits">Project IC</a><a href="#ecosystem">Ecosystem</a></nav>
    <div className="dz-nav-cta"><a className="dz-header-link" href="/app">Sign in</a><a className="dz-btn" href="/app">Open Chat <span aria-hidden="true">↗</span></a></div>
  </div></header>;
}
function EditorialHero(){
  return <>
  <section className="dz-hero" aria-labelledby="hero-title">
   <div className="dz-copy">
    <div className="dz-eyebrow">DRAGONZPYDER / CONNECTED INTELLIGENCE</div><div className="dz-rule"/>
    <h1 id="hero-title"><span>DRAGON</span><span>ZPYDER</span></h1>
    <h2>See. Hear. Speak. Create.</h2>
    <div className="dz-tag">A more capable AI, everywhere.</div>
    <p className="dz-desc">Your ideas deserve more than another isolated chatbot. DragonZpyder is bringing conversations, tools and governed AI actions into one experience, while building toward a connected ecosystem of specialist intelligence.</p>
    <div className="dz-actions"><a className="dz-btn" href="/app">Open the Personal AI workspace <span aria-hidden="true">↗</span></a><a className="dz-btn outline" href="#thesis">Discover the platform <span aria-hidden="true">↓</span></a></div>
    <div className="dz-checks"><span>Talk and create</span><span>Connect tools</span><span>Act with permission</span></div>
   </div>
   <div className="dz-stage">
    <div className="dz-sweep" aria-hidden="true"/><div className="dz-sigil"><EditorialDragonMark/></div>
    <div className="dz-card" aria-label="DragonZpyder platform overview">
      <div className="dz-card-top"><strong><span className="dz-symbol" aria-hidden="true">✺</span> DragonZpyder</strong><small>THE CONNECTED AI PLATFORM</small></div>
      <div className="dz-card-body">
       <div className="dz-card-kicker">THE IDEA / FROM INPUT TO OUTCOME</div>
       <div className="dz-card-title">Many kinds of intelligence.<br/><em>One coherent place.</em></div>
       <p className="dz-card-text">A different kind of AI platform: choose the right capabilities, coordinate what is permitted, and keep people in control of meaningful actions.</p>
       <div className="dz-process">
        <div><b>01</b><h3>Understand</h3><p>Conversations, context and inputs</p></div>
        <div><b>02</b><h3>Coordinate</h3><p>Models, tools and specialist agents</p></div>
        <div><b>03</b><h3>Act</h3><p>Reviewed steps and useful results</p></div>
       </div>
       <div className="dz-capabilities">
        <div className="dz-cap"><span className="dz-cap-icon">◈</span><span>Personal AI<br/><strong>Early access</strong></span></div>
        <div className="dz-cap"><span className="dz-cap-icon">⌘</span><span>Operly<br/><strong>Execution backbone</strong></span></div>
        <div className="dz-cap"><span className="dz-cap-icon">◎</span><span>AI Mesh<br/><strong>Planned</strong></span></div>
        <div className="dz-cap"><span className="dz-cap-icon">≋</span><span>Project IC / AIC<br/><strong>Research concept</strong></span></div>
       </div>
      </div>
      <div className="dz-card-foot"><span>Want to talk to DragonZpyder? The chat workspace lives separately.</span><a href="/app">Go to chat ↗</a></div>
    </div>
   </div>
  </section>
  <div className="dz-status-strip" aria-label="Platform offerings and status">
    <div><b>Personal AI <small>Early access</small></b><p>A separate workspace for conversation and permitted tools.</p></div>
    <div><b>AI Mesh <small>Planned</small></b><p>One coordination layer for compatible intelligence services.</p></div>
    <div><b>Project IC <small>Research</small></b><p>A proposed shared usage balance, not a live wallet.</p></div>
  </div>
  </>;
}

// Layout and copy are the existing DragonZpyder design, now authored as JSX.
// Do not reintroduce the former static HTML templates.
export function HomeTemplate() {
  return (
    <>

  <style>{edCSS}</style>
  <EditorialHeader />
  <main id="top">
  <EditorialHero />
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
    <div className="section-head"><div className="section-id">05 / Available now · Early access</div><div><h2>Start with DragonZpyder Personal.</h2><p className="section-summary">Today's product is deliberately narrower than the vision: a personal interface with conversations, permitted connected tools and reviewed actions, powered by Operly. It's a starting point for continuity and agency—not yet the multi-provider model marketplace or AIC wallet.</p><div className="actions" style={{ marginTop: "26px" }}><a className="button primary" href="/app">Try the current Personal AI <span aria-hidden="true">↗</span></a><a className="button" href="https://github.com/AaryanK/DragonZpyder">Explore the repository <span aria-hidden="true">↗</span></a></div><div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "22px", color: "var(--dim)", fontSize: "11px" }}><RuntimeDot /><RuntimeText /></div></div></div>
  </div></section>
  <section className="principle"><div className="wrap principle-grid"><div className="section-id">The name / Our philosophy</div><div><blockquote>Fire creates possibility.<br/>The spider weaves connection.<br/><em>Neither should be trapped.</em></blockquote><p>The dragon represents creative energy; the spider represents weaving independently existing things into a connected whole. DragonZpyder isn't trying to own every intelligence. It seeks to let people harness them together without becoming captive to any one system.</p></div></div></section>
  <section className="closing"><div className="wrap closing-inner"><div><div className="section-id">The direction is clear</div><h2>All that intelligence.<br/><span className="serif-em">One place to put it to work.</span></h2><p className="disclaimer">AI Mesh and AIC remain planned/research initiatives. Try the existing Personal experience or follow the development of the broader platform.</p></div><a className="button primary" href="/app">Open Personal AI <span aria-hidden="true">↗</span></a></div></section>
</main>
  <footer><div className="wrap footer-row"><a className="brand" href="#top"><img src="https://raw.githubusercontent.com/AaryanK/DragonZpyder-Landing/f18fa6a100eebfa8a43036d7baad5b85d9623785/favicon.png" width="27" height="27" alt=""/><span>DragonZpyder</span></a><div className="footer-links"><a href="#thesis">Why DragonZpyder</a><a href="#mesh">AI Mesh</a><a href="#credits">Project IC</a><a href="/app">Personal AI</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="https://github.com/AaryanK/DragonZpyder">GitHub</a></div><span>© <RuntimeYear /> DragonZpyder</span></div></footer>
  
    </>
  );
}
