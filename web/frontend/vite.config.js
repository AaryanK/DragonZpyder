import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));

// Match production's FastAPI clean routes when developing with Node/Vite.
function cleanPageRouteMiddleware(server) {
  server.middlewares.use((request, _response, next) => {
    if (request.method === "GET" || request.method === "HEAD") {
      const path = request.url || "";
      for (const [route, entry] of [["/app", "/app.html"], ["/account", "/account.html"]]) {
        if (path === route || path.startsWith(route + "?")) {
          request.url = entry + path.slice(route.length);
          break;
        }
      }
    }
    next();
  });
}
const cleanPageRoutes = {
  name: "dragonzpyder-clean-page-routes",
  configureServer: cleanPageRouteMiddleware,
  configurePreviewServer: cleanPageRouteMiddleware,
};

export default defineConfig({
  root,
  base: "/",
  publicDir: false,
  plugins: [react(), cleanPageRoutes],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/mesh": "http://127.0.0.1:8080",
      "/companion": "http://127.0.0.1:8080",
      "/internal": "http://127.0.0.1:8080",
    },
  },
  build: {
    outDir: resolve(root, "../dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        index: resolve(root, "index.html"),
        app: resolve(root, "app.html"),
        account: resolve(root, "account.html"),
      },
    },
  },
});
