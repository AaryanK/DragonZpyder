import { Sandbox } from "railway";

const originalCreate = Sandbox.create.bind(Sandbox);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const terminalStates = new Set(["FAILED", "STOPPED", "REMOVED", "DESTROYED", "DELETED"]);

async function waitUntilRunning(box, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs;
  let lastStatus = String(box?.status || "UNKNOWN").toUpperCase();
  let refreshError = null;

  while (Date.now() < deadline) {
    try {
      await box.refresh();
      refreshError = null;
      lastStatus = String(box.status || "UNKNOWN").toUpperCase();
      if (lastStatus === "RUNNING") return box;
      if (terminalStates.has(lastStatus)) {
        throw new Error(`Sandbox entered terminal state ${lastStatus} before becoming ready`);
      }
    } catch (error) {
      refreshError = error;
      if (terminalStates.has(lastStatus)) throw error;
    }
    await sleep(300);
  }

  const detail = refreshError ? `; last refresh error: ${String(refreshError?.message || refreshError).slice(0, 300)}` : "";
  throw Object.assign(
    new Error(`Sandbox did not reach RUNNING before readiness deadline (last status: ${lastStatus})${detail}`),
    { statusCode: 503 },
  );
}

Sandbox.create = async (...args) => {
  const box = await originalCreate(...args);
  try { return await waitUntilRunning(box); }
  catch (error) { try { await box.destroy(); } catch {} throw error; }
};

await import("./server.mjs");
