import React, {useEffect,useState} from "react";
import {initialInterface,inspectInterface,patchInterface,resetInterface} from "./adaptive-interface.js";
import "./adaptive-interface.css";

const accents = {blue:"#1554a8",violet:"#7040a8",teal:"#08675d"};
const fonts = {system:'system-ui,sans-serif',serif:'Georgia,serif',mono:'ui-monospace,monospace'};
const widths = {narrow:"660px",wide:"1100px"};
// The renderer owns the mapping. No supplied CSS, HTML, selectors or actions.
export function AdaptiveInterface() {
  const [state,setState] = useState(initialInterface);
  const [open,setOpen] = useState(false);
  const snapshot = inspectInterface(state);
  const p = snapshot.preferences;
  const change = (key,value) => setState(current => patchInterface(current,{
    expectedRevision:current.revision,changes:{[key]:value}
  }));
  useEffect(() => {
    const shell = document.getElementById("app-shell");
    if (!shell) return;
    const values = {
      "--dz-adaptive-accent":accents[p.accent],
      "--dz-adaptive-font":fonts[p.font],
      "--dz-adaptive-message-size":p.messageSize===15?undefined:p.messageSize+"px",
      "--dz-adaptive-width":widths[p.contentWidth],
    };
    for (const [key,value] of Object.entries(values)) {
      if (value) shell.style.setProperty(key,value); else shell.style.removeProperty(key);
    }
    if (p.motion==="reduced") shell.setAttribute("data-dz-adaptive-motion","reduced");
    else shell.removeAttribute("data-dz-adaptive-motion");
    return () => {
      for (const key of Object.keys(values)) shell.style.removeProperty(key);
      shell.removeAttribute("data-dz-adaptive-motion");
    };
  },[p.accent,p.font,p.messageSize,p.contentWidth,p.motion]);
  return <div className="dz-adaptive-control">
    <button type="button" className="dz-adaptive-trigger" aria-expanded={open}
      aria-controls="dz-adaptive-panel" onClick={()=>setOpen(!open)}>Customize</button>
    {open && <section className="dz-adaptive-panel" id="dz-adaptive-panel" aria-label="Customize conversation">
      <h2>Customize conversation</h2>
      <p>Changes apply only to this open page. Account and approval controls are unchanged.</p>
      <label>Accent<select value={p.accent} onChange={e=>change("accent",e.target.value)}>
        {snapshot.choices.accent.map(value=><option key={value}>{value}</option>)}
      </select></label>
      <label>Conversation font<select value={p.font} onChange={e=>change("font",e.target.value)}>
        {snapshot.choices.font.map(value=><option key={value}>{value}</option>)}
      </select></label>
      <label>Message size<select value={p.messageSize} onChange={e=>change("messageSize",Number(e.target.value))}>
        {snapshot.choices.messageSize.map(value=><option key={value} value={value}>{value===15?"Default":value+" px"}</option>)}
      </select></label>
      <label>Content width<select value={p.contentWidth} onChange={e=>change("contentWidth",e.target.value)}>
        {snapshot.choices.contentWidth.map(value=><option key={value}>{value}</option>)}
      </select></label>
      <label>Conversation motion<select value={p.motion} onChange={e=>change("motion",e.target.value)}>
        {snapshot.choices.motion.map(value=><option key={value}>{value}</option>)}
      </select></label>
      <button type="button" onClick={()=>setState(resetInterface)}>Restore defaults</button>
      <details><summary>Interface state</summary><pre>{JSON.stringify(snapshot,null,2)}</pre></details>
      <button type="button" onClick={()=>setOpen(false)}>Close</button>
    </section>}
  </div>;
}
