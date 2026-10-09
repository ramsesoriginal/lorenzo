// Stand-in content for the page without sign-in: a small made-up repository, held in memory by
// the sample transport (core/sample.ts), so the editor can be tried and tested with no server.

import type { SampleEntry } from '../core/sample';

export const SAMPLE_ENTRIES: SampleEntry[] = [
  { id: 'monster', name: 'Monster', kinds: ['item'], parents: [] },
  { id: 'beast', name: 'Beast', kinds: ['item'], parents: ['monster'] },
  { id: 'wolf', name: 'Wolf', kinds: ['item'], parents: ['beast'] },
  { id: 'dire-wolf', name: 'Dire wolf', kinds: ['item'], parents: ['wolf'] },
  { id: 'undead', name: 'Undead', kinds: ['item'], parents: ['monster'] },
  { id: 'zombie', name: 'Zombie', kinds: ['item'], parents: ['undead'] },
  { id: 'ghoul', name: 'Ghoul', kinds: ['item'], parents: ['undead', 'beast'] },
  { id: 'sword', name: 'Longsword', kinds: ['item'], parents: [] },
  { id: 'hollow', name: 'The Hollow', kinds: [], parents: [] },
  { id: 'mill', name: 'The old mill', kinds: [], parents: ['hollow'] },
];

export interface PaneDef {
  id: string;
  title: string;
  /** Size of a window when this pane is floated out. */
  float: [number, number];
}

export const PANES: PaneDef[] = [
  { id: 'explorer', title: 'Explorer', float: [264, 480] },
  { id: 'entry', title: 'Entry', float: [720, 520] },
  { id: 'props', title: 'Stats', float: [324, 500] },
  { id: 'links', title: 'Parents and children', float: [304, 380] },
];

export const PANE_IDS = PANES.map((p) => p.id);
