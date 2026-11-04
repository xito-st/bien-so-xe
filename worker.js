// ==============================================================================
// Cloudflare Worker Reverse Proxy cho Hệ thống Quản lý Biển số xe
// ==============================================================================

const BACKEND_URL = "https://biensoxe-api.onrender.com";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. Chuyển tiếp toàn bộ API về Render Backend
    if (url.pathname.startsWith("/api/")) {
      const targetUrl = new URL(url.pathname + url.search, BACKEND_URL);

      const modifiedHeaders = new Headers(request.headers);
      modifiedHeaders.set("Host", "biensoxe-api.onrender.com");
      modifiedHeaders.set("X-Forwarded-Host", url.host);
      modifiedHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

      const hasBody = request.method !== "GET" && request.method !== "HEAD";
      const proxyRequest = new Request(targetUrl.toString(), {
        method: request.method,
        headers: modifiedHeaders,
        body: hasBody ? request.body : undefined,
        redirect: "manual",
      });

      return fetch(proxyRequest);
    }

    // 2. Phục vụ tài nguyên Frontend React tĩnh (SPA)
    const assetResponse = await env.ASSETS.fetch(request);
    if (assetResponse.status === 404) {
      // Fallback về index.html cho các route phía client (như /bao-cao, /lo-xa)
      return env.ASSETS.fetch(new Request(new URL("/", request.url), request));
    }
    return assetResponse;
  },
};
