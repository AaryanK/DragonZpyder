import React, {useEffect,useRef,useState} from "react";
import {createVoiceOrbRenderer} from "./voice-orb-renderer.js";
import "./voice-orb.css";

// This is presentation only. web/companion.js owns the realtime peer, tokened
// SDP exchange, microphone, delegation, approval checks and session cleanup.
export function VoiceOrb() {
  const canvas=useRef(null);
  const [transcriptOpen,setTranscriptOpen]=useState(false);
  const [playbackMuted,setPlaybackMuted]=useState(false);
  useEffect(()=>{
    const renderer=createVoiceOrbRenderer(canvas.current);
    const handlers={
      "dragonzpyder:voice-open":()=>renderer.setActive(true),
      "dragonzpyder:voice-closed":()=>{renderer.setInputStream(null);renderer.setOutputStream(null);renderer.setActive(false)},
      "dragonzpyder:voice-input":event=>renderer.setInputStream(event.detail?.stream||null),
      "dragonzpyder:voice-output":event=>renderer.setOutputStream(event.detail?.stream||null),
      "dragonzpyder:voice-state":event=>renderer.setStatus(event.detail?.kind||"idle"),
    };
    Object.entries(handlers).forEach(([event,callback])=>window.addEventListener(event,callback));
    return ()=>{Object.entries(handlers).forEach(([event,callback])=>window.removeEventListener(event,callback));renderer.destroy()};
  },[]);
  const togglePlayback=()=>{
    const output=document.getElementById("companion-audio");
    if(!output)return;
    output.muted=!output.muted;
    setPlaybackMuted(output.muted);
  };
  return <div className="dz-voice-orb-shell">
    <canvas ref={canvas} className="dz-voice-orb-stage" aria-hidden="true"/>
    <div className="dz-voice-orb-vignette" aria-hidden="true"/>
    <div className="dz-voice-orb-ui">
      <header className="dz-voice-orb-head">
        <div className="dz-voice-orb-brand"><img src="/brand-icon.png" alt=""/><span>DRAGON<span>ZPYDER</span><small> / VOICE</small></span></div>
        <span className="dz-voice-orb-connection"><i aria-hidden="true"/> PERSONAL VOICE</span>
      </header>
      <main className="dz-voice-orb-main">
        <p className="dz-voice-orb-eyebrow">SEE. HEAR. SPEAK. CREATE.</p>
        <div className="dz-voice-orb-space" aria-hidden="true"/>
        <div className="dz-voice-orb-conversation">
          <h2>Voice, without interruption.</h2>
          <p id="companion-status" role="status" aria-live="polite">Ready</p>
        </div>
      </main>
      <footer className="dz-voice-orb-footer">
        <p className="dz-voice-orb-footnote">DRAGONZPYDER PERSONAL<br/>LIVE VOICE · SIGNED-IN SESSION</p>
        <div className="dz-voice-orb-controls">
          <button type="button" className="dz-voice-orb-circle" aria-label={playbackMuted?"Unmute speaker":"Mute speaker"} onClick={togglePlayback} title={playbackMuted?"Unmute AI playback":"Mute AI playback"}>
            {playbackMuted?<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="m16 9 5 6m0-6-5 6"/></svg>:<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/></svg>}
          </button>
          <button type="button" id="companion-mute" className="dz-voice-orb-circle dz-voice-orb-mic" disabled aria-label="Mute microphone">Mute</button>
          <button type="button" className="dz-voice-orb-circle" onClick={()=>setTranscriptOpen(v=>!v)} aria-label={transcriptOpen?"Hide transcript":"Show transcript"} aria-pressed={transcriptOpen} title="Transcript">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
          </button>
        </div>
        <button type="button" id="companion-end" className="dz-voice-orb-end">End conversation <span aria-hidden="true">↗</span></button>
      </footer>
      <section className={"dz-voice-orb-transcript-panel"+(transcriptOpen?" is-open":"")} aria-label="Live voice transcript" aria-hidden={!transcriptOpen}>
        <div className="dz-voice-orb-transcript-heading">Live transcript <button type="button" onClick={()=>setTranscriptOpen(false)} aria-label="Close transcript">×</button></div>
        <div className="companion-transcript" id="companion-transcript" aria-label="Live transcript"/>
        <p>Voice is streamed to the provider. Connected actions still require your Personal permissions and approvals.</p>
      </section>
    </div>
  </div>;
}
