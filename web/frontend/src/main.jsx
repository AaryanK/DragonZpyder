import React from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { Frontend } from "./pages.jsx";

const el = document.getElementById("root");
const route = document.documentElement.dataset.page || (
  location.pathname.startsWith("/admin") ? "admin" :
  location.pathname.startsWith("/app") ? "app" :
  location.pathname.startsWith("/account") ? "account" : "home"
);

if (!el) {
  throw new Error("React mount point is missing from the page");
}

const view = <Frontend page={route} />;
// Each Vite entry includes the original template as HTML, so search engines,
// no-JS users, and slow networks retain fully rendered content.
if (el.hasChildNodes()) {
  hydrateRoot(el, view, {
    onRecoverableError(error) {
      console.error("DragonZpyder hydration recovered:", error.message);
    },
  });
} else {
  createRoot(el).render(view);
}
