/** Versioned browser-local presentation configuration. No auth or execution
 * permissions, URLs, arbitrary CSS/HTML, scripts or selectors are accepted. */
const key="dragonzpyder:ui-preferences:v1";
const themeKey="dragonzpyder:workspace-theme";
export const defaultUiPreferences=Object.freeze({version:1,theme:"light",density:"comfortable",textSize:"normal",reducedMotion:false});
export const uiPreferenceSchema=Object.freeze({
  version:1,
  fields:Object.freeze({
    theme:Object.freeze(["light","dark"]),
    density:Object.freeze(["comfortable","compact"]),
    textSize:Object.freeze(["normal","large","extra-large"]),
    reducedMotion:Object.freeze([true,false])
  })
});
export function normalizeUiPreferences(value){
  const input=value&&typeof value==="object"&&!Array.isArray(value)&&value.version===1?value:{};
  return {version:1,theme:uiPreferenceSchema.fields.theme.includes(input.theme)?input.theme:defaultUiPreferences.theme,
    density:uiPreferenceSchema.fields.density.includes(input.density)?input.density:defaultUiPreferences.density,
    textSize:uiPreferenceSchema.fields.textSize.includes(input.textSize)?input.textSize:defaultUiPreferences.textSize,
    reducedMotion:input.reducedMotion===true};
}
export function readUiPreferences(){
  try{
    const saved=normalizeUiPreferences(JSON.parse(localStorage.getItem(key)||"null"));
    const theme=localStorage.getItem(themeKey);
    return {...saved,theme:uiPreferenceSchema.fields.theme.includes(theme)?theme:saved.theme};
  }catch{return {...defaultUiPreferences};}
}
export function applyUiPreferences(value){
  const prefs=normalizeUiPreferences(value);
  const root=document.documentElement;
  root.dataset.workspaceTheme=prefs.theme;
  root.dataset.dzDensity=prefs.density;
  root.dataset.dzTextSize=prefs.textSize;
  root.dataset.dzReducedMotion=String(prefs.reducedMotion);
  return prefs;
}
export function saveUiPreferences(value){
  const prefs=applyUiPreferences(value);
  try{localStorage.setItem(key,JSON.stringify(prefs));localStorage.setItem(themeKey,prefs.theme);return true;}
  catch{return false;}
}
