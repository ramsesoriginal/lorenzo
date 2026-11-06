import type { Engine, LayoutName } from '../types';
import { circle } from './circle';
import { forceatlas2 } from './forceatlas2';
import { layered } from './layered';
import { radial } from './radial';
import { stress } from './stress';

/** Each engine is `(graph, seed) -> positions`. `manual` lays the nodes that have no hand placement
 * on a circle and keeps those that have; `layered` rows the ranks of a family tree. The names are the
 * closed list in layouts.json. */
export const ENGINES: Record<LayoutName, Engine> = {
  circle,
  radial,
  stress,
  forceatlas2,
  manual: circle,
  layered,
};
