import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { cssProblems } from '../../../tools/brand/css-guard.mjs';

// Calendars styles itself with the brand's tokens and classes (ADR 0322): this fails on a
// custom property no brand sheet defines, a literal colour, font, shadow, radius or breakpoint,
// and !important. `--week-length` is the one property a script sets (the month grid's columns).
const src = join(import.meta.dirname, '..', 'src');
const alsoKnown = ['--week-length'];

function files(dir: string, ext: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return files(path, ext);
    return path.endsWith(ext) ? [path] : [];
  });
}

describe('the stylesheet', () => {
  it('uses only the brand’s tokens and classes', () => {
    const css = readFileSync(join(src, 'styles', 'app.css'), 'utf8');

    expect(cssProblems(css, { alsoKnown })).toEqual([]);
  });

  it('is not joined by a <style> block in a page or component', () => {
    const blocks = files(src, '.astro').flatMap((file) =>
      [...readFileSync(file, 'utf8').matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((match) => ({
        file,
        css: match[1] ?? '',
      })),
    );

    for (const { file, css } of blocks) {
      expect({ file, problems: cssProblems(css, { alsoKnown }) }).toEqual({ file, problems: [] });
    }
  });

  it('does not redeclare what the brand already has', () => {
    const css = readFileSync(join(src, 'styles', 'app.css'), 'utf8');
    const brand = [
      '\\.wrap',
      '\\.row',
      '\\.row-tight',
      '\\.stack',
      '\\.stack-tight',
      '\\.caption',
      '\\.editor-toolbar',
      '\\.ls-editor-panes',
      '\\.skip-link',
      '\\.site-header',
      '\\.panel',
      '\\.error',
      'input',
      'select',
      'textarea',
      'fieldset',
      'legend',
      'label',
    ];

    for (const name of brand) {
      // A selector that starts with the name, as its own rule: `.stack {`, not `.stack > .btn {`.
      expect(css).not.toMatch(new RegExp(`^${name}\\s*[,{]`, 'm'));
    }
    expect(css).not.toMatch(/^(?:a|button|input|select|textarea|summary)?:focus-visible/m);
  });
});
