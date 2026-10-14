// ADR 0294: a text about a being of a campaign names its game master by the campaign's words, so
// no surface of a play library keeps "GM" in a literal. A repository's entries belong to no
// campaign and say "GM": the lock on an Everyone's note, with its "Make GM only", is that surface
// (it shows only for an entry of a repository), and so is the default words in lib/gmTitle.ts.
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

// Surfaces of a repository's entries, with the one wording each keeps.
const REPOSITORY_SURFACES: Record<string, string> = {
  // The button of the lock on an Everyone's note of a repository's entry.
  'components/BeingNotes/BeingNotes.astro': 'Make GM only',
  // The same button's label for a screen reader.
  'components/BeingNotes/renderer.ts': 'Make GM only: ',
  // The default, which the API also sends for a campaign that names nothing.
  'lib/gmTitle.ts': "{ title: 'GM', plural: 'GMs' }",
};

const read = (name: string) => withoutComments(readFileSync(join(here, name), 'utf8'));

describe('a campaign surface has no literal GM', () => {
  const files = sourceFiles(here).map((file) => ({
    name: relative(here, file).replaceAll('\\', '/'),
  }));

  it('finds the source it is checking', () => {
    expect(files.length).toBeGreaterThan(40);
  });

  it.each(files.filter(({ name }) => !(name in REPOSITORY_SURFACES)))('$name', ({ name }) => {
    expect(read(name)).not.toMatch(GM);
  });

  it.each(Object.entries(REPOSITORY_SURFACES))('%s says nothing else', (name, wording) => {
    expect(read(name).replaceAll(wording, '')).not.toMatch(GM);
  });
});

describe('a repository surface still says GM', () => {
  for (const [name, wording] of Object.entries(REPOSITORY_SURFACES)) {
    it(name, () => {
      expect(read(name)).toContain(wording);
    });
  }
});
