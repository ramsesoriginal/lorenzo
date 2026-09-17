import { afterEach, describe, expect, it } from "vitest";
import { type HttpServer, createHttpServer, healthzRoute } from "../src/http-server.js";
import { logger } from "../src/logger.js";

describe("createHttpServer", () => {
  let server: HttpServer | undefined;

  afterEach(async () => {
    await server?.close();
    server = undefined;
  });

  it("serves a registered route over a real HTTP request", async () => {
    server = createHttpServer(new Map([["/healthz", healthzRoute]]), { port: 0, logger });
    await server.listen();
    const address = server.server.address();
    if (address === null || typeof address === "string") throw new Error("expected an AddressInfo");

    const response = await fetch(`http://127.0.0.1:${address.port}/healthz`);
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "ok" });
  });

  it("404s an unregistered path", async () => {
    server = createHttpServer(new Map([["/healthz", healthzRoute]]), { port: 0, logger });
    await server.listen();
    const address = server.server.address();
    if (address === null || typeof address === "string") throw new Error("expected an AddressInfo");

    const response = await fetch(`http://127.0.0.1:${address.port}/nope`);
    expect(response.status).toBe(404);
  });

  it("500s and does not crash the server when a handler throws", async () => {
    server = createHttpServer(
      new Map([
        [
          "/boom",
          () => {
            throw new Error("boom");
          },
        ],
      ]),
      { port: 0, logger },
    );
    await server.listen();
    const address = server.server.address();
    if (address === null || typeof address === "string") throw new Error("expected an AddressInfo");

    const response = await fetch(`http://127.0.0.1:${address.port}/boom`);
    expect(response.status).toBe(500);
  });
});
