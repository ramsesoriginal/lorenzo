// A check of an app's own stylesheet against the shared brand (ADR 0322): an app styles itself
// with the brand's tokens and classes, so a custom property that no brand sheet defines is a bug
// (an undefined `var()` silently becomes nothing, as `--radius-md` did), and a literal colour,
// font, shadow or breakpoint is a second source of truth. Apps call `cssProblems` from a test.
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const brandDir = resolve(dirname(fileURLToPath(import.meta.url)), '../../apps/brand');
const sheets = ['tokens', 'fonts', 'base', 'layout', 'components', 'motion'];

function withoutComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/** Every custom property the brand sheets define. */
export function brandTokens() {
  const names = new Set();

  for (const sheet of sheets) {
    const css = withoutComments(readFileSync(join(brandDir, `${sheet}.css`), 'utf8'));

    for (const [, name] of css.matchAll(/(--[a-z0-9-]+)\s*:/gi)) names.add(name);
  }

  return names;
}

/**
 * What in `css` breaks the rules, one sentence each. An app's own custom properties (declared in
 * the same sheet) are known; the brand's are known; `alsoKnown` names the ones a script sets at
 * run time (a `style.setProperty` call).
 */
export function cssProblems(css, { alsoKnown = [] } = {}) {
  const text = withoutComments(css);
  const known = brandTokens();
  const problems = [];

  for (const name of alsoKnown) known.add(name);

  for (const [, name] of text.matchAll(/(--[a-z0-9-]+)\s*:/gi)) known.add(name);

  for (const [, name] of text.matchAll(/var\(\s*(--[a-z0-9-]+)/g)) {
    if (!known.has(name)) problems.push(`${name} is not defined by the brand or by this sheet`);
  }

  for (const [colour] of text.matchAll(/#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\(/gi)) {
    problems.push(`literal colour ${colour}: use a semantic token`);
  }

  for (const [, value] of text.matchAll(/box-shadow\s*:\s*([^;}]+)/g)) {
    if (value.trim() !== 'none') problems.push(`box-shadow ${value.trim()}: surfaces have a border, not a shadow`);
  }

  for (const [, value] of text.matchAll(/font-family\s*:\s*([^;}]+)/g)) {
    if (!/^var\(--font-[a-z-]+\)$/.test(value.trim())) {
      problems.push(`font-family ${value.trim()}: use the brand's font tokens`);
    }
  }

  for (const [, value] of text.matchAll(/border-radius\s*:\s*([^;}]+)/g)) {
    if (!/^(0|50%|var\(--radius-[a-z]+\))(\s+(0|50%|var\(--radius-[a-z]+\)))*$/.test(value.trim())) {
      problems.push(`border-radius ${value.trim()}: use a radius token`);
    }
  }

  for (const [, query] of text.matchAll(/@media\s+([^{]+)\{/g)) {
    for (const [, kind, width] of query.matchAll(/\((max|min)-width\s*:\s*([^)]+)\)/g)) {
      const expected = kind === 'max' ? '720px' : '721px';

      if (width.trim() !== expected) problems.push(`@media ${kind}-width ${width.trim()}: the one breakpoint is 720px`);
    }
  }

  if (/!important/.test(text)) problems.push('!important: fix the specificity instead');

  return problems;
}
