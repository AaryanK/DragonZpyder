import crypto from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Sandbox } from "railway";
import { SCOPED_TOOLS, parseCreate, verifyScope, parseToolArguments } from "./scope.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const TOOL_HELPER = await fs.readFile(path.join(here, "computer_tool.py"));
const PORT = Math.max(1, Math.min(Number(process.env.PORT || 3000), 65535));
const RUNNER_TOKEN = String(process.env.DRAGONZPYDER_RUNNER_TOKEN || "").trim();
const RUNNER_SIGNING_KEY = String(process.env.DRAGONZPYDER_RUNNER_SIGNING_KEY || "").trim();
const ENVIRONMENT_ID = String(process.env.RAILWAY_ENVIRONMENT_ID || "").trim();
const MAX_REQUEST_BYTES = 30 * 1024 * 1024;
const MAX_RESPONSE_BYTES = 25 * 1024 * 1024;
const MAX_CLOCK_SKEW_MS = Math.max(10000, Math.min(Number(process.env.DRAGONZPYDER_RUNNER_MAX_CLOCK_SKEW_MS || 120000), 300000));
const REPLAY_TTL_MS = MAX_CLOCK_SKEW_MS * 2;
const SESSION_RE = /^[A-Za-z0-9_-]{4,200}$/;
const TOOL_RE = /^[a-z][a-z0-9_.-]{1,120}$/;
const NONCE_RE = /^[A-Za-z0-9_-]{16,200}$/;
const PYTHON = "/opt/operly-py/bin/python";
const WORKSPACE = "/workspace/work";
const REQUESTS = "/opt/dz-computer-requests";
const SCOPE_META = "/opt/dz-computer-scope.json";
const PUBLIC_META = "/opt/dz-computer-public.json";
const EXEC_PROXY_NOT_READY = "tcp-proxy exec WebSocket connection failed.";

const TOOL_IDS = SCOPED_TOOLS;
const TOOL_SET = new Set(TOOL_IDS);
const replayNonces = new Map();

let cachedTemplate = null;
let templateWarmPromise = null;
let templateWarmState = "idle";
let templateWarmStartedAt = null;
let templateWarmedAt = null;
let templateWarmLastError = null;

function computerTemplate() {
  if (cachedTemplate) return cachedTemplate;
  cachedTemplate = Sandbox.template()
    .withPackages(
      "bash", "build-essential", "ca-certificates", "chromium", "curl", "ffmpeg", "file", "git",
      "iptables", "jq", "nodejs", "npm", "poppler-utils", "procps", "python3", "python3-pip",
      "python3-venv", "ripgrep", "unzip", "wget", "zip",
    )
    .run("python3 -m venv /opt/operly-py")
    .run(
      "/opt/operly-py/bin/pip install --no-cache-dir " +
      "beautifulsoup4 duckdb httpx imageio lxml matplotlib numpy odfpy openpyxl pandas Pillow " +
      "playwright polars pyarrow PyMuPDF pypdf python-docx python-pptx PyYAML reportlab requests scipy soundfile",
    )
    .run("id -u operly >/dev/null 2>&1 || useradd -m -u 10001 -s /bin/bash operly")
    .run("mkdir -p /workspace/work /workspace/.operly/requests /workspace/.operly/processes && chown -R operly:operly /workspace");
  return cachedTemplate;
}

function templateWarmStatus() {
  return {
    state: templateWarmState,
    ready: templateWarmState === "ready",
    started_at: templateWarmStartedAt,
    warmed_at: templateWarmedAt,
    last_error: templateWarmLastError ? "template build failed" : null,
  };
}

function ensureComputerTemplateWarm() {
  if (templateWarmState === "ready") return Promise.resolve();
  if (templateWarmPromise) return templateWarmPromise;

  templateWarmState = "warming";
  templateWarmStartedAt = new Date().toISOString();
  templateWarmLastError = null;
  const started = Date.now();
  console.log("Agent Computer template warm started");

  templateWarmPromise = computerTemplate()
    .build({ environmentId: ENVIRONMENT_ID })
    .then(() => {
      templateWarmState = "ready";
      templateWarmedAt = new Date().toISOString();
      templateWarmLastError = null;
      console.log(`Agent Computer template ready in ${Date.now() - started}ms`);
    })
    .catch((error) => {
      templateWarmState = "failed";
      templateWarmLastError = String(error?.message || error).slice(0, 1000);
      console.error(`Agent Computer template warm failed after ${Date.now() - started}ms: ${templateWarmLastError}`);
      throw error;
    })
    .finally(() => {
      templateWarmPromise = null;
    });

  return templateWarmPromise;
}

function hmac(value) {
  return crypto.createHmac("sha256", RUNNER_SIGNING_KEY).update(value).digest("hex");
}

function safeEqual(left, right) {
  const a = Buffer.from(String(left || ""));
  const b = Buffer.from(String(right || ""));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function canonical(method, pathname, timestamp, nonce, raw) {
  return Buffer.concat([
    Buffer.from(`${method.toUpperCase()}\n${pathname}\n${timestamp}\n${nonce}\n`, "utf8"),
    raw,
  ]);
}

function pruneReplayNonces(now = Date.now()) {
  for (const [nonce, expiresAt] of replayNonces) {
    if (expiresAt <= now) replayNonces.delete(nonce);
  }
  // Never evict a still-valid nonce: fail closed on capacity instead.
}

async function readBody(req, limit = MAX_REQUEST_BYTES) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > limit) throw Object.assign(new Error("request body too large"), { statusCode: 413 });
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

function authenticate(req, pathname, raw) {
  if (!RUNNER_TOKEN || !RUNNER_SIGNING_KEY) throw Object.assign(new Error("runner authentication is not configured"), { statusCode: 503 });
  const auth = String(req.headers.authorization || "");
  if (!safeEqual(auth, `Bearer ${RUNNER_TOKEN}`)) throw Object.assign(new Error("invalid runner authorization"), { statusCode: 401 });

  const timestamp = String(req.headers["x-operly-timestamp"] || "").trim();
  const nonce = String(req.headers["x-operly-nonce"] || "").trim();
  if (!/^\d{10,16}$/.test(timestamp) || !NONCE_RE.test(nonce)) {
    throw Object.assign(new Error("runner freshness proof is missing or invalid"), { statusCode: 401 });
  }
  const requestTime = Number(timestamp);
  const now = Date.now();
  if (!Number.isFinite(requestTime) || Math.abs(now - requestTime) > MAX_CLOCK_SKEW_MS) {
    throw Object.assign(new Error("runner request timestamp is outside the allowed window"), { statusCode: 401 });
  }

  const supplied = String(req.headers["x-operly-signature"] || "");
  const expected = hmac(canonical(req.method || "GET", pathname, timestamp, nonce, raw));
  if (!supplied || !safeEqual(supplied, expected)) throw Object.assign(new Error("invalid runner request signature"), { statusCode: 401 });

  pruneReplayNonces(now);
  if (replayNonces.has(nonce)) {
    throw Object.assign(new Error("runner request replay detected"), { statusCode: 409 });
  }
  if (replayNonces.size >= 50000) throw Object.assign(new Error("Runner replay capacity exhausted"), { statusCode: 503 });
  replayNonces.set(nonce, now + REPLAY_TTL_MS);
}

function sendJson(res, status, value, { signed = true } = {}) {
  const body = Buffer.from(JSON.stringify(value));
  if (body.length > MAX_RESPONSE_BYTES) return sendJson(res, 500, { detail: "runner response exceeded policy" }, { signed });
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Content-Length", String(body.length));
  res.setHeader("Cache-Control", "no-store");
  if (signed && RUNNER_SIGNING_KEY && res.dzNonce) {
    // Bind the response to the authenticated request, including HTTP status.
    const signedBody = Buffer.concat([Buffer.from(res.dzNonce + "\n" + status + "\n"), body]);
    res.setHeader("X-Operly-Signature", hmac(signedBody));
  }
  res.end(body);
}

function cleanId(value) {
  const clean = String(value || "").trim();
  if (!SESSION_RE.test(clean)) throw Object.assign(new Error("invalid Computer runtime id"), { statusCode: 422 });
  return clean;
}

function cleanTool(value) {
  const clean = String(value || "").trim();
  if (!TOOL_RE.test(clean) || !TOOL_SET.has(clean)) throw Object.assign(new Error("unknown Computer tool"), { statusCode: 404 });
  return clean;
}

async function connect(runtimeId) {
  if (!ENVIRONMENT_ID) throw Object.assign(new Error("RAILWAY_ENVIRONMENT_ID is required"), { statusCode: 503 });
  const box = await Sandbox.connect(cleanId(runtimeId), { environmentId: ENVIRONMENT_ID });
  await box.refresh();
  return box;
}

function isExecProxyNotReady(error) {
  return String(error?.message || error) === EXEC_PROXY_NOT_READY;
}

async function bootstrapOperation(label, operation) {
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      if (!isExecProxyNotReady(error) || attempt >= 5) throw error;
      const delayMs = 400 * attempt;
      console.warn(`Agent Computer bootstrap ${label} waiting for exec proxy (attempt ${attempt}/5, ${delayMs}ms)`);
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  throw new Error(`Agent Computer bootstrap ${label} retries exhausted`);
}

async function writeHelper(box) {
  await bootstrapOperation("write-helper", () => box.files.write("/opt/operly-computer-tool.py", TOOL_HELPER, { mode: 0o555 }));
  await requiredBootstrapExec(box, "prepare-workspace", "mkdir -p /workspace/work /workspace/.operly/processes && chown -R operly:operly /workspace && install -d -m 0711 -o root -g root /opt/dz-computer-requests && chown root:root /opt/operly-computer-tool.py && chmod 0555 /opt/operly-computer-tool.py");
}

function requireExecSuccess(result, label) {
  const rawCode = result?.exitCode ?? result?.exit_code ?? result?.code;
  if (rawCode === undefined || rawCode === null) throw Object.assign(new Error("Computer bootstrap returned no exit status"), { statusCode: 503 });
  const exitCode = Number(rawCode);
  if (!Number.isFinite(exitCode) || exitCode !== 0) {
    throw Object.assign(
      new Error(`Agent Computer ${label} failed closed (exit ${String(rawCode)})`),
      { statusCode: 503 },
    );
  }
  return result;
}

async function requiredBootstrapExec(box, label, command) {
  const result = await bootstrapOperation(label, () => box.exec(command, { timeoutSec: 10 }));
  return requireExecSuccess(result, label);
}

async function harden(box, networkPolicy) {
  const rules = [
    {
      apply: "iptables -C OUTPUT -m owner --uid-owner 10001 -d 169.254.0.0/16 -j REJECT 2>/dev/null || iptables -A OUTPUT -m owner --uid-owner 10001 -d 169.254.0.0/16 -j REJECT",
      verify: "iptables -C OUTPUT -m owner --uid-owner 10001 -d 169.254.0.0/16 -j REJECT",
    },
    {
      apply: "ip6tables -C OUTPUT -m owner --uid-owner 10001 -d fe80::/10 -j REJECT 2>/dev/null || ip6tables -A OUTPUT -m owner --uid-owner 10001 -d fe80::/10 -j REJECT",
      verify: "ip6tables -C OUTPUT -m owner --uid-owner 10001 -d fe80::/10 -j REJECT",
    },
  ];
  if (networkPolicy === "off") {
    rules.push(
      {
        apply: "iptables -C OUTPUT -m owner --uid-owner 10001 ! -d 127.0.0.0/8 -j REJECT 2>/dev/null || iptables -A OUTPUT -m owner --uid-owner 10001 ! -d 127.0.0.0/8 -j REJECT",
        verify: "iptables -C OUTPUT -m owner --uid-owner 10001 ! -d 127.0.0.0/8 -j REJECT",
      },
      {
        apply: "ip6tables -C OUTPUT -m owner --uid-owner 10001 ! -d ::1/128 -j REJECT 2>/dev/null || ip6tables -A OUTPUT -m owner --uid-owner 10001 ! -d ::1/128 -j REJECT",
        verify: "ip6tables -C OUTPUT -m owner --uid-owner 10001 ! -d ::1/128 -j REJECT",
      },
    );
  }

  // Network isolation is a security boundary. Never swallow firewall failures:
  // apply every required rule, then independently verify that the kernel has it.
  for (const rule of rules) {
    await requiredBootstrapExec(box, "network-harden", rule.apply);
  }
  for (const rule of rules) {
    await requiredBootstrapExec(box, "network-verify", rule.verify);
  }
}

async function createSession(payload) {
  if (!ENVIRONMENT_ID) throw Object.assign(new Error("RAILWAY_ENVIRONMENT_ID is required"), { statusCode: 503 });
  const request = parseCreate(payload);
  const started = Date.now();

  // Build the content-addressed base image once and let all later Computer
  // sessions fork the Railway-cached template instead of building it in the
  // user's request path.
  await ensureComputerTemplateWarm();

  const options = {
    environmentId: ENVIRONMENT_ID,
    idleTimeoutMinutes: Math.max(1, Math.min(Math.ceil(request.ttlSeconds / 60), 360)),
    networkIsolation: "ISOLATED",
  };
  const box = await Sandbox.create(computerTemplate(), options);
  try {
    await writeHelper(box);
    const expiresAt = new Date(Date.now() + request.ttlSeconds * 1000).toISOString();
    const meta = Buffer.from(JSON.stringify({scope: request.scope, expiresAt,
      profile: request.profile, networkPolicy: request.networkPolicy}));
    const publicMeta = Buffer.from(JSON.stringify({profile: request.profile, networkPolicy: request.networkPolicy}));
    await bootstrapOperation("write-scope-meta", () => box.files.write(SCOPE_META, meta, { mode: 0o600 }));
    await bootstrapOperation("write-public-meta", () => box.files.write(PUBLIC_META, publicMeta, { mode: 0o444 }));
    await requiredBootstrapExec(box, "protect-session-meta",
      "chown root:root /opt/dz-computer-scope.json /opt/dz-computer-public.json && chmod 0600 /opt/dz-computer-scope.json && chmod 0444 /opt/dz-computer-public.json");
    await harden(box, request.networkPolicy);
    console.log(`Agent Computer session ${String(box.id || "").slice(0, 24)} ready in ${Date.now() - started}ms`);
    return {
      id: String(box.id || ""), session_id: String(box.id || ""), state: "active",
      isolation: "railway_sandbox_vm_v2", provider: "railway-sandbox",
      profile: request.profile, network_policy: request.networkPolicy, private_network: false, tools: TOOL_IDS, expires_at: expiresAt,
    };
  } catch (error) {
    try { await box.destroy(); } catch {}
    throw error;
  }
}

async function scopedBox(runtimeId, scope, allowExpired = false) {
  const box = await connect(runtimeId);
  let meta;
  try {
    const bytes = Buffer.from(await box.files.read(SCOPE_META, { format: "bytes" }));
    meta = JSON.parse(bytes.toString("utf8"));
  } catch {
    throw Object.assign(new Error("Computer scope unavailable"), { statusCode: 403 });
  }
  verifyScope(meta, scope, {allowExpired});
  return {box, meta};
}

async function statusSession(runtimeId, scope) {
  const {box, meta} = await scopedBox(runtimeId, scope, true);
  const rawStatus = String(box.status || "UNKNOWN");
  const expired = Date.now() >= Date.parse(meta.expiresAt);
  return {
    id: cleanId(runtimeId), state: expired ? "expired" : rawStatus === "RUNNING" ? "active" : rawStatus.toLowerCase(),
    expired, expires_at: meta.expiresAt, isolation: "railway_sandbox_vm_v2",
    provider: "railway-sandbox", private_network: false,
    profile: meta.profile, network_policy: meta.networkPolicy, tools: TOOL_IDS,
  };
}

async function destroySession(runtimeId, scope) {
  const {box} = await scopedBox(runtimeId, scope, true);
  try { await box.destroy(); }
  catch { throw Object.assign(new Error("Computer destruction outcome unconfirmed"), {statusCode:503}); }
  return { id: cleanId(runtimeId), state: "stopped", destroyed: true };
}

function shellQuote(value) { return `'${String(value).replaceAll("'", `'"'"'`)}'`; }

async function executeTool(runtimeId, toolId, scope, rawArgs) {
  const {box} = await scopedBox(runtimeId, scope);
  if (String(box.status || "") !== "RUNNING") throw Object.assign(new Error("Computer runtime is not running"), { statusCode: 409 });
  const tool = cleanTool(toolId);
  const args = parseToolArguments(tool, rawArgs);
  const requestId = crypto.randomUUID();
  const requestPath = `${REQUESTS}/${requestId}.json`;
  const raw = Buffer.from(JSON.stringify(args && typeof args === "object" ? args : {}));
  if (raw.length > MAX_REQUEST_BYTES) throw Object.assign(new Error("tool arguments exceed policy"), { statusCode: 413 });
  // Root-owned directory prevents untrusted symlink/replacement races.
  await box.files.write(requestPath, raw, { mode: 0o440 });
  await requiredBootstrapExec(box, "protect-tool-request", `chown root:operly ${shellQuote(requestPath)} && chmod 0440 ${shellQuote(requestPath)}`);
  const requestedTimeout = Number(args?.timeout_seconds || 30);
  const timeoutSec = Math.max(20, Math.min(requestedTimeout + 15, 75));
  let result;
  try {
    result = await box.exec(
      `su -s /bin/bash operly -c ${shellQuote(`${PYTHON} /opt/operly-computer-tool.py ${tool} ${requestPath}`)}`,
      { cwd: WORKSPACE, timeoutSec },
    );
  } finally {
    try { await box.exec(`rm -f ${shellQuote(requestPath)}`, { timeoutSec: 5 }); } catch {}
  }
  const stdout = String(result.stdout || "").trim();
  let packet;
  try { packet = JSON.parse(stdout); }
  catch { throw Object.assign(new Error("Computer sandbox returned invalid tool output"), { statusCode: 502 }); }
  if (!packet || typeof packet !== "object") throw Object.assign(new Error("invalid Computer tool response"), { statusCode: 502 });
  if (!packet.ok) {
    return {
      runtime_state: "active", ok: false,
      error: String(packet.error || "Computer tool failed"), error_type: String(packet.error_type || "ToolError"),
      runner_exit_code: result.exitCode, runner_stderr: String(result.stderr || "").slice(-12000),
    };
  }
  return { runtime_state: "active", ok: true, ...packet.result };
}

function parseJson(raw) {
  if (!raw.length) return {};
  try {
    const value = JSON.parse(raw.toString("utf8"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    throw Object.assign(new Error("invalid JSON"), { statusCode: 400 });
  }
}

const server = http.createServer(async (req, res) => {
  let pathname = "/";
  try { pathname = new URL(req.url || "/", "http://runner.invalid").pathname; } catch {}
  if (pathname === "/health" && req.method === "GET") {
    return sendJson(res, 200, {
      ok: true,
      service: "dragonzpyder-sandbox-runner",
      protocol: "scoped-v2",
      computer_runtime: true,
      isolation: "railway-sandbox",
      private_network_default: false,
      replay_protection: true,
      split_authentication_secrets: true,
      tools: TOOL_IDS.length,
      computer_template: templateWarmStatus(),
    }, { signed: false });
  }
  if (!pathname.startsWith("/v2/computer/")) return sendJson(res, 404, { detail: "Not found" }, { signed: false });
  try {
    const raw = await readBody(req);
    authenticate(req, pathname, raw);
    res.dzNonce = String(req.headers["x-operly-nonce"]).trim();
    const payload = parseJson(raw);
    if (pathname === "/v2/computer/sessions" && req.method === "POST") return sendJson(res, 201, await createSession(payload));
    const statusMatch = pathname.match(/^\/v2\/computer\/sessions\/([^/]+)\/status$/);
    if (statusMatch && req.method === "POST") return sendJson(res, 200, await statusSession(statusMatch[1], payload.scope));
    const destroyMatch = pathname.match(/^\/v2\/computer\/sessions\/([^/]+)\/destroy$/);
    if (destroyMatch && req.method === "POST") return sendJson(res, 200, await destroySession(destroyMatch[1], payload.scope));
    const toolMatch = pathname.match(/^\/v2\/computer\/sessions\/([^/]+)\/tools\/([^/]+)$/);
    if (toolMatch && req.method === "POST") return sendJson(res, 200, await executeTool(toolMatch[1], decodeURIComponent(toolMatch[2]), payload.scope, payload.arguments));
    return sendJson(res, 404, { detail: "Computer endpoint not found" });
  } catch (error) {
    const suppliedStatus = Number(error?.statusCode || 503);
    const status = Number.isInteger(suppliedStatus) && suppliedStatus >= 400 && suppliedStatus <= 599
      ? suppliedStatus : 503;
    const safeMessage = status === 403 ? "Computer scope rejected" :
      status === 410 ? "Computer session expired" :
      status === 409 ? "Computer request conflict or replay" :
      status === 422 ? "Computer request rejected" : "Sandbox runner operation failed";
    console.error(`Scoped sandbox request failed status=${status}`);
    return sendJson(res, status, { detail: safeMessage });
  }
});

if (!RUNNER_TOKEN) { console.error("DRAGONZPYDER_RUNNER_TOKEN is required"); process.exit(1); }
if (!RUNNER_SIGNING_KEY) { console.error("DRAGONZPYDER_RUNNER_SIGNING_KEY is required"); process.exit(1); }
if (safeEqual(RUNNER_TOKEN, RUNNER_SIGNING_KEY)) { console.error("DRAGONZPYDER_RUNNER_TOKEN and DRAGONZPYDER_RUNNER_SIGNING_KEY must be different"); process.exit(1); }
if (!ENVIRONMENT_ID) { console.error("RAILWAY_ENVIRONMENT_ID is required"); process.exit(1); }
server.listen(PORT, "0.0.0.0", () => {
  console.log(`DragonZpyder Sandbox Runner listening on :${PORT}`);
  void ensureComputerTemplateWarm().catch(() => {});
});
