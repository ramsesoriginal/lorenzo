// What a Map's coordinate system is called on a card of the gallery (MP1): "Free plane · paces",
// "Grid of hexes · pointy top · metres", "Sphere · degrees". Pure, so the page and the tests share
// it. The author's own unit is said as the author wrote it, and nothing is assumed when there is none.
import type { System } from '@lorenzo/map-renderer';

const NAMES: Record<string, string> = {
  plane: 'Free plane',
  outline: 'Outline only',
  square: 'Grid of squares',
  rect: 'Grid of rectangles',
  hex: 'Grid of hexes',
  sphere: 'Sphere',
};

export function systemWords(system: System): string {
  const parts = [NAMES[system.kind] ?? system.kind];
  if (system.kind === 'hex')
    parts.push(
      system.orientation === 'pointy'
        ? 'pointy top'
        : system.orientation === 'flat'
          ? 'flat top'
          : '',
    );
  if (system.kind === 'plane') parts.push(system.scale?.unit ?? '');
  if (system.kind === 'square' || system.kind === 'rect' || system.kind === 'hex')
    parts.push(system.measure?.unit ?? '');
  if (system.kind === 'sphere') parts.push('degrees');

  return parts.filter(Boolean).join(' · ');
}
