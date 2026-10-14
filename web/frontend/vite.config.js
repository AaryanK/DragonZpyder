import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root,
  base: "/",
  publicDir: false,
  plugins: [react()],
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
