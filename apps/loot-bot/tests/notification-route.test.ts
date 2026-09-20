import type http from "node:http";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Config } from "../src/config.js";
import { createNotificationDeliveryRoute } from "../src/notification-route.js";

const SERVICE_ACCOUNT = "scheduler@proj.iam.gserviceaccount.com";
const DELIVERY_URL = "https://bot.example.com/internal/deliver-notifications";

const REPORT = { users: 3, skippedUsers: 1, delivered: 4, undelivered: 1, failed: 0 };

function configWith(over: Partial<Config> = {}): Config {
  return {
    notificationSchedulerServiceAccount: SERVICE_ACCOUNT,
    notificationDeliveryUrl: DELIVERY_URL,
    ...over,
  } as Config;
}

function fakeRequest(method = "POST", authorization?: string) {
  return { method, headers: { authorization } } as unknown as http.IncomingMessage;
}

function fakeResponse() {
  const captured: { status?: number; headers?: Record<string, string>; body?: string } = {};
  const res = {
    writeHead: vi.fn((status: number, headers: Record<string, string>) => {
      captured.status = status;
      captured.headers = headers;
      return res;
    }),
    end: vi.fn((body: string) => {
      captured.body = body;
    }),
  };
  return { res: res as unknown as http.ServerResponse, captured };
}

const url = new URL("http://localhost/internal/deliver-notifications");
const warn = vi.fn();
const logger = { warn, info: vi.fn(), error: vi.fn() } as never;

describe("the notification delivery route", () => {
  const run = vi.fn();
  const verify = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    run.mockResolvedValue(REPORT);
    verify.mockResolvedValue({ ok: true });
  });

  function route(config = configWith()) {
    return createNotificationDeliveryRoute({ config, logger, run, verify });
  }

  it("is a plain 404 - as if it didn't exist - when the bridge isn't configured", async () => {
    const { res, captured } = fakeResponse();

    await route(configWith({ notificationSchedulerServiceAccount: undefined }))(
      fakeRequest("POST", "Bearer x"),
      res,
      url,
    );

    expect(captured.status).toBe(404);
    expect(verify).not.toHaveBeenCalled();
    expect(run).not.toHaveBeenCalled();
  });

  it("only accepts POST, as Cloud Scheduler sends", async () => {
    const { res, captured } = fakeResponse();

    await route()(fakeRequest("GET", "Bearer x"), res, url);

    expect(captured.status).toBe(405);
    expect(captured.headers?.allow).toBe("POST");
    expect(run).not.toHaveBeenCalled();
  });

  it("verifies the token against this route's own URL and the expected service account", async () => {
    const { res } = fakeResponse();

    await route()(fakeRequest("POST", "Bearer tok"), res, url);

    expect(verify).toHaveBeenCalledWith("Bearer tok", {
      audience: DELIVERY_URL,
      serviceAccountEmail: SERVICE_ACCOUNT,
    });
  });

  it("rejects an unauthenticated request with a bare 401, and runs nothing", async () => {
    verify.mockResolvedValue({ ok: false, reason: "token is for a different account" });
    const { res, captured } = fakeResponse();

    await route()(fakeRequest("POST", "Bearer tok"), res, url);

    expect(captured.status).toBe(401);
    expect(captured.body).toBe("Unauthorized");
    expect(run).not.toHaveBeenCalled();
  });

  it("gives a prober nothing: the response never reveals why it was refused", async () => {
    verify.mockResolvedValue({ ok: false, reason: "token is for a different account" });
    const { res, captured } = fakeResponse();

    await route()(fakeRequest("POST", "Bearer tok"), res, url);

    expect(captured.body).not.toContain("account");
    expect(warn).toHaveBeenCalledWith(
      { reason: "token is for a different account" },
      expect.any(String),
    );
  });

  it("runs the bridge for an authenticated request and returns its tally as JSON", async () => {
    const { res, captured } = fakeResponse();

    await route()(fakeRequest("POST", "Bearer tok"), res, url);

    expect(run).toHaveBeenCalledTimes(1);
    expect(captured.status).toBe(200);
    expect(captured.headers?.["content-type"]).toBe("application/json");
    expect(JSON.parse(captured.body ?? "")).toEqual(REPORT);
  });

  it("lets a failing run surface, so the server's own handler answers 500 and Cloud Scheduler retries", async () => {
    run.mockRejectedValue(new Error("boom"));
    const { res } = fakeResponse();

    await expect(route()(fakeRequest("POST", "Bearer tok"), res, url)).rejects.toThrow("boom");
  });
});
