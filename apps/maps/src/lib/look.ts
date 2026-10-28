// The look of a Map for this viewer (ADR 0352): the viewer's own choice, then the Map's theme name,
// then the default. The choice is an appearance preference, kept in this browser only.
import { type Theme, themeNamed } from '@lorenzo/map-renderer';

export type Look = 'map' | 'default' | 'plain';

export const LOOKS: [Look, string][] = [
  ['map', "The Map's own"],
  ['default', 'Default'],
  ['plain', 'Plain'],
];

const KEY = 'lorenzo:maps:look';

export function readLook(): Look {
  try {
    const stored = localStorage.getItem(KEY);
    return stored === 'default' || stored === 'plain' ? stored : 'map';
  } catch {
    return 'map';
  }
}

export function writeLook(look: Look): void {
  try {
    if (look === 'map') localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, look);
  } catch {
    // The choice is only remembered when the browser lets it be.
  }
}

/** The theme to draw with: the viewer's choice unless it is "the Map's own", then the Map's name. */
export function chosenTheme(look: Look, hint: string | null | undefined): Theme {
  return themeNamed(look === 'map' ? hint : look);
}
