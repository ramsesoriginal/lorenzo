/* Social: made-up data for the prototype, in a harbour town. Types, standings and scales are the library's own data. */
const EVENTS = [
  { id: 'harvest', n: 'The harvest fair' }, { id: 'wedding', n: 'The Wedding' }, { id: 'storm', n: 'The Storm' },
  { id: 'trial', n: 'The Trial', unordered: true }, { id: 'closed', n: 'A closed meeting', hidden: true },
];
const ENTS = {
  mara: { n: 'Mara Quill', k: 'being' }, wren: { n: 'Wren Ashby', k: 'being' }, tobias: { n: 'Tobias Reyes', k: 'being' }, imani: { n: 'Dr. Imani Roe', k: 'being' },
  orla: { n: 'Orla Venn', k: 'being', hid: true }, harbourm: { n: 'Harbour master', k: 'being' }, clerk: { n: 'Customs clerk', k: 'being' },
  lamp: { n: 'Lamp Street', k: 'location' }, guild: { n: 'The Guild', k: 'group' }, council: { n: 'Harbour council', k: 'group' },
};
const KIND_ICON = { being: 'kind-being', group: 'kind-group', location: 'kind-location', event: 'kind-event' };
const GROUP_MEMBERS = { guild: ['mara', 'tobias', 'imani'], council: ['harbourm', 'clerk', 'orla'] };
let TYPES = [
  { id: 'family', n: 'Family', parent: null }, { id: 'parent', n: 'Parent of', parent: 'family', directed: true, reads: 'is the parent of', back: 'is a child of', defaults: { rep: 3 } },
  { id: 'sibling', n: 'Sibling of', parent: 'family', directed: false, reads: 'is a sibling of' },
  { id: 'ally', n: 'Ally of', parent: null, directed: false, reads: 'is an ally of' }, { id: 'rival', n: 'Rival of', parent: null, directed: false, reads: 'is a rival of' },
  { id: 'confidant', n: 'Confidant of', parent: null, directed: true, reads: 'is a confidant of', back: 'confides in' }, { id: 'reports', n: 'Reports to', parent: null, directed: true, reads: 'reports to', back: 'has as a report' },
  { id: 'watches', n: 'Watches', parent: null, directed: true, reads: 'watches', back: 'is watched by' }, { id: 'owes', n: 'Owes a favour to', parent: null, directed: true, reads: 'owes a favour to', back: 'is owed a favour by' },
  { id: 'meets', n: 'Meets at', parent: null, directed: true, reads: 'meets at', back: 'is a meeting place of' }, { id: 'member', n: 'Member of', parent: null, directed: true, reads: 'is a member of', back: 'has as a member' },
];
let STANDINGS = [{ id: 'rep', n: 'Reputation', min: -5, max: 5 }, { id: 'fam', n: 'Familiarity', min: 0, max: 10 }, { id: 'faith', n: 'Faith', min: null, max: null }];
let RELS = [
  { id: 'r1', a: 'mara', b: 'wren', type: 'parent', vals: {}, since: 'wedding', until: null, aud: 'public', readers: [], through: [], notes: 'Since the harvest fair.' },
  { id: 'r2', a: 'mara', b: 'tobias', type: 'ally', vals: { rep: 3 }, since: 'harvest', until: null, aud: 'public', readers: [], through: [], notes: '' },
  { id: 'r3', a: 'tobias', b: 'imani', type: 'owes', vals: { rep: 2 }, since: 'storm', until: null, aud: 'restricted', readers: ['tobias'], through: [], notes: 'Over the storm.' },
  { id: 'r4', a: 'imani', b: 'mara', type: 'confidant', vals: { rep: 5, fam: 8 }, since: 'harvest', until: null, aud: 'restricted', readers: ['imani'], through: [], notes: '' },
  { id: 'r5', a: 'clerk', b: 'harbourm', type: 'reports', vals: { rep: 1 }, since: null, until: null, aud: 'public', readers: [], through: [], notes: '' },
  { id: 'r6', a: 'orla', b: 'mara', type: 'watches', vals: { rep: -2 }, since: 'wedding', until: 'storm', aud: 'restricted', readers: [], through: [], notes: '' },
  { id: 'r7', a: 'wren', b: 'tobias', type: 'ally', vals: { rep: 2 }, since: null, until: null, aud: 'public', readers: [], through: ['r2', 'r1'], notes: '' },
  { id: 'r8', a: 'orla', b: 'tobias', type: 'rival', vals: {}, since: 'closed', until: null, aud: 'restricted', readers: [], through: [], notes: '' },
  { id: 'r9', a: 'mara', b: 'lamp', type: 'meets', vals: {}, since: null, until: null, aud: 'public', readers: [], through: [], notes: '' },
  { id: 'r10', a: 'harbourm', b: 'guild', type: 'rival', vals: { rep: -3 }, since: 'storm', until: null, aud: 'restricted', readers: [], through: [], notes: '' },
  { id: 'r11', a: 'imani', b: 'clerk', type: 'ally', vals: { rep: 1 }, since: 'trial', until: null, aud: 'public', readers: [], through: ['r5', 'r2'], notes: '' },
  { id: 'r12', a: 'wren', b: 'guild', type: 'member', vals: {}, since: null, until: null, aud: 'public', readers: [], through: [], notes: '' },
  { id: 'r13', a: 'mara', b: 'tobias', type: 'ally', vals: { rep: -1 }, since: 'storm', until: null, aud: 'public', readers: [], through: [], notes: '' },
  { id: 'r14', a: 'harbourm', b: 'clerk', type: 'watches', vals: { rep: 2 }, since: null, until: null, aud: 'public', readers: [], through: [], notes: '' },
];
let WEBS = [
  { id: 'court', n: 'The harbour court', members: ['mara', 'wren', 'tobias', 'imani', 'orla', 'harbourm', 'clerk', 'lamp', 'guild'], layout: 'circle', pos: {} },
  { id: 'family', n: 'The Ashby family', members: ['mara', 'wren', 'tobias'], layout: 'circle', pos: {} },
  { id: 'council', n: 'The harbour council', members: ['harbourm', 'clerk', 'orla', 'council'], layout: 'circle', pos: {} },
];
const STALE = 'mara>imani'; /* a cell whose relationship changed meanwhile: its save is refused once */
