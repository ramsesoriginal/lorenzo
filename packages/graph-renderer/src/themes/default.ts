import type { Theme } from '../types';

/** The default theme: sizes, and class names the stylesheet maps onto brand tokens. It names no
 * colour, so light and dark follow the tokens (ADR 0407). */
export const defaultTheme: Theme = {
  name: 'default',
  nodeRadius: 16,
  iconSize: 18,
  fontSize: 12,
  edgeWidth: 1.5,
  edgeWidthMax: 5,
  arrowSize: 9,
  parallelGap: 16,
  hullPadding: 28,
  labelChars: 24,
  classes: {
    node: 'gr-node',
    edge: 'gr-edge',
    hull: 'gr-hull',
    label: 'gr-label',
    arrow: 'gr-arrow',
  },
};
