import type { Page } from '@playwright/test';

export type Rgb = [number, number, number];

const luminance = (c: Rgb) => {
  const f = (v: number) => {
    const x = v / 255;
    return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
};

/** WCAG contrast ratio of two colours. */
export const contrast = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

export async function setTheme(page: Page, theme: 'light' | 'dark') {
  await page.evaluate((t) => {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
  }, theme);
  // The components animate colour changes; let them settle before reading a colour.
  await page.waitForTimeout(350);
}

/** The colour a CSS colour expression (color-mix, oklab, a var) resolves to, as sRGB. */
export async function resolve(page: Page, selector: string, property: string): Promise<Rgb> {
  return page.evaluate(
    ([sel, prop]) => {
      const el = document.querySelector(sel as string) as HTMLElement;
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
      ctx.fillStyle = '#000';
      ctx.fillStyle = getComputedStyle(el).getPropertyValue(prop as string);
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2]] as [number, number, number];
    },
    [selector, property],
  );
}

/** The sRGB of a custom property on the root, e.g. --text-tertiary. */
export async function token(page: Page, name: string): Promise<Rgb> {
  return page.evaluate((n) => {
    const probe = document.createElement('i');
    probe.style.color = `var(${n})`;
    document.body.append(probe);
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D;
    ctx.fillStyle = '#000';
    ctx.fillStyle = getComputedStyle(probe).color;
    ctx.fillRect(0, 0, 1, 1);
    probe.remove();
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2]] as [number, number, number];
  }, name);
}

/** Fail a test on any error the page throws. */
export function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}
