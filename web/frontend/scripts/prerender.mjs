import React from "react";
import { renderToString } from "react-dom/server";
import { createServer } from "vite";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "../dist");
// Vite transforms JSX for SSR using the same React source as the browser.
// The result is static content in the output, NOT separate source templates.
const vite = await createServer({
  configFile: resolve(root, "vite.config.js"),
  server: { middlewareMode: true, hmr: false },
  // Prerender needs server-side markup only. Avoid background dependency scanning
  // after the ephemeral Vite server closes when rich Markdown modules are imported.
  optimizeDeps: { noDiscovery: true, include: [] },
  appType: "custom",
  logLevel: "error",
});
try {
  const { Frontend } = await vite.ssrLoadModule("/src/pages.jsx");
  for (const [file, page] of [["index.html", "home"], ["app.html", "app"], ["account.html", "account"]]) {
    const path = resolve(dist, file);
    const shell = readFileSync(path, "utf8");
    if (!shell.includes('<div id="root"></div>')) {
      throw new Error(file + " missing the React root shell");
    }
    const markup = renderToString(React.createElement(Frontend, { page }));
    writeFileSync(path, shell.replace('<div id="root"></div>',
      '<div id="root">' + markup + "</div>"));
  }
} finally {
  await vite.close();
}
