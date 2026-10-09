import { gzipSync } from "node:zlib";
import { expect, test } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { names, simulate, useCorpus } from "../scripts/gen.mjs";
import { open, record } from "./helpers";

// real English sentences from this repository's own ADRs (technical prose, so a fair, not a flattering, ratio)
const adrDir = join(process.cwd(), "../../docs/adr");
const SENTENCES = readdirSync(adrDir)
  .filter((f) => f.endsWith(".md"))
  .flatMap((f) => readFileSync(join(adrDir, f), "utf8").replace(/```[\s\S]*?```/g, " ").split(/(?<=[.!?])\s+/))
  .map((s) => s.replace(/\s+/g, " ").trim())
  .filter((s) => s.length > 40 && s.length < 300 && !/[|`]/.test(s));

const kb = (n: number) => Math.round(n / 100) / 10;
const sizes = (value: unknown) => {
  const raw = Buffer.byteLength(JSON.stringify(value));
  return { rawKB: kb(raw), gzipKB: kb(gzipSync(JSON.stringify(value)).length), ratio: Math.round((raw / gzipSync(JSON.stringify(value)).length) * 10) / 10 };
};

for (const n of [700, 7000]) {
  test(`export of ${n} simulated entries: size and what the device spends on it`, async ({ page }) => {
    test.setTimeout(120_000);
    const entries = simulate(n);
    const full = sizes(entries);
    const list = sizes(names(entries));
    const gmOnly = entries.filter((e: any) => e.information.some((i: any) => i.visibility === "gm")).length;
    const pageOf100 = sizes(entries.slice(0, 100));
    // sensitivity: descriptions twice as long (a book-like repository), and the same text with no compressibility help
    const doubled = sizes(simulate(n, { descChars: 700, gmChars: 1800 }));
    useCorpus(SENTENCES);
    const realProse = sizes(simulate(n));
    useCorpus(null);

    await open(page, `size${n}`);
    const json = JSON.stringify(entries);
    const device = await page.evaluate(async (payload: string) => {
      const t0 = performance.now();
      const parsed = JSON.parse(payload) as { id: string }[];
      const parseMs = performance.now() - t0;
      const db = await new Promise<IDBDatabase>((res, rej) => {
        const r = indexedDB.open(`size-test-${Math.random()}`, 1);
        r.onupgradeneeded = () => r.result.createObjectStore("m", { keyPath: "id" });
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
      });
      const t1 = performance.now();
      await new Promise<void>((res, rej) => {
        const t = db.transaction("m", "readwrite");
        for (const e of parsed) t.objectStore("m").put(e);
        t.oncomplete = () => res();
        t.onerror = () => rej(t.error);
      });
      const writeMs = performance.now() - t1;
      const t2 = performance.now();
      const back = await new Promise<unknown[]>((res) => {
        const r = db.transaction("m").objectStore("m").getAll();
        r.onsuccess = () => res(r.result);
      });
      const readMs = performance.now() - t2;
      const est = await navigator.storage.estimate();
      db.close();
      return { parseMs, writeMs, readMs, count: back.length, usageKB: Math.round((est.usage ?? 0) / 1e3), quotaMB: Math.round((est.quota ?? 0) / 1e6) };
    }, json);
    expect(device.count).toBe(n);

    // transfer time of the gzipped export at three link speeds (arithmetic, not a measurement)
    const bits = full.gzipKB * 1000 * 8;
    const secs = (bps: number) => Math.round((bits / bps) * 10) / 10;
    record(`export.${n}`, {
      entries: n, gmNotes: gmOnly, full, namesOnly: list, pageOf100, doubledText: doubled, realProseSentences: SENTENCES.length, realProse,
      device: { ...device, parseMs: Math.round(device.parseMs), writeMs: Math.round(device.writeMs), readMs: Math.round(device.readMs) },
      transferSeconds: { slow3g_400kbps: secs(4e5), fourG_5Mbps: secs(5e6), wifi_50Mbps: secs(5e7) },
    });
  });
}
