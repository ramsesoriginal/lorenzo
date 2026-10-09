// Stub of the API for the spike: just enough of W1 (checked writes), W2 (client ids, replay)
// and W3 (cursor-paged, gzipped export with a revision ETag), plus test controls under /api/_test.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import { extname, join } from "node:path";

const dist = new URL("../dist/", import.meta.url).pathname;
const html = new URL("../index.html", import.meta.url).pathname;
let entries = new Map();
let revision = 0;
let log = [];
let dropNextWriteResponse = false;

const seed = (n) => {
  entries = new Map();
  revision = 1;
  log = [];
  for (let i = 0; i < n; i++) {
    const id = `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`;
    entries.set(id, { id, name: `Entry ${i}`, stats: { a: i, b: i * 2, c: null }, version: "v1" });
  }
};
seed(300);

const send = (res, status, body, headers = {}, req) => {
  const raw = body === undefined ? "" : JSON.stringify(body);
  const h = { "content-type": "application/json", ...headers };
  if (req?.headers["accept-encoding"]?.includes("gzip") && raw.length > 1024) {
    res.writeHead(status, { ...h, "content-encoding": "gzip" });
    return res.end(gzipSync(raw));
  }
  res.writeHead(status, h);
  res.end(raw);
};
const readBody = (req) => new Promise((ok) => { let s = ""; req.on("data", (d) => (s += d)); req.on("end", () => ok(s ? JSON.parse(s) : null)); });
const bump = (e) => { e.version = `v${Number(e.version.slice(1)) + 1}`; revision++; };

createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const p = url.pathname;
  try {
    if (!p.startsWith("/api/")) {
      if (p === "/" || p === "/index.html") {
        const body = await readFile(html);
        return res.writeHead(200, { "content-type": "text/html" }).end(body);
      }
      const type = { ".js": "text/javascript", ".map": "application/json" }[extname(p)] ?? "text/plain";
      const body = await readFile(join(dist, p)).catch(() => null);
      if (!body) return res.writeHead(404).end();
      return res.writeHead(200, { "content-type": type }).end(body);
    }
    if (p === "/api/_test/reset") { seed(Number(url.searchParams.get("n") ?? 300)); return send(res, 200, { ok: true }); }
    if (p === "/api/_test/log") return send(res, 200, { log, revision, count: entries.size });
    if (p === "/api/_test/get") return send(res, 200, [...entries.values()]);
    if (p === "/api/_test/drop-next") { dropNextWriteResponse = true; return send(res, 200, {}); }
    if (p === "/api/_test/mutate") {
      const b = await readBody(req);
      const e = entries.get(b.id);
      if (b.field === "name") e.name = b.value; else e.stats[b.field] = b.value;
      bump(e);
      return send(res, 200, e);
    }
    if (p === "/api/export") {
      const cursor = Number(url.searchParams.get("cursor") ?? 0);
      const size = Number(url.searchParams.get("size") ?? 100);
      const etag = `"rev-${revision}"`;
      if (cursor === 0 && req.headers["if-none-match"] === etag) return res.writeHead(304, { etag }).end();
      const all = [...entries.values()];
      const page = all.slice(cursor, cursor + size);
      const next = cursor + size < all.length ? cursor + size : null;
      return send(res, 200, { entries: page, next }, { etag }, req);
    }
    const m = p.match(/^\/api\/entries(?:\/([\w-]+))?$/);
    if (m) {
      const id = m[1];
      if (req.method === "GET" && id) {
        const e = entries.get(id);
        return e ? send(res, 200, e) : send(res, 404, { detail: "no such entry" });
      }
      if (req.method === "POST") {
        const b = await readBody(req);
        const existing = entries.get(b.id);
        if (existing) { log.push(`POST ${b.id} replay`); return send(res, 200, existing); }
        const e = { id: b.id, name: b.name, stats: b.stats, version: "v1" };
        entries.set(b.id, e); revision++;
        log.push(`POST ${b.id} created`);
        if (dropNextWriteResponse) { dropNextWriteResponse = false; return req.socket.destroy(); }
        return send(res, 201, e);
      }
      if (req.method === "PATCH" && id) {
        const e = entries.get(id);
        if (!e) return send(res, 404, {});
        if (req.headers["if-match"] !== e.version) return send(res, 412, e);
        const b = await readBody(req);
        if (b.field === "name") e.name = b.value; else e.stats[b.field] = b.value;
        bump(e);
        log.push(`PATCH ${id} ${b.field}=${b.value}`);
        return send(res, 200, e);
      }
    }
    send(res, 404, { detail: "not found" });
  } catch (err) {
    if (!res.headersSent) send(res, 500, { detail: String(err) });
  }
}).listen(Number(process.env.PORT ?? 4173), "127.0.0.1", () => console.log("stub on", process.env.PORT ?? 4173));
