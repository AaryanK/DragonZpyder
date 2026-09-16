const topbar = document.getElementById("topbar");
const runtimeDot = document.getElementById("runtime-dot");
const runtimeText = document.getElementById("runtime-text");
const year = document.getElementById("year");

if (year) year.textContent = String(new Date().getFullYear());

addEventListener("scroll", () => {
  topbar?.classList.toggle("scrolled", scrollY > 12);
}, { passive: true });

async function checkRuntime() {
  if (!runtimeDot || !runtimeText) return;
  try {
    const response = await fetch("/api/health", {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    runtimeDot.classList.add("online");
    runtimeDot.classList.remove("error");
    runtimeText.textContent = "Operly runtime reachable";
  } catch {
    runtimeDot.classList.remove("online");
    runtimeDot.classList.add("error");
    runtimeText.textContent = "Runtime status unavailable";
  }
}

checkRuntime();
