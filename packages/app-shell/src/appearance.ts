// What a person chooses about how the shell looks (D22, ADR 0416): the theme (the system's, light or
// dark), the density of lists and tables, and motion. Kept in this browser; the account has no
// preferences yet (ADR 0411). Reads never throw: private browsing has no storage, and the default
// then applies. SiteHead applies the same choices before first paint.

import {
  type Density,
  densityOf,
  initialTheme,
  type Motion,
  motionOf,
  type ThemeChoice,
  themeChoiceOf,
} from './pure';

export const DENSITY_KEY = 'lorenzo:density';
export const MOTION_KEY = 'lorenzo:motion';

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Not kept; it applies until the page is closed.
  }
}

export function readThemeChoice(themeKey: string): ThemeChoice {
  return themeChoiceOf(read(themeKey));
}

export function readDensity(): Density {
  return densityOf(read(DENSITY_KEY));
}

export function readMotion(): Motion {
  return motionOf(read(MOTION_KEY));
}

const dark = () => window.matchMedia?.('(prefers-color-scheme: dark)');

/** Applies a theme choice; the system's one is kept up to date while it is the choice. */
export function setThemeChoice(themeKey: string, choice: ThemeChoice): void {
  write(themeKey, choice === 'system' ? null : choice);
  document.documentElement.dataset.theme = initialTheme(
    choice === 'system' ? null : choice,
    dark()?.matches ?? false,
  );
}

export function setDensity(density: Density): void {
  write(DENSITY_KEY, density === 'comfortable' ? null : density);
  applyDensity(density);
}

export function setMotion(motion: Motion): void {
  write(MOTION_KEY, motion === 'reduced' ? 'reduced' : null);
  applyMotion(motion);
}

function applyDensity(density: Density): void {
  if (density === 'comfortable') delete document.documentElement.dataset.density;
  else document.documentElement.dataset.density = density;
}

function applyMotion(motion: Motion): void {
  if (motion === 'reduced') document.documentElement.dataset.motion = 'reduced';
  else delete document.documentElement.dataset.motion;
}

/** What was chosen, applied to this page, and the system's theme followed while it is the choice. */
export function applyAppearance(themeKey: string): void {
  applyDensity(readDensity());
  applyMotion(readMotion());
  dark()?.addEventListener?.('change', () => {
    if (readThemeChoice(themeKey) === 'system') setThemeChoice(themeKey, 'system');
  });
}
