// Pure trusted control-plane contract. Never accept these fields from an LLM.
const ID = /^[A-Za-z0-9_-]{4,160}$/;
export const SCOPED_TOOLS = Object.freeze([
  "terminal.exec", "python.exec", "files.list", "files.read", "files.write",
  "files.mkdir", "files.search", "git.status", "git.diff", "artifact.import",
  "artifact.export", "environment.info",
]);
const allowed = new Set(SCOPED_TOOLS);
function fail(message, statusCode = 422) {
  throw Object.assign(new Error(message), { statusCode });
}
export function parseScope(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("Computer scope is required");
  if (Object.keys(value).some(k => !["scopeKind","principalId","workspaceId","clientSessionId"].includes(k))) fail("Unknown scope field");
  const {scopeKind, principalId, workspaceId, clientSessionId} = value;
  if (!["personal","workspace"].includes(scopeKind)) fail("Invalid scope kind");
  if (typeof principalId !== "string" || !ID.test(principalId) ||
      typeof clientSessionId !== "string" || !ID.test(clientSessionId)) fail("Invalid scope identity");
  if (scopeKind === "personal" && workspaceId != null) fail("Personal scope cannot have workspace identity");
  if (scopeKind === "workspace" && (typeof workspaceId !== "string" || !ID.test(workspaceId))) fail("Workspace identity required");
  return {scopeKind, principalId, workspaceId: workspaceId ?? null, clientSessionId};
}
export function verifyScope(metadata, supplied, {allowExpired=false, now=Date.now()}={}) {
  const scope = parseScope(supplied);
  let saved;
  try { saved = parseScope(metadata?.scope); } catch { fail("Computer scope unavailable",403); }
  if (Object.keys(scope).some(k => scope[k] !== saved[k])) fail("Computer scope rejected",403);
  const expiry = Date.parse(metadata?.expiresAt);
  if (!Number.isFinite(expiry)) fail("Computer expiry unavailable",403);
  if (!allowExpired && now >= expiry) fail("Computer session expired",410);
  return scope;
}
export function parseCreate(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("Computer request is required");
  if (Object.keys(value).some(k => !["scope","profile","networkPolicy","ttlSeconds"].includes(k))) fail("Unknown create field");
  const scope = parseScope(value.scope);
  const profile = value.profile ?? "general";
  if (!["general","coding","data"].includes(profile)) fail("Invalid computer profile");
  if ((value.networkPolicy ?? "off") !== "off") fail("Network-enabled scoped sessions are not approved");
  const ttlSeconds = value.ttlSeconds ?? 900;
  if (!Number.isInteger(ttlSeconds) || ttlSeconds < 60 || ttlSeconds > 1800) fail("Invalid computer TTL");
  return {scope, profile, networkPolicy:"off", ttlSeconds};
}
export function parseToolArguments(tool, value) {
  if (!allowed.has(tool)) fail("Tool not approved in scoped runner",404);
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("Tool arguments must be an object");
  if ("background" in value || "env" in value) fail("Background execution and arbitrary environment overrides are not approved");
  if ("timeout_seconds" in value &&
      (!Number.isInteger(value.timeout_seconds) || value.timeout_seconds < 1 || value.timeout_seconds > 60))
    fail("Invalid tool deadline");
  const result = {...value};
  if (["terminal.exec","python.exec"].includes(tool)) result.timeout_seconds = value.timeout_seconds ?? 30;
  if (Buffer.byteLength(JSON.stringify(result)) > 25*1024*1024) fail("Tool arguments exceed policy",413);
  return result;
}

// Diagnostics contain fixed phase names and bounded numerical fields only.
export function bootstrapFailure(stage, error, cleanup = "not_attempted") {
  const stages = new Set(["template","sdk-create","sdk-ready","write-helper","prepare-workspace","write-scope-meta","write-public-meta","protect-session-meta","network-harden","network-verify","session-bootstrap"]);
  const cleanups = new Set(["not_attempted","confirmed","unconfirmed","unknown_allocation"]);
  const status = Number(error?.statusCode ?? error?.status ?? 503);
  const exit = error?.bootstrapExitCode;
  return {stage:stages.has(stage)?stage:"session-bootstrap",status:Number.isInteger(status)&&status>=400&&status<=599?status:503,
    exit_code:Number.isInteger(exit)&&exit>=0&&exit<=255?exit:null,
    cleanup:cleanups.has(cleanup)?cleanup:"unconfirmed"};
}
