import type { Theme } from '../types';
import { defaultTheme } from './default';

/** A family tree: smaller nodes, ties with right angles, the labels cut shorter. Same data, same
 * classes; only sizes and the edge shape differ (ADR 0407). */
export const familyTheme: Theme = {
  ...defaultTheme,
  name: 'family',
  nodeRadius: 14,
  iconSize: 16,
  edgeShape: 'elbow',
  arrowSize: 8,
  parallelGap: 10,
  labelChars: 20,
};
