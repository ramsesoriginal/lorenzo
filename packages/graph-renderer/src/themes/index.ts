import type { Theme } from '../types';
import { defaultTheme } from './default';

/** The themes by name. A theme is a module here, never a colour or a field of the data. */
export const THEMES: Record<string, Theme> = { default: defaultTheme };

/** The viewer's choice beats the web's hint, which beats the default (ADR 0406). */
export function themeFor(...names: (string | null | undefined)[]): Theme {
  for (const name of names) {
    const found = name ? THEMES[name] : undefined;
    if (found) return found;
  }
  return defaultTheme;
}

export { defaultTheme };
