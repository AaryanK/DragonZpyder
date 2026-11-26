import React,{useEffect,useState} from "react";
import {defaultUiPreferences,readUiPreferences,saveUiPreferences,normalizeUiPreferences} from "./ui-preferences.js";
import {UiIcon} from "./UiIcon.jsx";

// These settings are intentionally browser-local until an authenticated,
// versioned preference API is available. Changes never alter runtime authority.
export function AppearanceSettings(){
 const [value,setValue]=useState(defaultUiPreferences),[message,setMessage]=useState("");
 useEffect(()=>setValue(readUiPreferences()),[]);
 function change(next){const valid=normalizeUiPreferences(next);setValue(valid);setMessage(saveUiPreferences(valid)?"Appearance saved on this device.":"Appearance applied; browser storage is unavailable.");}
 return <section className="dz-account-group dz-appearance-settings" id="dz-appearance">
 <div className="dz-account-group-heading"><div><h3>Appearance</h3><p className="muted small">Saved on this device.</p></div><span className="dz-account-symbol"><UiIcon name="sun"/></span></div>
 <div className="dz-preference-grid">
 <label>Theme<select value={value.theme} onChange={e=>change({...value,theme:e.target.value})}><option value="light">Light</option><option value="dark">Dark</option></select></label>
 <label>Layout density<select value={value.density} onChange={e=>change({...value,density:e.target.value})}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
 <label>Chat text size<select value={value.textSize} onChange={e=>change({...value,textSize:e.target.value})}><option value="normal">Normal</option><option value="large">Large</option><option value="extra-large">Extra large</option></select></label>
 <label className="dz-preference-checkbox"><input type="checkbox" checked={value.reducedMotion} onChange={e=>change({...value,reducedMotion:e.target.checked})}/> Reduce interface motion</label>
 </div><div className="dz-preference-footer"><button type="button" className="dz-account-resource-action" onClick={()=>change(defaultUiPreferences)}>Restore defaults</button><span role="status">{message}</span></div>
 </section>;
}
