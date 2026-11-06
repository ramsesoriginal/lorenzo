/* Beings: made-up data for the prototype. The library's Settings define the stats; they are not designed here. */
const ME = 'ana';
const PEOPLE = [{ id: 'ana', n: 'Ana' }, { id: 'joss', n: 'Joss' }, { id: 'wen', n: 'Wen' }];
const CAMPAIGNS = [{ id: 'thu', n: 'Thursday table', players: ['ana', 'joss', 'wen'] }, { id: 'sun', n: 'Sunday one-shots', players: ['joss', 'wen'] }];
/* the stats a library defines (Settings): pin puts a number in the band; derived ones have a rule */
const STATDEF = [
  { id: 'hp', n: 'Hit points', k: 'num', pin: true, max: true },
  { id: 'res', n: 'Resolve', k: 'num', pin: true, max: true },
  { id: 'arm', n: 'Armour', k: 'num', pin: true, derived: (b) => 9 + b.stats.body.v, why: (b) => `9 plus Body (${b.stats.body.v})` },
  { id: 'body', n: 'Body', k: 'num' }, { id: 'mind', n: 'Mind', k: 'num' }, { id: 'reach', n: 'Reach', k: 'num' },
  { id: 'cond', n: 'Conditions', k: 'tags', play: true, options: ['Wounded', 'Shaken', 'Hidden'] },
  { id: 'role', n: 'Role', k: 'text' }, { id: 'langs', n: 'Languages', k: 'tags' },
];
const mk = (id, name, kind, played, campaign, seen, place, about, o) => ({ id, name, kind, played, campaign, seen, place, about, notes: [], inv: [], events: [], ...o });
const BEINGS = [
  mk('mara-quill', 'Mara Quill', 'Character', 'ana', 'thu', 'Everyone', 'Orbital Station 4', 'A quartermaster who keeps the ledger and a second, smaller ledger. Short, exact, and never in the room when a price is named.', {
    stats: { hp: { v: 14, max: 20 }, res: { v: 2, max: 3 }, body: { v: 3 }, mind: { v: 2 }, reach: { v: 5 }, role: { v: 'Quartermaster' }, langs: { v: ['Trade', 'Cant'] } },
    notes: [{ id: 'n1', aud: 'Everyone', t: 'Keeps the ledger. Knows what every crate on the quay weighs.' }, { id: 'n2', aud: 'Some characters', who: ['Tobias Reyes'], t: 'Owes Tobias Reyes a favour, and has not said which.' }, { id: 'n3', aud: 'GM only', t: 'Skims a little from every manifest. Has done for years.' }, { id: 'n4', aud: 'Player note', t: 'Ask what Mara would not sell.' }],
    inv: [['Ledger', 1], ['Lantern', 1], ['Key ring', 1], ['Rope, 15 m', 2]], events: [['Night on Station 4', 'Scene'], ['The missing manifest', 'Session']] }),
  mk('tobias-reyes', 'Tobias Reyes', 'Character', 'joss', 'thu', 'Everyone', 'Old Mill Road', 'Carries letters he has not delivered.', {
    stats: { hp: { v: 11, max: 18 }, res: { v: 3, max: 3 }, body: { v: 2 }, mind: { v: 3 }, reach: { v: 4 }, role: { v: 'Courier' }, langs: { v: ['Trade'] } },
    notes: [{ id: 'n5', aud: 'Everyone', t: 'Has been seen at every door on Mill Road.' }, { id: 'n6', aud: 'GM only', t: 'One letter is addressed to him.' }], inv: [['Satchel', 1], ['Letters', 7]], events: [['The missing manifest', 'Session']] }),
  mk('imani-roe', 'Dr. Imani Roe', 'Character', 'wen', 'thu', 'Everyone', 'Orbital Station 4', 'A physician with a lantern she was told to leave on the shelf.', {
    stats: { hp: { v: 9, max: 12 }, res: { v: 1, max: 4 }, body: { v: 1 }, mind: { v: 4 }, reach: { v: 3 }, role: { v: 'Physician' }, langs: { v: ['Trade', 'Latin'] } },
    notes: [{ id: 'n7', aud: 'Everyone', t: 'Prefers to be asked before anyone is moved.' }], inv: [['Lantern', 1], ['Kit', 1]], events: [] }),
  mk('harbour-master', 'Harbour master', 'NPC', null, null, 'Everyone', 'Harbour', 'Knows every ship by its sound. Does not know the one that arrived last night.', {
    stats: { hp: { v: 8, max: 8 }, res: { v: 4, max: 4 }, body: { v: 2 }, mind: { v: 3 }, reach: { v: 2 }, role: { v: 'Official' }, langs: { v: ['Trade'] } },
    notes: [{ id: 'n8', aud: 'Everyone', t: 'Keeps the tide table and shares it with anyone who asks politely.' }, { id: 'n9', aud: 'GM only', t: 'Let the unknown ship dock for a price.' }], inv: [['Tide table', 1]], events: [['Night on Station 4', 'Scene']] }),
  mk('orla-venn', 'Orla Venn', 'NPC', null, null, 'GM only', 'Apartment 3B', 'An inspector with one question and a long memory.', {
    stats: { hp: { v: 16, max: 16 }, res: { v: 5, max: 5 }, body: { v: 4 }, mind: { v: 4 }, reach: { v: 3 }, role: { v: 'Inspector' }, langs: { v: ['Trade', 'Cant'] } },
    notes: [{ id: 'n10', aud: 'GM only', t: 'Wants the second ledger.' }], inv: [['Notebook', 1]], events: [] }),
  mk('customs-clerk', 'Customs clerk', 'NPC', null, null, 'Everyone', 'Customs house', 'Stamps first and reads later.', {
    stats: { hp: { v: 5, max: 5 }, res: { v: 2, max: 2 }, body: { v: 1 }, mind: { v: 2 }, reach: { v: 1 }, role: { v: 'Clerk' }, langs: { v: ['Trade'] } }, notes: [{ id: 'n11', aud: 'Everyone', t: 'Works the late shift.' }], inv: [['Stamp', 1]], events: [] }),
];

BEINGS.forEach((b) => { b.stats.cond = { v: b.id === 'mara-quill' ? ['Hidden'] : [] }; });
