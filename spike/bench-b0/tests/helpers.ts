import { appendFileSync, mkdirSync } from "node:fs";
import type { APIRequestContext, Page } from "@playwright/test";

export const id = (i: number) => `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`;
export const row = (page: Page, i: number | string) => page.locator(`bench-row[data-id="${typeof i === "number" ? id(i) : i}"]`);
export const field = (page: Page, i: number | string, f: string) => row(page, i).locator(`input[data-field="${f}"]`);

export async function reset(request: APIRequestContext, n = 300) {
  await request.get(`/api/_test/reset?n=${n}`);
}
export async function open(page: Page, user = "u1", query = "") {
  await page.goto(`/?user=${user}${query}`);
  await page.waitForSelector("body[data-ready='1']");
}
export const serverLog = async (request: APIRequestContext) => (await request.get("/api/_test/log")).json();
export const serverEntries = async (request: APIRequestContext) => (await request.get("/api/_test/get")).json();
export const pass = (page: Page) => page.evaluate(() => (window as any).__bench.runner.pass());

export function record(name: string, data: unknown) {
  mkdirSync("findings", { recursive: true });
  appendFileSync("findings/findings.ndjson", `${JSON.stringify({ name, ...((data as object) ?? {}) })}\n`);
}
