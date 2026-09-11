import http from "node:http";
import type { Logger } from "pino";

export type RouteHandler = (
  req: http.IncomingMessage,
  res: http.ServerResponse,
  url: URL,
) => void | Promise<void>;

export type HttpServer = Readonly<{
  server: http.Server;
  listen: () => Promise<void>;
  close: () => Promise<void>;
}>;

/**
 * A bare node:http server, deliberately not a framework (Fastify/Express) -
 * this only ever needs a couple of routes (/healthz, /auth/callback), and a
 * framework's real value-adds (schema validation, plugin ecosystem) don't
 * engage at that scale. Mirrors apps/api/scripts/get_dev_token.py's own
 * precedent of using the plainest possible HTTP listener for a small OAuth
 * callback - see ADR 0029.
 *
 * Routes are matched on `url.pathname` only (no method routing, no path
 * params) - everything this app needs so far is a distinct GET path; revisit
 * if that stops being true.
 */
export function createHttpServer(
  routes: ReadonlyMap<string, RouteHandler>,
  options: { port: number; logger: Logger },
): HttpServer {
  const server = http.createServer((req, res) => {
    void handleRequest(req, res, routes, options.logger);
  });

  return {
    server,
    listen: () =>
      new Promise((resolve) => {
        server.listen(options.port, () => resolve());
      }),
    close: () =>
      new Promise((resolve, reject) => {
        server.close((err) => (err ? reject(err) : resolve()));
      }),
  };
}

async function handleRequest(
  req: http.IncomingMessage,
  res: http.ServerResponse,
  routes: ReadonlyMap<string, RouteHandler>,
  logger: Logger,
): Promise<void> {
  const url = new URL(req.url ?? "/", "http://localhost");
  const handler = routes.get(url.pathname);
  if (!handler) {
    res.writeHead(404, { "content-type": "text/plain" }).end("Not found");
    return;
  }
  try {
    await handler(req, res, url);
  } catch (error) {
    logger.error({ err: error, path: url.pathname }, "request handler failed");
    if (!res.headersSent) {
      res.writeHead(500, { "content-type": "text/plain" }).end("Internal error");
    }
  }
}

export const healthzRoute: RouteHandler = (_req, res) => {
  res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify({ status: "ok" }));
};
