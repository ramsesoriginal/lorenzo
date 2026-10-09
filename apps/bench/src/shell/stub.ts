// Stand-in content for the workbench until the API is wired in (B2, B3). Made-up entries.

export interface StubEntry {
  id: string;
  name: string;
  parents: string[];
  kind: string;
  text: string;
  stats: Record<string, number>;
}

export const ENTRIES: StubEntry[] = [
  {
    id: 'monster',
    name: 'Monster',
    parents: [],
    kind: 'item',
    text: 'The root of everything that bites.',
    stats: { hp: 10, ac: 10 },
  },
  {
    id: 'beast',
    name: 'Beast',
    parents: ['monster'],
    kind: 'item',
    text: 'Natural creatures.',
    stats: { hp: 15 },
  },
  {
    id: 'wolf',
    name: 'Wolf',
    parents: ['beast'],
    kind: 'item',
    text: 'Hunts in packs.',
    stats: { hp: 11, ac: 13, speed: 40 },
  },
  {
    id: 'dire-wolf',
    name: 'Dire wolf',
    parents: ['wolf'],
    kind: 'item',
    text: 'A wolf, only more.',
    stats: { hp: 37, ac: 14 },
  },
  {
    id: 'undead',
    name: 'Undead',
    parents: ['monster'],
    kind: 'item',
    text: 'Not done yet.',
    stats: { ac: 8 },
  },
  {
    id: 'zombie',
    name: 'Zombie',
    parents: ['undead'],
    kind: 'item',
    text: 'Slow and certain.',
    stats: { hp: 22, speed: 20 },
  },
  {
    id: 'ghoul',
    name: 'Ghoul',
    parents: ['undead', 'beast'],
    kind: 'item',
    text: 'Two parents: undead, and beast.',
    stats: { hp: 22, ac: 12 },
  },
  {
    id: 'sword',
    name: 'Longsword',
    parents: [],
    kind: 'item',
    text: 'A sword.',
    stats: { damage: 8 },
  },
  {
    id: 'hollow',
    name: 'The Hollow',
    parents: [],
    kind: 'place',
    text: 'A village that stopped.',
    stats: {},
  },
  {
    id: 'mill',
    name: 'The old mill',
    parents: ['hollow'],
    kind: 'place',
    text: 'Burned down.',
    stats: {},
  },
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
