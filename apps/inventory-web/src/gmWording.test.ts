// ADR 0294: a text about one campaign's things names its game master by the campaign's words, so
// no surface of a campaign keeps "GM" in a literal. What has no one campaign in it says "GM": the
// library's public catalog and the library's unsorted page, listed below with why.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const here = import.meta.dirname;

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);

    if (entry.isDirectory()) return sourceFiles(path);

    return /\.(ts|astro)$/.test(entry.name) && !/\.test\.ts$/.test(entry.name) ? [path] : [];
  });
}

// The words a person could read: a file without its comments.
function withoutComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/(^|\s)\/\/.*$/gm, '');
}

const GM = /\bGMs?\b/;

// Surfaces about no one campaign, and the word they keep.
const LIBRARY_SURFACES: Record<string, string> = {
  // The public catalog of a library: its GMs, whatever each campaign calls its own.
  'components/Catalog/Catalog.astro': 'your GMs',
  // A library's unsorted page, reached by someone who GMs nothing here.
  'pages/unsorted/index.astro': 'for a GM',
  // The default, which the API also sends for a campaign that names nothing.
  'lib/gmTitle.ts': "title: 'GM'",
};

describe('a campaign surface has no literal GM', () => {
  const files = sourceFiles(here).map((file) => ({
    name: relative(here, file).replaceAll('\\', '/'),
    text: withoutComments(readFileSync(file, 'utf8')),
  }));

  it('finds the source it is checking', () => {
    expect(files.length).toBeGreaterThan(50);
  });

  it.each(files.filter(({ name }) => !(name in LIBRARY_SURFACES)))('$name', ({ text }) => {
    expect(text).not.toMatch(GM);
  });
});

describe('a library surface still says GM', () => {
  for (const [name, wording] of Object.entries(LIBRARY_SURFACES)) {
    it(name, () => {
      expect(withoutComments(readFileSync(join(here, name), 'utf8'))).toContain(wording);
    });
  }
});
