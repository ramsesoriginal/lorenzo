// The colour a person picks for themselves (ADR 0418, PT2): five to choose from and any #RRGGBB. It
// is drawn on a light and on a dark surface, so it must be told apart from both (3 to 1, WCAG's
// threshold for a mark that is not text). Pure, so it is tested without a browser.

/** The page's two surfaces: Paper and Ink (identity.md). */
const LIGHT = '#FBFAF7';
const DARK = '#08131F';

export const MIN_CONTRAST = 3;

/** Five to choose from: each passes the check on both surfaces. */
export const SWATCHES: { name: string; hex: string }[] = [
  { name: 'Rust', hex: '#B5471E' },
  { name: 'Blue', hex: '#2D6FB5' },
  { name: 'Green', hex: '#2F8A57' },
  { name: 'Violet', hex: '#8C47B3' },
  { name: 'Amber', hex: '#B8760A' },
];

/** "#abc" and "#aabbcc", in any case, as "#AABBCC"; null for anything else. */
export function normalizeHex(text: string): string | null {
  const match = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(text.trim());

  if (!match?.[1]) return null;

  const digits = match[1].length === 3 ? [...match[1]].map((d) => d + d).join('') : match[1];

  return `#${digits.toUpperCase()}`;
}

function channel(value: number): number {
  const s = value / 255;

  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const n = Number.parseInt(hex.slice(1), 16);

  return (
    0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255)
  );
}

/** WCAG contrast ratio of two #RRGGBB colours, 1 to 21. */
export function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p) as [number, number];

  return (x + 0.05) / (y + 0.05);
}

/** Why a colour cannot be used, in words, or null when it can. */
export function colourProblem(hex: string): string | null {
  const normal = normalizeHex(hex);

  if (!normal) return 'A colour is six characters after the #, such as #B5471E.';
  if (contrast(normal, LIGHT) < MIN_CONTRAST || contrast(normal, DARK) < MIN_CONTRAST) {
    return 'That colour is hard to see on a light page or a dark one. Try a stronger or a deeper one.';
  }

  return null;
}
