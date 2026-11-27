import React, {useEffect, useRef, useState} from "react";
import {createVoiceOrbRenderer} from "./voice-canvas-renderer.js";
import "./voice-orb.css";

// The entire interface and lifecycle are React-owned. The canvas implements
// only the original uploaded artwork, with authentic fluid movement and glow.
// It never requests the microphone or starts a session on its own.
function VoiceArtworkCanvas({inputStream,outputStream,session}){
  const ref=useRef(null);
  const renderer=useRef(null);
  useEffect(()=>{
    const instance=createVoiceOrbRenderer(ref.current);
    renderer.current=instance;
    return ()=>{renderer.current=null;instance.destroy()};
  },[]);
  useEffect(()=>{renderer.current?.setActive(session!=="idle");return ()=>{}},[session]);
  useEffect(()=>{renderer.current?.setInputStream(inputStream);return ()=>{}},[inputStream]);
  useEffect(()=>{renderer.current?.setOutputStream(outputStream);return ()=>{}},[outputStream]);
  useEffect(()=>{renderer.current?.setStatus(session)},[session]);
  return <canvas className="dz-voice-original-canvas" ref={ref} aria-hidden="true"/>;
}

function SpeakerIcon({ muted }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M11 5 6 9H3v6h3l5 4V5Z"/>
    {muted ? <path d="m16 9 5 6m0-6-5 6"/> : <><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/></>}
  </svg>;
}

function MicrophoneIcon({ muted }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/>
    {muted && <path d="M4 4 20 20"/>}
  </svg>;
}

export function VoiceOrb() {
  const audioRef = useRef(null);
  const [session, setSession] = useState("idle");
  const [status, setStatus] = useState("Ready");
  const [connected, setConnected] = useState(false);
  const [voiceMode, setVoiceMode] = useState("realtime");
  const [inputStream, setInputStream] = useState(null);
  const [outputStream, setOutputStream] = useState(null);
  const [microphoneMuted, setMicrophoneMuted] = useState(false);
  const [playbackMuted, setPlaybackMuted] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [transcripts, setTranscripts] = useState([]);

  useEffect(() => {
    const events = {
      "dragonzpyder:voice-open": () => {
        setSession("connecting"); setStatus("Connecting…");
        setConnected(false); setVoiceMode("realtime"); setMicrophoneMuted(false); setTranscripts([]); setTranscriptOpen(false);
      },
      "dragonzpyder:voice-closed": () => {
        setSession("idle"); setConnected(false);
        setInputStream(null); setOutputStream(null); setMicrophoneMuted(false);
      },
      "dragonzpyder:voice-input": e => setInputStream(e.detail?.stream || null),
      "dragonzpyder:voice-output": e => setOutputStream(e.detail?.stream || null),
      "dragonzpyder:voice-state": e => {
        setSession(e.detail?.kind || "idle");
        setStatus(e.detail?.message || "Ready");
      },
      "dragonzpyder:voice-session": e => setConnected(Boolean(e.detail?.connected)),
      "dragonzpyder:voice-mode": e => setVoiceMode(["browser","openrouter"].includes(e.detail?.mode) ? e.detail.mode : "realtime"),
      "dragonzpyder:voice-mute": e => setMicrophoneMuted(Boolean(e.detail?.muted)),
      "dragonzpyder:voice-transcript": e => {
        const { id, label, value, append, interim } = e.detail || {};
        if (typeof value !== "string" || !value || !id || !label) return;
        setTranscripts(previous => {
          const index = previous.findIndex(item => item.id === id);
          if (index < 0) return [...previous.slice(-49), { id, label, value: value.slice(0, 4000), interim: Boolean(interim) }];
          const next = previous.slice();
          const old = next[index];
          next[index] = { ...old, value: (append ? old.value + value : value).slice(-4000), interim: Boolean(interim) };
          return next;
        });
      },
    };
    for (const [event, listener] of Object.entries(events)) window.addEventListener(event, listener);
    return () => { for (const [event, listener] of Object.entries(events)) window.removeEventListener(event, listener); };
  }, []);

  const togglePlayback = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !audioRef.current.muted;
    setPlaybackMuted(audioRef.current.muted);
    window.dispatchEvent(new CustomEvent("dragonzpyder:voice-playback-mute",{detail:{muted:audioRef.current.muted}}));
  };

  const browserOnly = voiceMode === "browser";
  const latestTranscript = transcripts[transcripts.length - 1];
  const label = browserOnly ? "TRANSCRIPTION" : session === "error" ? "VOICE ERROR" :
    connected ? "VOICE CONNECTED" :
    session === "connecting" ? "CONNECTING" : "PERSONAL VOICE";

  return <div className="dz-voice-orb-shell" data-connected={connected} data-session={session} data-voice-mode={voiceMode}>
    <VoiceArtworkCanvas inputStream={inputStream} outputStream={outputStream} session={session}/>
    <div className="dz-voice-orb-vignette" aria-hidden="true"/>
    <div className="dz-voice-orb-ui">
      <header className="dz-voice-orb-head">
        <div className="dz-voice-orb-brand"><img className="dz-voice-brandmark" src="/brand-icon.png" alt="" width="30" height="30"/><span>DRAGON<span>ZPYDER</span><small> / VOICE</small></span></div>
        <span className="dz-voice-orb-connection"><i aria-hidden="true"/>{label}</span>
      </header>
      <main className="dz-voice-orb-main">
        <p className="dz-voice-orb-eyebrow">SEE. HEAR. SPEAK. CREATE.</p>
        <div className="dz-voice-orb-space" aria-hidden="true" />
        <div className={"dz-voice-orb-conversation" + (session === "error" ? " is-error" : "")}>
          {session === "error"
            ? <div className="dz-voice-error-message" role="alert">
                <h2>{connected ? "Voice interrupted" : "Voice isn't available yet"}</h2>
                <p id="companion-status" role="status" aria-live="polite">{status}</p>
              </div>
            : <>
                <h2>{browserOnly ? "Speak naturally" : "Your intelligence, in conversation."}</h2>
                <p id="companion-status" role="status" aria-live="polite">{status}</p>
                {browserOnly && <>
                  <p className="dz-voice-browser-notice">Browser speech-to-text · No AI replies</p>
                  <p className="dz-voice-live-caption" data-interim={Boolean(latestTranscript?.interim)} aria-label="Latest transcription">{latestTranscript?.value || "Your words will appear here."}</p>
                </>}
              </>}
        </div>
      </main>
      <footer className="dz-voice-orb-footer">
        <p className="dz-voice-orb-footnote">DRAGONZPYDER PERSONAL / VOICE<br/>{browserOnly ? "BROWSER SPEECH RECOGNITION" : "SECURE SESSION · AUDIO STREAMED TO PROVIDER"}</p>
        <div className="dz-voice-orb-controls">
          <button type="button" className="dz-voice-orb-circle" aria-label={playbackMuted ? "Unmute speaker" : "Mute speaker"} onClick={togglePlayback} disabled={browserOnly} title={playbackMuted ? "Unmute AI playback" : "Mute AI playback"}>
            <SpeakerIcon muted={playbackMuted}/>
          </button>
          <button type="button" id="companion-mute" className={"dz-voice-orb-circle dz-voice-orb-mic" + (microphoneMuted ? " is-muted" : "")} disabled={!connected && !browserOnly} aria-label={microphoneMuted ? "Unmute microphone" : "Mute microphone"} title={microphoneMuted ? "Unmute microphone" : "Mute microphone"}>
            <MicrophoneIcon muted={microphoneMuted}/>
          </button>
          <button type="button" className="dz-voice-orb-circle" onClick={() => setTranscriptOpen(value => !value)} aria-label={transcriptOpen ? "Hide transcript" : "Show transcript"} aria-pressed={transcriptOpen} title="Transcript">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
          </button>
        </div>
        <button type="button" id="companion-end" className="dz-voice-orb-end" aria-label={session === "error" ? "Back to chat" : "End conversation"}>{session === "error" ? "Back to chat" : "End conversation"} <span aria-hidden="true">↗</span></button>
      </footer>
      <section className={"dz-voice-orb-transcript-panel" + (transcriptOpen ? " is-open" : "")} aria-label="Live voice transcript" aria-hidden={!transcriptOpen}>
        <div className="dz-voice-orb-transcript-heading">Live transcript <button type="button" onClick={() => setTranscriptOpen(false)} aria-label="Close transcript">×</button></div>
        <div className="companion-transcript" id="companion-transcript" aria-label="Live transcript">
          {transcripts.length ? transcripts.map(item => <p key={item.id} data-interim={Boolean(item.interim)}><strong>{item.label}: </strong><span>{item.value}</span></p>) : <p className="dz-voice-transcript-empty">Spoken words will appear here when transcription is available.</p>}
        </div>
        <p>{browserOnly ? "Speech recognition is provided by your browser and may use an online service. Transcriptions are not automatically sent to the agent." : voiceMode==="openrouter" ? "Speech is transcribed by OpenRouter and submitted to your DragonZpyder agent. The microphone pauses while the agent works and speaks." : "Voice is streamed to the provider. Agent access depends on your voice session."}</p>
      </section>
    </div>
    <audio ref={audioRef} id="companion-audio" autoPlay playsInline />
  </div>;
}
