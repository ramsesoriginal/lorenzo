// The web design adds class names to apps/brand (web-classes.json). An app that loads the brand
// and already defines one of them in its own stylesheet would be restyled without asking. This
// test fails on that, and on a listed class the brand does not define (so the list cannot rot).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const brand = join(dirname(fileURLToPath(import.meta.url)), "..");
const apps = join(brand, "..");
const { classes, allowed } = JSON.parse(
  readFileSync(join(brand, "web-classes.json"), "utf8"),
);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    // `branding` is the copy of this very package that an app's build makes (public/branding).
    if (
      [
        "node_modules",
        "dist",
        ".astro",
        "test-results",
        "build",
        "branding",
      ].includes(name)
    )
      continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (p.endsWith(".css")) out.push(p);
  }
  return out;
}

function classesIn(css) {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const found = new Set();
  for (const m of stripped.matchAll(/\.(-?[_a-zA-Z][-\w]*)/g)) found.add(m[1]);
  return found;
}

test("every listed class is defined by the brand", () => {
  const own = new Set();
  for (const f of ["components.css", "layout.css", "motion.css"]) {
    for (const c of classesIn(readFileSync(join(brand, f), "utf8"))) own.add(c);
  }
  const missing = classes.filter((c) => !own.has(c));
  assert.deepEqual(
    missing,
    [],
    `listed but not defined in apps/brand: ${missing.join(", ")}`,
  );
});

test("no other app defines a class the web design added to the brand", () => {
  const clashes = [];
  for (const app of readdirSync(apps)) {
    if (app === "brand" || app in allowed) continue;
    const dir = join(apps, app);
    if (!statSync(dir).isDirectory() || !existsSync(dir)) continue;
    for (const file of walk(dir)) {
      const defined = classesIn(readFileSync(file, "utf8"));
      for (const c of classes)
        if (defined.has(c))
          clashes.push(`${file.slice(apps.length + 1)}: .${c}`);
    }
  }
  assert.deepEqual(
    clashes,
    [],
    `defined in another app too:\n${clashes.join("\n")}`,
  );
});

// UI-H H2 (ADR 0528): an app does not restate a brand class as a rule of its own. A bare
// `.class` or `.class:state` rule in an app's stylesheet repeats or fights what the brand draws;
// what an app adds is scoped (`.page .btn`, `.my-thing`). Bench draws its own page and is left out.
function brandClasses() {
  const own = new Set();
  for (const f of ["components.css", "layout.css", "base.css", "motion.css"]) {
    for (const c of classesIn(readFileSync(join(brand, f), "utf8"))) own.add(c);
  }
  return own;
}

function bareRules(css) {
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  for (const m of stripped.matchAll(/([^{}@;]+)\{/g)) {
    // A rule that groups the class with others adds to a list (a touch height, say); only a
    // rule that is the class alone restates it.
    const sel = m[1].trim();
    const bare = sel.match(
      /^\.(-?[_a-zA-Z][-\w]*)(?::[-\w]+(?:\([^)]*\))?)*$/,
    );
    if (bare) out.push({ sel, cls: bare[1] });
  }
  return out;
}

test("no app restates a brand class as a rule of its own", () => {
  const own = brandClasses();
  const restated = [];
  for (const app of readdirSync(apps)) {
    if (["brand", "bench", "legal"].includes(app) || app in allowed) continue;
    const dir = join(apps, app);
    if (!statSync(dir).isDirectory()) continue;
    for (const file of walk(dir)) {
      for (const { sel, cls } of bareRules(readFileSync(file, "utf8")))
        if (own.has(cls)) restated.push(`${file.slice(apps.length + 1)}: ${sel}`);
    }
  }
  assert.deepEqual(
    [...new Set(restated)],
    [],
    `a brand class restated in an app:\n${[...new Set(restated)].join("\n")}`,
  );
});
