import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import parse from "html-react-parser";
import homeHTML from "../../index.html?raw";
import appHTML from "../../app.html?raw";
import accountHTML from "../../account.html?raw";

// Keep the existing HTML/CSS templates as the canonical source of truth during
// migration. React renders their markup; the controllers for auth, chat and
// realtime voice remain as temporary adapters, loaded only after hydration.
const sources = { home: homeHTML, app: appHTML, account: accountHTML };
const bodies = Object.fromEntries(
  Object.entries(sources).map(([name, html]) => {
    const body = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i)?.[1];
    if (!body) throw new Error("Missing HTML body for " + name);
    return [name, body.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")];
  }),
);

const Runtime = createContext({ status: "checking", year: 2026 });
function StatusDot() {
  const { status } = useContext(Runtime);
  return (
    <span id="runtime-dot" className={status === "online" ? "online" : status === "error" ? "error" : ""}
      style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: "#858a81" }}
      aria-hidden="true" />
  );
}
function StatusText() {
  const { status } = useContext(Runtime);
  return <span id="runtime-text" aria-live="polite">
    {status === "online" ? "Operly runtime reachable" : status === "error" ? "Runtime status unavailable" : "Checking runtime…"}
  </span>;
}
function CopyrightYear() {
  const { year } = useContext(Runtime);
  return <span id="year">{year}</span>;
}

function PageMarkup({ page }) {
  const children = useMemo(
    () => parse(bodies[page], {
      replace(node) {
        if (page !== "home" || !node.attribs) return;
        if (node.attribs.id === "runtime-dot") return <StatusDot />;
        if (node.attribs.id === "runtime-text") return <StatusText />;
        if (node.attribs.id === "year") return <CopyrightYear />;
      },
    }),
    [page],
  );
  return <>{children}</>;
}

function HomePage() {
  const [status, setStatus] = useState("checking");
  const [year, setYear] = useState(2026);
  useEffect(() => {
    setYear(new Date().getFullYear());
    const onScroll = () => document.getElementById("topbar")?.classList.toggle("scrolled", window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    const controller = new AbortController();
    fetch("/api/health", { headers: { accept: "application/json" },
      credentials: "same-origin", cache: "no-store", signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error("Runtime unavailable");
        setStatus("online");
      })
      .catch(error => {
        if (error.name !== "AbortError") setStatus("error");
      });
    return () => { controller.abort(); window.removeEventListener("scroll", onScroll); };
  }, []);
  const state = useMemo(() => ({ status, year }), [status, year]);
  return <Runtime.Provider value={state}><PageMarkup page="home" /></Runtime.Provider>;
}

function LegacyAdapters({ page }) {
  useEffect(() => {
    // Existing auth/approval semantics are critical. Preserve them until each
    // feature has its own tested React hook instead of rewriting them blindly.
    const initialise = async () => {
      if (page === "app") {
        await import("../../app.js");
        await import("../../companion.js");
        await import("../../dictation.js");
        await import("../../mesh.js");
      } else if (page === "account") {
        await import("../../account.js");
      }
    };
    initialise().catch(error => console.error("DragonZpyder interface initialisation failed", error));
  }, [page]);
  return null;
}

export function Frontend({ page }) {
  if (page === "home") return <HomePage />;
  if (!["app", "account"].includes(page)) throw new Error("Unknown frontend page");
  return <><PageMarkup page={page} /><LegacyAdapters page={page} /></>;
}
