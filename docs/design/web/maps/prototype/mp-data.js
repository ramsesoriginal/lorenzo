/* Maps: made-up data. Nothing is real; nothing is saved. */
const SEG = [['Frostwane', 30], ['Thaw', 30], ['Seedtime', 30], ['Greening', 30], ['Highsun', 30], ['Harvest', 30], ['Leaffall', 30], ['Darkmonth', 30], ['Lamp week', 6]];
const YEAR_DAYS = SEG.reduce((s, x) => s + x[1], 0);
const dayName = (n) => { let left = n; for (const [name, d] of SEG) { if (left <= d) return `${name} ${left}, Year 4`; left -= d; } return `Year 4`; };
const dayNum = (seg, d) => SEG.slice(0, seg).reduce((s, x) => s + x[1], 0) + d;
/* Locations: a tree of "part of". A Location is any kind of place, from a universe to a floor. hidden ones are absent for readers. */
const LOCS = [
  { id: 'harbour-town', n: 'Harbour town', parent: null, open: true, tie: [] },
  { id: 'quay', n: 'The quay', parent: 'harbour-town', open: true, tie: [dayNum(3, 22), dayNum(3, 23)] },
  { id: 'old-town', n: 'Old town', parent: 'harbour-town', open: true, tie: [] },
  { id: 'customs', n: 'Customs house', parent: 'old-town', open: true, tie: [dayNum(3, 3), dayNum(3, 9)] },
  { id: 'lamp-square', n: 'Lamp square', parent: 'old-town', open: true, tie: [dayNum(3, 22), dayNum(3, 28)] },
  { id: 'east-wall', n: 'East wall', parent: 'old-town', open: true, tie: [] },
  { id: 'vault', n: 'The sealed vault', parent: 'customs', open: false, tie: [] },
  { id: 'cellar', n: 'The lamp cellar', parent: 'vault', open: true, tie: [] },
  { id: 'salt-flats', n: 'The salt flats', parent: null, open: true, tie: [] },
  { id: 'station', n: 'Station 4', parent: null, open: true, tie: [] }
];
const CONNS = [{ id: 'c1', a: 'customs', b: 'quay', how: 'Quay road' }, { id: 'c2', a: 'customs', b: 'station', how: 'The lamp tunnels' }, { id: 'c3', a: 'quay', b: 'salt-flats', how: 'The salt road' }];
const MAPS = [
  { id: 'harbour', n: 'The harbour', sys: 'Free plane', unit: 'paces', w: 600, h: 400, tie: [dayNum(3, 22)], shows: 'harbour-town', vis: true, theme: 'default', detail: true },
  { id: 'tunnels', n: 'The lamp tunnels', sys: 'Grid of squares', unit: 'metres', w: 600, h: 400, cell: 25, tie: [dayNum(3, 9)], shows: 'station', vis: true, theme: 'default', detail: true },
  { id: 'reach', n: 'The Reach', sys: 'Sphere', unit: 'degrees', tie: [], shows: '', vis: true, theme: 'default', detail: true },
  { id: 'deck', n: 'Station 4, deck plan', sys: 'Grid of hexes · pointy top', unit: 'metres', tie: [], shows: 'station', vis: true, detail: false },
  { id: 'old', n: 'Old town', sys: 'Outline only', unit: '', tie: [dayNum(3, 22)], shows: 'old-town', vis: false, detail: false }
];
/* placements on the harbour map. Every number is the map's own unit. */
const PL = {
  harbour: [
    { id: 'p-water', ent: 'The harbour water', k: 'area', role: 'water', pts: [[0, 330], [200, 310], [420, 340], [600, 320], [600, 400], [0, 400]], order: 1, layer: 'Terrain' },
    { id: 'p-square', ent: 'Lamp square', loc: 'lamp-square', k: 'area', role: 'site', pts: [[300, 140], [380, 130], [392, 200], [310, 212]], order: 2, layer: 'Places' },
    { id: 'p-road', ent: 'Quay road', k: 'line', role: 'road', pts: [[60, 220], [150, 190], [262, 270], [330, 250], [520, 230]], order: 3, layer: 'Roads' },
    { id: 'p-wall', ent: 'East wall', loc: 'east-wall', k: 'line', role: 'wall', pts: [[430, 90], [440, 190], [430, 290]], order: 4, layer: 'Places' },
    { id: 'p-customs', ent: 'Customs house', loc: 'customs', k: 'pin', role: 'site', pts: [[150, 120]], order: 5, layer: 'Places' },
    { id: 'p-quay', ent: 'The quay', loc: 'quay', k: 'pin', role: 'site', pts: [[262, 300]], order: 6, layer: 'Places' },
    { id: 'p-ir', ent: 'Imani Roe', k: 'person', role: 'person', pts: [[272, 290]], order: 7, layer: 'People', init: 'IR' }
  ],
  tunnels: [
    { id: 't1', ent: 'Lamp tunnel A', k: 'line', role: 'road', pts: [[75, 75], [75, 200], [275, 200], [275, 325]], order: 1, layer: 'Roads' },
    { id: 't2', ent: 'The lamp cellar', loc: 'cellar', k: 'cells', role: 'site', cells: ['2,2', '3,2', '4,2', '4,3'], pts: [], order: 2, layer: 'Places' },
    { id: 't3', ent: 'Station 4', loc: 'station', k: 'pin', role: 'site', pts: [[275, 325]], order: 3, layer: 'Places' }
  ],
  reach: [
    { id: 'r1', ent: 'The harbour', k: 'pin', role: 'site', ll: [12, 41], layer: 'Places', pts: [] },
    { id: 'r2', ent: 'Station 4', k: 'pin', role: 'site', ll: [-80, 28], layer: 'Places', pts: [] },
    { id: 'r3', ent: 'The salt flats', k: 'pin', role: 'site', ll: [60, -20], layer: 'Places', pts: [] }
  ]
};
const PICS = [{ id: 'pic1', n: 'Surveyor’s sketch', on: true, op: 60, fit: 'the sheet' }];
const BEINGS = [{ id: 'imani', n: 'Imani Roe', at: 'quay' }, { id: 'mara', n: 'Mara Quill', at: 'customs' }, { id: 'tobias', n: 'Tobias Reyes', at: null }];
const LINT = ['2 Locations are not part of anything: The salt flats, Station 4.', '“The sealed vault” is closed to the library and has an open Location inside it.', '“The quay” is tied to a date but is not placed on any Map as an area.'];
