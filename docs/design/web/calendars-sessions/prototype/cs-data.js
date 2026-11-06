/* Calendars and Sessions: made-up data. Nothing is real; nothing is saved. */
const CAL = {
  name: 'The harbour reckoning', year: 4, week: ['Lampday', 'Quayday', 'Tideday', 'Saltday', 'Wickday', 'Restday'],
  seg: [{ n: 'Frostwane', d: 30 }, { n: 'Thaw', d: 30 }, { n: 'Seedtime', d: 30 }, { n: 'Greening', d: 30 }, { n: 'Highsun', d: 30 }, { n: 'Harvest', d: 30 }, { n: 'Leaffall', d: 30 }, { n: 'Darkmonth', d: 30 }, { n: 'Lamp week', d: 6, k: 'festival' }, { n: 'Leap day', d: 1, k: 'leap', every: 4, rem: 1 }],
  moons: [{ n: 'Pale', cycle: 28, off: 3 }, { n: 'Ember', cycle: 45, off: 11 }],
  version: 7,
  /* what is written on a period: key is year/segment/day. A period exists only once something is written on it. */
  periods: {
    '4/3/9': { notes: [{ id: 'n1', text: 'The customs house kept the list.' }] },
    '4/3/17': { notes: [{ id: 'n2', text: 'She came on the morning boat.' }] },
    '4/3/22': { notes: [{ id: 'n3', text: 'The lights went out a little after nineteen forty.' }] },
    '4/3/28': { notes: [{ id: 'n4', text: 'Lamps checked, five of five.' }] }
  },
  obs: [{ id: 'o1', name: 'Tide count', every: 6, segs: 'all', note: 'The harbourmaster counts the boats.' }, { id: 'o2', name: 'Wick-trimming', every: 10, segs: [3, 4], note: '' }]
};
const EV = [
  { id: 'ev-tax', name: 'The lamp tax is announced', dates: ['4/3/3'], aud: 'everyone', by: 'Mara Quill', part: ['harbourmaster'], info: 'A notice on the customs house door.', read: [], learn: [] },
  { id: 'ev-boats', name: 'Boats seized at the east steps', dates: ['4/3/9'], aud: 'everyone', by: 'Dana Okafor', part: ['harbourmaster', 'mara'], info: 'Nine boats, no warning.', read: [{ clock: 'tidal', val: '14.5' }], learn: [{ being: 'mara', info: 'The seizure list' }] },
  { id: 'ev-arrive', name: 'Imani arrives', dates: ['4/3/17'], aud: 'participants', by: 'Dana Okafor', part: ['imani'], info: '', read: [], learn: [] },
  { id: 'ev-black', name: 'The blackout', dates: ['4/3/22'], aud: 'participants', by: 'Dana Okafor', part: ['imani', 'harbourmaster', 'mara'], info: 'Every lamp but one.', read: [{ clock: 'tidal', val: '15.0' }], learn: [] },
  { id: 'ev-lamp', name: 'The first lamp fails', dates: ['4/3/22'], aud: 'restricted', by: 'Dana Okafor', part: ['harbourmaster'], info: 'GM only until the players ask.', read: [], learn: [] },
  { id: 'ev-quay', name: 'The quay is empty', dates: ['4/3/23'], aud: 'everyone', by: 'Dana Okafor', part: ['imani'], info: '', read: [], learn: [] },
  { id: 'ev-old', name: 'The new quay is opened', dates: ['3/5/12'], aud: 'everyone', by: 'Mara Quill', part: ['harbourmaster'], info: '', read: [], learn: [] }
];
const FACTS = [{ id: 'f-lamp', name: 'The fifth lamp is faulty', dates: ['4/3/28'], about: 'The east wall' }, { id: 'f-tax', name: 'Lamps are taxed by the wick', dates: [], about: 'The customs house' }];
/* an order assertion: a is before b, or a caused b. Each starts private. */
const ORD = [
  { id: 'a1', a: 'ev-tax', b: 'ev-boats', kind: 'before', shared: true },
  { id: 'a2', a: 'ev-tax', b: 'ev-boats', kind: 'caused', shared: false },
  { id: 'a3', a: 'ev-boats', b: 'ev-black', kind: 'before', shared: true },
  { id: 'a4', a: 'ev-lamp', b: 'ev-black', kind: 'caused', shared: false },
  { id: 'a5', a: 'ev-arrive', b: 'ev-black', kind: 'before', shared: true }
];
const BEINGS = { harbourmaster: 'The harbourmaster', mara: 'Mara Quill', imani: 'Imani Roe', tobias: 'Tobias Reyes' };
const CLOCKS = [
  { id: 'tidal', name: 'The tide clock', ticking: true, reck: [{ cal: 'The harbour reckoning', date: '4/3/1', val: '0', shared: false }], rel: [{ to: 'wick', ratio: '12', shared: false }], note: 'Counts tides since the quay opened.' },
  { id: 'wick', name: 'The wick clock', ticking: true, reck: [], rel: [], note: 'One mark for each wick burned.' },
  { id: 'dream', name: 'The dream clock', ticking: false, reck: [], rel: [], note: 'Timeless. It does not tick.' }
];
const SESS = [
  { id: 's5', camp: 'The harbour job', no: 5, title: 'The slip', real: 'Thu 7 Mar, 19:30', start: '4/3/3', covers: ['4/3/3'], gms: ['Dana Okafor'], roster: [{ who: 'Mara Quill', ch: 'Quartermaster Quill' }, { who: 'Tobias Reyes', ch: 'Tobias' }], status: 'past' },
  { id: 's6', camp: 'The harbour job', no: 6, title: 'The customs list', real: 'Thu 14 Mar, 19:30', start: '4/3/9', covers: ['4/3/9'], gms: ['Dana Okafor'], roster: [{ who: 'Mara Quill', ch: 'Quartermaster Quill' }, { who: 'Tobias Reyes', ch: 'Tobias' }], status: 'past' },
  { id: 's7', camp: 'The harbour job', no: 7, title: 'The blackout', real: 'Thu 21 Mar, 19:30', start: '4/3/22', covers: ['4/3/22', '4/3/23'], gms: ['Dana Okafor'], roster: [{ who: 'Mara Quill', ch: 'Quartermaster Quill' }, { who: 'Tobias Reyes', ch: 'Tobias' }, { who: 'Ana Duarte', ch: '' }], status: 'next',
    notes: { me: 'The players will want to know why the fifth lamp is the only one that fails. Hold the ledger back until they ask the harbourmaster.', gms: 'Keep the ledger for scene three.', part: 'Bring your lamps.' },
    refs: [{ kind: 'Fact', name: 'The fifth lamp is faulty', shared: true }, { kind: 'Event', name: 'The blackout', shared: false }, { kind: 'Being', name: 'The harbourmaster', shared: true }],
    scenes: [{ id: 'sc1', t: 'Lamps going out', st: 'planned', aud: 'group', note: 'Open on the quay at dusk.' }, { id: 'sc2', t: 'The east quay', st: 'planned', aud: 'private', note: '' }, { id: 'sc3', t: 'The ledger', st: 'planned', aud: 'group', note: 'Let them find the torn page.' }, { id: 'sc4', t: 'Night shift', st: 'planned', aud: 'private', note: '' }],
    played: null },
  { id: 's8', camp: 'The harbour job', no: 8, title: 'The salt road, part 1', real: 'Thu 28 Mar, 19:30', start: '', covers: [], gms: ['Dana Okafor'], roster: [], status: 'unplaced' },
  { id: 'a1', camp: 'Aftermath', no: 1, title: 'Arrival', real: 'Sat 23 Mar, 14:00', start: '4/5/2', covers: ['4/5/2'], gms: ['Mara Quill'], roster: [{ who: 'Dana Okafor', ch: 'Dana’s detective' }], status: 'upcoming', mine: 'player' }
];
const SCENES = [
  { id: 'sc1', t: 'Lamps going out', link: 'lamps-going-out', period: '4/3/22', refs: [{ kind: 'Event', name: 'The blackout', shared: false }, { kind: 'Being', name: 'The harbourmaster', shared: true }] },
  { id: 'sc2', t: 'The east quay', link: 'the-east-quay', period: '4/3/23', refs: [{ kind: 'Fact', name: 'The fifth lamp is faulty', shared: false }] },
  { id: 'sc3', t: 'The ledger', link: 'the-ledger', period: '', refs: [] },
  { id: 'sc4', t: 'Night shift', link: 'night-shift', period: '', refs: [] }
];
const LIVED = { mara: { name: 'Mara Quill', parts: ['ev-tax', 'ev-boats', 'ev-black'] }, imani: { name: 'Imani Roe', parts: ['ev-arrive', 'ev-black', 'ev-quay'] }, harbourmaster: { name: 'The harbourmaster', parts: ['ev-tax', 'ev-boats', 'ev-lamp', 'ev-black'] } };
const PLACES = [{ n: 'The east quay', at: ['4/3/22', '4/3/23'] }, { n: 'The customs house', at: ['4/3/9', '4/3/3'] }, { n: 'The old slip', at: ['3/5/12'] }, { n: 'The salt flats', at: [] }, { n: 'Lamp square', at: ['4/3/22', '4/3/28'] }];
