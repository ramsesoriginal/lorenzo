import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// ADR 0439, and the privacy policy's sentence that the apps "load no fonts or scripts from third
// parties": a page's own markup and styles never pull a resource from another host. Links a person
// follows (`<a href>`) are fine; a script, image, frame, stylesheet, font, form target or CSS
// `url()` / `@import` at an absolute address is not. This is a source scan, the net that catches
// the usual way it breaks (a hosted font, a widget); the browser run in the pull request that
// introduced it checked the built apps' requests.
const root = fileURLToPath(new URL('../../../', import.meta.url));
const SKIP = new Set([
  'node_modules',
  'dist',
  '.astro',
  'public',
  'test',
  'tests',
  'e2e',
  'preview',
]);
const FILE = /\.(astro|ts|css|html)$/;
// A server, a bot and the native apps serve no page of their own, so nothing a person's browser loads.
const NOT_PAGES = new Set(['api', 'cli', 'loot-bot', 'inventory-mobile', 'inventory-ios']);

const EXTERNAL_RESOURCE = [
  /<(script|img|iframe|video|audio|source|embed|object|link)\b[^>]*\b(src|href|data)=["']https?:\/\//i,
  /url\(\s*["']?https?:\/\//i,
  /@import[^;]*https?:\/\//i,
  /<form\b[^>]*\baction=["']https?:\/\//i,
];

function* files(dir: string): Generator<string> {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (FILE.test(name) && !/\.(test|spec)\./.test(name)) yield path;
  }
}

describe('the pages of the apps', () => {
  it('pull no script, image, font, stylesheet or frame from another host', () => {
    const offenders: string[] = [];

    for (const group of ['apps', 'packages']) {
      for (const name of readdirSync(join(root, group))) {
        if (group === 'apps' && NOT_PAGES.has(name)) continue;
        const dir = join(root, group, name);
        for (const sub of ['src', '.']) {
          const scan = sub === 'src' ? join(dir, 'src') : dir;
          try {
            if (!statSync(scan).isDirectory()) continue;
          } catch {
            continue;
          }
          // Only the top level of a package outside src/ (the brand's stylesheets).
          const found =
            sub === 'src'
              ? [...files(scan)]
              : readdirSync(scan)
                  .filter((n) => /\.css$/.test(n))
                  .map((n) => join(scan, n));
          for (const path of found) {
            const text = readFileSync(path, 'utf8');
            if (EXTERNAL_RESOURCE.some((pattern) => pattern.test(text))) {
              offenders.push(relative(root, path).replaceAll('\\', '/'));
            }
          }
        }
      }
    }

    expect([...new Set(offenders)].sort()).toEqual([]);
  });
});
