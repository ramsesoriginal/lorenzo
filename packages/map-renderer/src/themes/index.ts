import type { Theme } from '../theme';
import { defaultTheme } from './default';
import { plainTheme } from './plain';

/** The names a Map may ask for (ADR 0352). `packages/map-engine` holds the same list. */
export const THEME_NAMES = ['default', 'plain'] as const;

export type ThemeName = (typeof THEME_NAMES)[number];

export const themes: Readonly<Record<ThemeName, Theme>> = {
  default: defaultTheme,
  plain: plainTheme,
};

/** The theme of a name; none, or one this version does not know, is the default. */
export function themeNamed(name: string | null | undefined): Theme {
  return typeof name === 'string' && Object.hasOwn(themes, name)
    ? themes[name as ThemeName]
    : defaultTheme;
}
