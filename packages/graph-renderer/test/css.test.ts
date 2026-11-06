import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { defaultTheme } from '../src';

const css = readFileSync(new URL('../src/graph.css', import.meta.url), 'utf8');

describe('the stylesheet', () => {
  it('names brand tokens and no colour', () => {
    const rules = css.replace(/\/\*[\s\S]*?\*\//g, '');
    expect(rules).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(rules).not.toMatch(/\b(rgb|rgba|hsl|hsla|oklch|lab|lch)\(/);
    expect(rules).not.toMatch(/:\s*(red|green|blue|black|white|gray|grey|orange|purple|yellow)\b/);
  });

  it('styles every class a theme refers to', () => {
    for (const name of Object.values(defaultTheme.classes)) {
      expect(css).toContain(`.${name}`);
    }
    expect(css).toContain('.is-selected');
    expect(css).toContain(':focus-visible');
  });
});
