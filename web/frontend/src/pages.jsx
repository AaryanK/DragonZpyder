import React, { useEffect, useMemo, useState } from "react";
import { HomeTemplate } from "./HomeTemplate.jsx";
import { PersonalTemplate } from "./PersonalTemplate.jsx";
import { AccountTemplate } from "./AccountTemplate.jsx";
import { RuntimeContext } from "./runtime.jsx";
import { AdminPage } from "./AdminPage.jsx";

// Each page's markup is real React JSX. The old standalone HTML templates
// are no longer imported, parsed, or used by the browser.
function HomePage() {
  const [status, setStatus] = useState("checking");
  const [year, setYear] = useState(2026);
  useEffect(() => {
    setYear(new Date().getFullYear());
    const onScroll = () =>
      document.getElementById("topbar")?.classList.toggle("scrolled", window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    const controller = new AbortController();
    fetch("/api/health", {
      headers: { accept: "application/json" }, credentials: "same-origin",
      cache: "no-store", signal: controller.signal,
    })
      .then(response => {
        if (!response.ok) throw new Error("Runtime unavailable");
        setStatus("online");
      })
      .catch(error => {
        if (error.name !== "AbortError") setStatus("error");
      });
    return () => { controller.abort(); window.removeEventListener("scroll", onScroll); };
  }, []);
  const context = useMemo(() => ({ status, year }), [status, year]);
  return <RuntimeContext.Provider value={context}><HomeTemplate /></RuntimeContext.Provider>;
}

function CompatibilityAdapters({ page }) {
  useEffect(() => {
    // Auth, chat, approvals, voice and Mesh still have carefully permissioned
    // imperative controllers. Initialise only AFTER the JSX page has mounted,
    // then migrate each feature to dedicated hooks/components in later changes.
    const initialise = async () => {
      if (page === "app") {
        await import("../../app.js");
        await import("../../companion.js");
        await import("../../dictation.js");
        await import("../../mesh.js");
        await import("../../mesh-picker.js");
      } else if (page === "account") {
        await import("../../account.js");
      }
    };
    initialise().catch(error => console.error("DragonZpyder initialisation failed", error));
  }, [page]);
  return null;
}

export function Frontend({ page }) {
  if (page === "admin") return <AdminPage />;
  if (page === "home") return <HomePage />;
  if (page === "app") return <><PersonalTemplate /><CompatibilityAdapters page="app" /></>;
  if (page === "account") return <><AccountTemplate /><CompatibilityAdapters page="account" /></>;
  throw new Error("Unknown frontend page");
}
