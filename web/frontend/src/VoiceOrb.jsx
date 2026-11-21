import React, { useEffect, useMemo, useRef, useState } from "react";
import "./voice-orb.css";

// All visible voice UI is React (including SVG, captions, controls and transcript).
// companion.js alone owns authenticated WebRTC and permissioned Personal delegation.
const TAU = Math.PI * 2;
const clamp = value => Math.max(0, Math.min(1, value));

const STARFIELD = Array.from({ length: 90 }, (_, i) => {
  // Deterministic positions: identical SVG across renders and device sizes.
  const x = ((Math.sin(i * 127.1 + 45.8) * 43758.5453) % 1 + 1) % 1;
  const y = ((Math.sin(i * 311.7 + 12.7) * 22578.1453) % 1 + 1) % 1;
  return { x: x * 760, y: y * 760, r: 0.35 + (i % 7) * 0.14, opacity: 0.18 + (i % 5) * 0.07 };
});

const FLUID_PATHS = Array.from({ length: 24 }, (_, k) => {
  const base = 348 + (k - 11.5) * 15;
  const points = Array.from({ length: 38 }, (_, j) => {
    const x = 105 + j * 15;
    const u = (x - 380) / 195;
    const y = base + 19 * Math.sin(u * 2.7 + k * 0.25) + 8 * Math.sin(u * 7.3 - k * 0.34);
    return (j ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  });
  return { d: points.join(" "), opacity: 0.10 + 0.12 * (1 - Math.abs(k - 11.5) / 12), delay: -(k % 9) * 0.37 };
});

const FILAMENTS = Array.from({ length: 34 }, (_, k) => {
  const y = 167 + k * 11.1;
  const x1 = 134 - (k % 4) * 10;
  const x2 = 625 + (k % 6) * 8;
  const bend = 19 * Math.sin(k * 0.53);
  return { d: `M ${x1} ${y.toFixed(1)} Q 380 ${(y + bend).toFixed(1)} ${x2} ${(y - bend * 0.6).toFixed(1)}`, delay: -(k % 6) * 0.48 };
});

const MOTES = Array.from({ length: 46 }, (_, i) => {
  const a = (i * 2.39996) % TAU;
  const r = 208 + (i % 9) * 20;
  return { x: 380 + Math.cos(a) * r, y: 350 + Math.sin(a) * r * 0.77, size: 0.7 + (i % 4) * 0.38, opacity: 0.10 + (i % 5) * 0.065 };
});

function VoiceOrbArtwork({ level, activity }) {
  // SVG is a native React tree, not an imperative canvas or injected HTML.
  // Independent CSS keyframes animate the flowing ribbons; energy is measured
  // from the actual microphone/provider audio, not generated demo sound.
  const energy = clamp(level);
  const variables = {
    "--dz-voice-energy": energy.toFixed(3),
    "--dz-voice-scale": (1 + energy * 0.085).toFixed(4),
    "--dz-voice-wave-scale": (0.55 + energy * 1.8).toFixed(3),
    "--dz-voice-glow-opacity": (0.63 + energy * 0.36).toFixed(3),
  };
  const nativeSvg = useMemo(() => (
    <svg className="dz-voice-art-svg" viewBox="0 0 760 760" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        <defs>
          <radialGradient id="dz-orb-background">
            <stop offset="0" stopColor="#24435b" stopOpacity=".30" />
            <stop offset=".42" stopColor="#172838" stopOpacity=".20" />
            <stop offset="1" stopColor="#08090d" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="dz-orb-halo">
            <stop offset="0" stopColor="#f5a374" stopOpacity=".31" />
            <stop offset=".39" stopColor="#a36391" stopOpacity=".19" />
            <stop offset=".76" stopColor="#3366a8" stopOpacity=".10" />
            <stop offset="1" stopColor="#08090d" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="dz-orb-body" cx="29%" cy="20%" r="91%">
            <stop offset="0" stopColor="#e8a17e" />
            <stop offset=".17" stopColor="#b96c75" />
            <stop offset=".37" stopColor="#70456c" />
            <stop offset=".56" stopColor="#352d59" />
            <stop offset=".78" stopColor="#172541" />
            <stop offset="1" stopColor="#091522" />
          </radialGradient>
          <radialGradient id="dz-orb-face" cx="24%" cy="17%" r="83%">
            <stop offset="0" stopColor="#ffdbb8" stopOpacity=".29" />
            <stop offset=".38" stopColor="#d988ae" stopOpacity=".06" />
            <stop offset=".73" stopColor="#060a19" stopOpacity=".04" />
            <stop offset="1" stopColor="#040714" stopOpacity=".84" />
          </radialGradient>
          <linearGradient id="dz-orb-edge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#ffe3c2" stopOpacity=".97" />
            <stop offset=".28" stopColor="#f7a47c" stopOpacity=".68" />
            <stop offset=".52" stopColor="#6f96cd" stopOpacity=".22" />
            <stop offset=".78" stopColor="#68b4d6" stopOpacity=".39" />
            <stop offset="1" stopColor="#f5a68f" stopOpacity=".75" />
          </linearGradient>
          <linearGradient id="dz-orb-ribbon" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#f9acbf" stopOpacity="0" />
            <stop offset=".26" stopColor="#ffd7bd" stopOpacity=".54" />
            <stop offset=".51" stopColor="#fcb6d4" stopOpacity=".49" />
            <stop offset=".74" stopColor="#bda9df" stopOpacity=".31" />
            <stop offset="1" stopColor="#6a9dd2" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="dz-orb-wave" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#6dcddd" stopOpacity="0" />
            <stop offset=".3" stopColor="#8be9ee" stopOpacity=".54" />
            <stop offset=".51" stopColor="#f4aa87" stopOpacity=".92" />
            <stop offset=".72" stopColor="#84d4ef" stopOpacity=".55" />
            <stop offset="1" stopColor="#6dcddd" stopOpacity="0" />
          </linearGradient>
          <clipPath id="dz-orb-clip"><circle cx="380" cy="350" r="180" /></clipPath>
          <filter id="dz-orb-blur"><feGaussianBlur stdDeviation="23" /></filter>
          <filter id="dz-orb-light"><feGaussianBlur stdDeviation="5" /></filter>
        </defs>

        <circle cx="380" cy="350" r="365" fill="url(#dz-orb-background)" />
        <g className="dz-voice-stars">
          {STARFIELD.map((star, i) => (
            <circle key={i} cx={star.x} cy={star.y} r={star.r} fill="#88bfce" opacity={star.opacity} />
          ))}
        </g>

        <g className="dz-voice-orbit-field">
          {[0, 1, 2, 3].map(i => (
            <ellipse key={i} cx="380" cy="350" rx={245 + i * 27} ry={168 + i * 20} transform="rotate(-19 380 350)" stroke="#78cfe4" strokeWidth=".7" fill="none" opacity={0.11 - i * 0.017} />
          ))}
        </g>
        <circle className="dz-voice-halo" cx="380" cy="350" r="330" fill="url(#dz-orb-halo)" />
        <circle cx="380" cy="350" r="197" fill="#ef967c" opacity=".23" filter="url(#dz-orb-blur)" />
        <g className="dz-voice-sphere">
          <circle cx="380" cy="350" r="180" fill="url(#dz-orb-body)" />
          <g clipPath="url(#dz-orb-clip)">
            <ellipse cx="302" cy="227" rx="149" ry="116" fill="#edbbad" opacity=".16" filter="url(#dz-orb-blur)" />
            <ellipse cx="503" cy="469" rx="160" ry="126" fill="#356ea4" opacity=".23" filter="url(#dz-orb-blur)" />
            <g className="dz-voice-fluid-ribbons">
              {FLUID_PATHS.map((path, i) => (
                <path key={i} d={path.d} stroke="url(#dz-orb-ribbon)" strokeWidth={8 + (i % 4) * 3} strokeLinecap="round" fill="none" opacity={path.opacity} style={{ animationDelay: path.delay + "s" }} />
              ))}
            </g>
            <g className="dz-voice-fluid-filaments">
              {FILAMENTS.map((path, i) => (
                <path key={i} d={path.d} stroke={i % 3 ? "#ffe0cf" : "#92b6da"} strokeWidth=".65" fill="none" opacity={0.12 + (i % 5) * 0.026} style={{ animationDelay: path.delay + "s" }} />
              ))}
            </g>
            <circle cx="380" cy="350" r="180" fill="url(#dz-orb-face)" />
          </g>
          <circle cx="380" cy="350" r="179" stroke="url(#dz-orb-edge)" strokeWidth="2.3" fill="none" />
          <path d="M 230 253 A 179 179 0 0 1 444 183" stroke="#ffe5d1" strokeWidth="3.1" strokeLinecap="round" opacity=".47" fill="none" filter="url(#dz-orb-light)" />
          <path d="M 228 257 A 179 179 0 0 1 430 179" stroke="#ffe8d2" strokeWidth="1.8" strokeLinecap="round" opacity=".53" fill="none" />
        </g>

        <g className="dz-voice-orbit dz-voice-orbit-one">
          <ellipse cx="380" cy="350" rx="209" ry="154" transform="rotate(-20 380 350)" stroke="#80bddb" strokeWidth="1.2" opacity=".25" fill="none" />
        </g>
        <g className="dz-voice-orbit dz-voice-orbit-two">
          <ellipse cx="380" cy="350" rx="236" ry="179" transform="rotate(14 380 350)" stroke="#8bd5f3" strokeWidth="1" opacity=".16" fill="none" />
        </g>
        {[0, 1, 2].map(i => (
          <ellipse key={i} className="dz-voice-ripple" cx="380" cy="350" rx={213 + i * 36} ry={184 + i * 30} transform="rotate(-12 380 350)" stroke="#6ad7ec" strokeWidth="1" opacity={0.16 - i * .04} fill="none" style={{ animationDelay: -i * 1.7 + "s" }} />
        ))}
        <g className="dz-voice-motes">
          {MOTES.map((mote, i) => (
            <circle key={i} cx={mote.x} cy={mote.y} r={mote.size} fill="#f8b69f" opacity={mote.opacity} />
          ))}
        </g>
        <g className="dz-voice-audio-wave">
          <path d="M 110 636 C 165 635 173 623 210 636 S 258 654 284 634 S 326 605 347 638 S 369 661 387 635 S 429 599 449 633 S 484 652 511 637 S 574 632 649 636" fill="none" stroke="url(#dz-orb-wave)" strokeWidth="2.2" />
          <path d="M 122 637 C 184 638 203 623 230 637 S 281 649 301 636 S 337 621 356 637 S 393 649 417 636 S 462 622 481 636 S 544 642 637 637" fill="none" stroke="#91d7ed" strokeWidth=".85" opacity=".36" />
        </g>
    </svg>
  ), []);
  return <div className="dz-voice-artwork" data-activity={activity} style={variables} aria-hidden="true">
    <div className="dz-voice-atmosphere" />
    {nativeSvg}
  </div>;
}

function useVoiceEnergy(inputStream, outputStream) {
  const [energy, setEnergy] = useState(0);
  useEffect(() => {
    const streams = [inputStream, outputStream].filter(s => s?.getAudioTracks?.().length);
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!streams.length || !AudioContextClass) { setEnergy(0); return; }
    let context, frame = 0, last = 0, closed = false;
    const analysers = [];
    try {
      context = new AudioContextClass();
      // Keep analyser nodes running without duplicating audible voice output.
      const silentSink = context.createGain();
      silentSink.gain.value = 0;
      silentSink.connect(context.destination);
      for (const stream of streams) {
        // Meter only: do not route the remote stream to the speakers a second time.
        const source = context.createMediaStreamSource(stream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = .78;
        source.connect(analyser);
        analyser.connect(silentSink);
        analysers.push({ analyser, data: new Uint8Array(analyser.fftSize) });
      }
      context.resume().catch(() => {});
    } catch (error) {
      context?.close().catch(() => {});
      return;
    }
    const sample = now => {
      if (closed) return;
      if (now - last >= 65) {
        last = now;
        let strongest = 0;
        for (const { analyser, data } of analysers) {
          analyser.getByteTimeDomainData(data);
          let sum = 0;
          for (let i = 0; i < data.length; i += 4) {
            const v = (data[i] - 128) / 128;
            sum += v * v;
          }
          strongest = Math.max(strongest, Math.sqrt(sum / (data.length / 4)) * 7);
        }
        setEnergy(previous => {
          const target = strongest < .025 ? 0 : clamp(strongest);
          const next = previous + (target - previous) * .28;
          return Math.abs(next - previous) < .008 ? previous : Number(next.toFixed(3));
        });
      }
      frame = requestAnimationFrame(sample);
    };
    frame = requestAnimationFrame(sample);
    return () => { closed = true; cancelAnimationFrame(frame); context?.close().catch(() => {}); };
  }, [inputStream, outputStream]);
  return energy;
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
  const [inputStream, setInputStream] = useState(null);
  const [outputStream, setOutputStream] = useState(null);
  const [microphoneMuted, setMicrophoneMuted] = useState(false);
  const [playbackMuted, setPlaybackMuted] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [transcripts, setTranscripts] = useState([]);
  const level = useVoiceEnergy(inputStream, outputStream);

  useEffect(() => {
    const events = {
      "dragonzpyder:voice-open": () => {
        setSession("connecting"); setStatus("Connecting…");
        setConnected(false); setMicrophoneMuted(false); setTranscripts([]);
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
      "dragonzpyder:voice-mute": e => setMicrophoneMuted(Boolean(e.detail?.muted)),
      "dragonzpyder:voice-transcript": e => {
        const { id, label, value, append } = e.detail || {};
        if (typeof value !== "string" || !value || !id || !label) return;
        setTranscripts(previous => {
          const index = previous.findIndex(item => item.id === id);
          if (index < 0) return [...previous.slice(-49), { id, label, value: value.slice(0, 4000) }];
          const next = previous.slice();
          const old = next[index];
          next[index] = { ...old, value: (append ? old.value + value : value).slice(-4000) };
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
  };

  const label = session === "error" ? "VOICE ERROR" :
    connected ? "VOICE CONNECTED" :
    session === "connecting" ? "CONNECTING" : "PERSONAL VOICE";

  return <div className="dz-voice-orb-shell" data-connected={connected} data-session={session}>
    <VoiceOrbArtwork level={level} activity={session} />
    <div className="dz-voice-orb-vignette" aria-hidden="true"/>
    <div className="dz-voice-orb-ui">
      <header className="dz-voice-orb-head">
        <div className="dz-voice-orb-brand"><span className="dz-voice-brandmark" aria-hidden="true"/><span>DRAGON<span>ZPYDER</span><small> / VOICE</small></span></div>
        <span className="dz-voice-orb-connection"><i aria-hidden="true"/>{label}</span>
      </header>
      <main className="dz-voice-orb-main">
        <p className="dz-voice-orb-eyebrow">SEE. HEAR. SPEAK. CREATE.</p>
        <div className="dz-voice-orb-space" aria-hidden="true"/>
        <div className="dz-voice-orb-conversation">
          <h2>{connected ? "Your intelligence, in conversation." : session === "error" ? "Voice connection unavailable." : "Your intelligence, in conversation."}</h2>
          <p id="companion-status" role="status" aria-live="polite">{status}</p>
        </div>
      </main>
      <footer className="dz-voice-orb-footer">
        <p className="dz-voice-orb-footnote">DRAGONZPYDER PERSONAL / VOICE<br/>SECURE SESSION · AUDIO STREAMED TO PROVIDER</p>
        <div className="dz-voice-orb-controls">
          <button type="button" className="dz-voice-orb-circle" aria-label={playbackMuted ? "Unmute speaker" : "Mute speaker"} onClick={togglePlayback} title={playbackMuted ? "Unmute AI playback" : "Mute AI playback"}>
            <SpeakerIcon muted={playbackMuted}/>
          </button>
          <button type="button" id="companion-mute" className={"dz-voice-orb-circle dz-voice-orb-mic" + (microphoneMuted ? " is-muted" : "")} disabled={!connected} aria-label={microphoneMuted ? "Unmute microphone" : "Mute microphone"} title={microphoneMuted ? "Unmute microphone" : "Mute microphone"}>
            <MicrophoneIcon muted={microphoneMuted}/>
          </button>
          <button type="button" className="dz-voice-orb-circle" onClick={() => setTranscriptOpen(value => !value)} aria-label={transcriptOpen ? "Hide transcript" : "Show transcript"} aria-pressed={transcriptOpen} title="Transcript">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
          </button>
        </div>
        <button type="button" id="companion-end" className="dz-voice-orb-end" aria-label="End conversation">End conversation <span aria-hidden="true">↗</span></button>
      </footer>
      <section className={"dz-voice-orb-transcript-panel" + (transcriptOpen ? " is-open" : "")} aria-label="Live voice transcript" aria-hidden={!transcriptOpen}>
        <div className="dz-voice-orb-transcript-heading">Live transcript <button type="button" onClick={() => setTranscriptOpen(false)} aria-label="Close transcript">×</button></div>
        <div className="companion-transcript" id="companion-transcript" aria-label="Live transcript">
          {transcripts.length ? transcripts.map(item => <p key={item.id}><strong>{item.label}: </strong><span>{item.value}</span></p>) : <p className="dz-voice-transcript-empty">Spoken words will appear here when transcription is available.</p>}
        </div>
        <p>Voice is streamed to the provider. Connected actions still require your Personal permissions and approvals.</p>
      </section>
    </div>
    <audio ref={audioRef} id="companion-audio" autoPlay playsInline />
  </div>;
}
