import "./grid";
import type { BenchGrid } from "./grid";
import { Model } from "./model";
import { Runner } from "./runner";
import { Store } from "./store";
import type { Entry } from "./types";

const params = new URLSearchParams(location.search);
const user = params.get("user") ?? "u1";

async function fetchExport(store: Store): Promise<{ entries: Entry[]; notModified: boolean; bytes: number }> {
  const known = await store.getMeta<string>("etag");
  const entries: Entry[] = [];
  let cursor = 0;
  let bytes = 0;
  let etag = "";
  for (;;) {
    const r = await fetch(`/api/export?cursor=${cursor}&size=100`, { headers: cursor === 0 && known ? { "if-none-match": known } : {} });
    if (r.status === 304) return { entries: [], notModified: true, bytes };
    const body = await r.text();
    bytes += body.length;
    const page = JSON.parse(body) as { entries: Entry[]; next: number | null };
    if (cursor === 0) etag = r.headers.get("etag") ?? "";
    entries.push(...page.entries);
    if (page.next === null) break;
    cursor = page.next;
  }
  await store.setMeta("etag", etag);
  return { entries, notModified: false, bytes };
}

async function boot() {
  const store = await Store.open(user);
  const model = new Model(store);
  let exported: { notModified: boolean; bytes: number; ms: number } | { offline: true };
  try {
    const t0 = performance.now();
    const x = await fetchExport(store);
    if (!x.notModified) {
      // names-first/bodies-lazily is not spiked; here the whole export replaces the mirror
      await store.replaceMirror(x.entries);
    }
    exported = { notModified: x.notModified, bytes: x.bytes, ms: performance.now() - t0 };
  } catch {
    exported = { offline: true }; // API unreachable: the app still opens, from the store
    model.online.set(false);
  }
  const t1 = performance.now();
  await model.load();
  const grid = document.querySelector("bench-grid") as BenchGrid;
  const runner = new Runner(model);
  runner.autoSync = params.get("auto") === "1";
  grid.model = model;
  grid.runner = runner;
  const t2 = performance.now();
  grid.render();
  const renderMs = performance.now() - t2;
  runner.start();

  document.querySelector("#sync")!.addEventListener("click", () => void runner.pass());
  document.querySelector("#new")!.addEventListener("click", () => {
    model.create(`New entry ${Date.now() % 100000}`);
    grid.sync();
  });
  model.channel.addEventListener("message", () => grid.sync());
  window.addEventListener("offline", () => { model.online.set(false); model.refreshAll(); });
  window.addEventListener("online", () => { model.online.set(true); model.refreshAll(); });

  (window as unknown as Record<string, unknown>).__bench = {
    model, runner, store, grid, exported, loadMs: t2 - t1, renderMs,
    syncGrid: () => grid.sync(),
  };
  document.body.dataset.ready = "1";
}
void boot();
