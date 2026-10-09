// Stand-in content for the page without sign-in: a small made-up repository, held in memory by
// the sample transport (core/sample.ts), so the editor can be tried and tested with no server.

import type { SampleEntry } from '../core/sample';
import type { StatDef } from '../core/transport';

export const SAMPLE_STATS: StatDef[] = [
  { id: 'armor', name: 'Armor class', type: 'int', enumValues: [] },
  { id: 'size', name: 'Size', type: 'enum', enumValues: ['tiny', 'small', 'medium', 'large'] },
  { id: 'flavour', name: 'Flavour', type: 'text', enumValues: [] },
  { id: 'undead', name: 'Undead', type: 'bool', enumValues: [] },
  { id: 'weight', name: 'Weight', type: 'float', enumValues: [] },
];

export const SAMPLE_ENTRIES: SampleEntry[] = [
  { id: 'monster', name: 'Monster', kinds: ['item'], parents: [], stats: { armor: 10 } },
  { id: 'beast', name: 'Beast', kinds: ['item'], parents: ['monster'] },
  {
    id: 'wolf',
    name: 'Wolf',
    kinds: ['item'],
    parents: ['beast'],
    description: 'Hunts in **packs**.',
    notes: [{ id: 'wolf-note', text: 'Pairs well with a ranger.' }],
  },
  { id: 'dire-wolf', name: 'Dire wolf', kinds: ['item'], parents: ['wolf'] },
  { id: 'undead', name: 'Undead', kinds: ['item'], parents: ['monster'], stats: { undead: true } },
  { id: 'zombie', name: 'Zombie', kinds: ['item'], parents: ['undead'] },
  { id: 'ghoul', name: 'Ghoul', kinds: ['item'], parents: ['undead', 'beast'] },
  { id: 'sword', name: 'Longsword', kinds: ['item'], parents: [] },
  { id: 'hollow', name: 'The Hollow', kinds: [], parents: [] },
  { id: 'ashfang', name: 'Ashfang', kinds: ['being'], parents: ['hollow'] },
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
