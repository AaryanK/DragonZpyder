// Legacy direct-to-model chat has been retired.
// DragonZpyder's web product now lives at /app.html and sends requests through
// the same-origin /api/* bridge into Operly's governed Personal runtime.
if (location.pathname.endsWith("/chat.html")) {
  location.replace("/app.html" + location.search + location.hash);
}
