/**
 * Cloudflare Worker: static UI + thin edge API.
 *
 * Cloudflare Workers cannot run the Python/FastAPI service, so this worker:
 *   - serves the SPA from [assets];
 *   - answers /api/health itself;
 *   - reverse-proxies every other /api/* request to API_ORIGIN (Zeabur).
 *
 * Optional: if a D1 binding named DB exists and EDGE_READS="d1", /api/runs
 * can be served directly from D1 (read-only). Write endpoints always proxy.
 */

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

async function d1Runs(env) {
  const { results } = await env.DB.prepare(
    `SELECT r.run_id, r.category, r.created_at, r.stats_json
       FROM runs r ORDER BY r.created_at DESC LIMIT 50`
  ).all();
  const runs = (results || []).map((r) => {
    let stats = {};
    try { stats = JSON.parse(r.stats_json || "{}"); } catch (_) { /* ignore */ }
    return {
      run_id: r.run_id,
      category: r.category,
      created_at: r.created_at,
      items: stats.items || 0,
      atoms: stats.atoms || 0,
      extractor: stats.extractor || "",
      latest_for_category: false,
    };
  });
  return { runs };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/health") {
      return json({
        ok: true,
        edge: true,
        store: env.DB ? "d1" : "proxy",
        api_origin: env.API_ORIGIN || null,
      });
    }

    if (url.pathname.startsWith("/api/")) {
      if (url.pathname === "/api/runs" && env.DB && env.EDGE_READS === "d1") {
        try {
          return json(await d1Runs(env));
        } catch (err) {
          return json({ detail: `d1 read failed: ${err.message}` }, 502);
        }
      }
      if (!env.API_ORIGIN) {
        return json({ detail: "API_ORIGIN is not configured" }, 502);
      }
      const target = new URL(url.pathname + url.search, env.API_ORIGIN);
      const upstream = new Request(target.toString(), request);
      const response = await fetch(upstream);
      const out = new Response(response.body, response);
      out.headers.set("x-painradar-edge", "proxy");
      return out;
    }

    if (env.ASSETS) return env.ASSETS.fetch(request);
    return new Response("Not found", { status: 404 });
  },
};
