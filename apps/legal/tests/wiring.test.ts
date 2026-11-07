import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// ADR 0439: every web app links the legal notice, the privacy policy and the support link, from
// the registry (`GET /app-links`). The shared parts are tested in packages/app-shell; this checks
// that each app actually uses them, and that a new web app cannot be added without deciding.
const apps = fileURLToPath(new URL('../../', import.meta.url));

/** Static web apps that are not a Lorenzo web app of their own: nothing to link from. */
const EXEMPT = new Set(['brand', 'legal']);

function sources(dir: string): string[] {
  const found: string[] = [];
  for (const name of readdirSync(dir)) {
    if (['node_modules', 'dist', '.astro', 'public'].includes(name)) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) found.push(...sources(path));
    else if (/\.(ts|astro)$/.test(name) && !/\.(test|spec)\./.test(name)) found.push(path);
  }
  return found;
}

const webApps = readdirSync(apps).filter((name) => {
  const manifest = join(apps, name, 'package.json');
  if (EXEMPT.has(name) || !existsSync(manifest)) return false;
  const deps = JSON.parse(readFileSync(manifest, 'utf8')).dependencies ?? {};
  return 'astro' in deps;
});

describe('the web apps', () => {
  it('include the ones this test knows about', () => {
    expect(webApps).toEqual(
      expect.arrayContaining([
        'account-hub',
        'bench',
        'beings',
        'calendars',
        'inventory-web',
        'maps',
        'sessions',
        'social',
        'writing',
      ]),
    );
  });

  describe.each(webApps)('%s', (app) => {
    const text = sources(join(apps, app, 'src'))
      .map((path) => readFileSync(path, 'utf8'))
      .join('\n');

    it('reads the legal links from the registry', () => {
      expect(text).toContain('bindLegalLinksFromApi');
    });

    it('draws them: in the shared footer, its own footer, or its own bar', () => {
      expect(
        text.includes('app-shell/AppPage.astro') ||
          text.includes('app-shell/LegalLinks.astro') ||
          text.includes('legalHolders'),
      ).toBe(true);
    });
  });
});
