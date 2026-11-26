// The portable, declarative contract. No DOM, storage, code evaluation or network.
export const INTERFACE_VERSION = 1;
const freeze = value => Object.freeze(value);
const choices = freeze({
  accent: freeze(["default", "blue", "violet", "teal"]),
  font: freeze(["default", "system", "serif", "mono"]),
  messageSize: freeze([14, 15, 16, 18, 20]),
  contentWidth: freeze(["default", "narrow", "wide"]),
  motion: freeze(["default", "reduced"]),
});
export const COMPONENTS = freeze([
  freeze({id:"workspace", role:"layout", properties:freeze(["font","accent","motion"])}),
  freeze({id:"conversation", role:"content", properties:freeze(["messageSize","contentWidth"])}),
  freeze({id:"composer", role:"input", properties:freeze(["contentWidth"])}),
  freeze({id:"approval", role:"security", properties:freeze([])}),
  freeze({id:"identity", role:"security", properties:freeze([])}),
]);
export const DEFAULT_PREFERENCES = freeze({
  accent:"default", font:"default", messageSize:15, contentWidth:"default", motion:"default",
});
const plain = value => value !== null && typeof value === "object" &&
  (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
export function initialInterface() {
  return freeze({version:INTERFACE_VERSION, revision:0, preferences:DEFAULT_PREFERENCES});
}
export function inspectInterface(state) {
  return {version:state.version, revision:state.revision,
    preferences:{...state.preferences}, choices, components:COMPONENTS,
    persistence:"mounted-session-only", transport:"local-only"};
}
// Atomic, explicit, closed-world patch. Unknown fields are errors, not CSS/HTML.
export function patchInterface(state, request) {
  if (!plain(request) || Object.keys(request).length !== 2 ||
      !Object.hasOwn(request,"expectedRevision") || !Object.hasOwn(request,"changes") ||
      request.expectedRevision !== state.revision || !plain(request.changes)) {
    throw new Error("Invalid or stale interface patch");
  }
  const keys = Reflect.ownKeys(request.changes);
  if (!keys.length || keys.length > Object.keys(choices).length) throw new Error("Invalid changes");
  for (const key of keys) {
    if (typeof key !== "string" || !Object.hasOwn(choices,key) ||
        !choices[key].includes(request.changes[key])) throw new Error("Unsupported interface property");
  }
  const preferences = freeze({...state.preferences,...request.changes});
  if (keys.every(key => preferences[key] === state.preferences[key])) return state;
  if (!Number.isSafeInteger(state.revision+1)) throw new Error("Revision exhausted");
  return freeze({version:INTERFACE_VERSION, revision:state.revision+1, preferences});
}
export function resetInterface(state) {
  return patchInterface(state,{expectedRevision:state.revision,changes:DEFAULT_PREFERENCES});
}
