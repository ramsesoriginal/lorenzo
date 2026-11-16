import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { STORAGE_KEYS } from '../src/lib/storage-keys';

// ADR 0439: a change that makes an app keep something in a browser has to pass through the
// policy. This finds every source file of the web apps and shared packages that touches browser
// storage and requires it to be listed in src/lib/storage-keys.ts, which the policy prints.
const root = fileURLToPath(new URL('../../../', import.meta.url));
const USES = /\b(localStorage|sessionStorage|indexedDB)\b/;
const SOURCE = /\.(ts|tsx|js|mjs|astro)$/;
const SKIP = new Set(['node_modules', 'dist', '.astro', 'public', 'test', 'tests', 'e2e']);

function* files(dir: string): Generator<string> {
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name)) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (SOURCE.test(name) && !/\.(test|spec)\./.test(name)) yield path;
  }
}

function filesUsingStorage(): string[] {
  const found: string[] = [];
  for (const group of ['apps', 'packages']) {
    for (const name of readdirSync(join(root, group))) {
      const src = join(root, group, name, 'src');
      try {
        if (!statSync(src).isDirectory()) continue;
      } catch {
        continue;
      }
      // A server, a bot or a native app has no browser storage of its own to declare here.
      if (name === 'api' || name === 'cli' || name === 'loot-bot' || name === 'legal') continue;
      for (const path of files(src)) {
        if (USES.test(readFileSync(path, 'utf8')))
          found.push(relative(root, path).replaceAll('\\', '/'));
      }
    }
  }
  return found.sort();
}

describe('the browser storage the policy lists', () => {
  const declared = STORAGE_KEYS.flatMap((entry) => entry.files).sort();

  it('names every source file that uses browser storage', () => {
    const undeclared = filesUsingStorage().filter((path) => !declared.includes(path));
    expect(
      undeclared,
      'These files use browser storage but are not in src/lib/storage-keys.ts. Add their keys there (the privacy policy prints that list).',
    ).toEqual([]);
  });

  it('lists no file that is gone or no longer uses storage', () => {
    const present = new Set(filesUsingStorage());
    expect(declared.filter((path) => !present.has(path))).toEqual([]);
  });
});
