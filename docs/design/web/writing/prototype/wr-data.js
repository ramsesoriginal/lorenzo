/* Writing: made-up data. Nothing is real; nothing is saved. The model follows RFC 0047: an entry's content is an ordered list of
   items, and a child Chapter is an item, so prose can sit before, between and after children. */
const P1 = 'Imani came down the hill with one bag and no plan. The harbour below her was the colour of a slate roof, and every window along the front had a lamp in it.';
const WD = {
  nodes: {
    ed1: { id: 'ed1', kind: 'edition', title: 'Edition 1', items: [{ id: 'a1', t: 'child', ref: 'ch1' }, { id: 'a2', t: 'child', ref: 'ch2' }, { id: 'a3', t: 'child', ref: 'ch3' }] },
    ch1: { id: 'ch1', kind: 'chapter', title: 'Arrivals', items: [{ id: 'b1', t: 'p', text: P1 }, { id: 'b2', t: 'p', text: 'Nobody met her. That suited her; she had learned to distrust a welcome that came with a handshake and a question.' }] },
    ch2: { id: 'ch2', kind: 'chapter', title: 'The blackout', items: [
      { id: 'c1', t: 'p', text: 'The lights went out a little after nineteen forty. By the time anyone thought to look at the clock, the whole front was dark.' },
      { id: 'c2', t: 'child', ref: 'ch21' }, { id: 'c3', t: 'child', ref: 'ch22' },
      { id: 'c4', t: 'p', text: 'In the morning they would argue about whose fault it was. That night nobody argued about anything.' }] },
    ch21: { id: 'ch21', kind: 'chapter', title: 'Lamps out', items: [{ id: 'd1', t: 'p', text: 'Nobody noticed the first lamp. Everybody noticed the third.' }, { id: 'd2', t: 'p', text: 'The harbourmaster stood in the doorway of the customs house and counted them out loud, as if the number might be argued with.' }] },
    ch22: { id: 'ch22', kind: 'chapter', title: 'The quay', items: [
      { id: 'e1', t: 'p', text: 'The quay was empty when Imani reached it. Somewhere behind the warehouses a bell rang the hour, and the water slapped against the stone as though it had been waiting.' },
      { id: 'e2', t: 'p', text: 'She counted the lamps along the east wall on day 112 of Year 4. Four were lit. The fifth, the one the harbourmaster always complained about, had gone dark again.' },
      { id: 'e3', t: 'tell', scene: 'sc-ledger', own: false, text: '' },
      { id: 'e4', t: 'pic', cap: 'The east wall at dusk' },
      { id: 'e5', t: 'list', rows: ['Four lamps lit', 'The fifth dark', 'No boats at the east steps'] },
      { id: 'e6', t: 'p', text: '“You’re late,” said the voice from the dark, and Imani did not turn round.' }] },
    ch3: { id: 'ch3', kind: 'chapter', title: 'Night shift', items: [{ id: 'f1', t: 'p', text: 'By midnight the harbour had its own weather. The wind came in low along the water and found every gap in every door.' }, { id: 'f2', t: 'p', text: 'The night crew changed at one. Nobody had told them about the lamps.' }] },
    ed2: { id: 'ed2', kind: 'edition', title: 'Edition 2', items: [{ id: 'g1', t: 'child', ref: 'ch1b' }] },
    ch1b: { id: 'ch1b', kind: 'chapter', title: 'Arrivals', items: [{ id: 'g2', t: 'p', text: P1 }] },
    'sc-ledger': { id: 'sc-ledger', kind: 'scene', title: 'The ledger', items: [{ id: 'h1', t: 'p', text: 'Every name in the ledger had been struck through but one. Someone had pressed hard enough to tear the page.' }] },
    'sc-bell': { id: 'sc-bell', kind: 'scene', title: 'The night bell', items: [{ id: 'i1', t: 'p', text: 'The bell rang once, and then not again.' }] },
    'ch-alt': { id: 'ch-alt', kind: 'chapter', title: 'Opening, other ways', items: [{ id: 'j1', t: 'p', text: 'A first line, tried three ways. This is the second.' }] },
    car: { id: 'car', kind: 'carrier', title: 'The harbourmaster’s log', items: [{ id: 'k1', t: 'p', text: 'Entered in the harbourmaster’s own hand, the log opens with the weather.' }, { id: 'k2', t: 'cover', ref: 'ch22' }] },
    ed4: { id: 'ed4', kind: 'edition', title: 'Edition 1', items: [{ id: 'n1', t: 'child', ref: 'fg-toc' }, { id: 'n2', t: 'child', ref: 'fg-lamps' }, { id: 'n3', t: 'child', ref: 'fg-wall' }, { id: 'n4', t: 'child', ref: 'fg-old' }] },
    'fg-toc': { id: 'fg-toc', kind: 'chapter', special: 'contents', unnumbered: true, title: 'Contents', items: [] },
    'fg-lamps': { id: 'fg-lamps', kind: 'chapter', title: 'Lamps and lanterns', items: [{ id: 'o1', t: 'p', text: 'A harbour lamp burns oil, and a lantern burns a wick. The difference matters when the wind is up.' }] },
    'fg-wall': { id: 'fg-wall', kind: 'chapter', title: 'The east wall', items: [{ id: 'o2', t: 'p', text: 'The east wall carries five lamps. The fifth is the harbourmaster’s complaint, and has been for years.' }, { id: 'o3', t: 'p', text: 'We added a note here about the steps, because our players always ask.' }] },
    'fg-old': { id: 'fg-old', kind: 'chapter', title: 'Old harbour', items: [{ id: 'o4', t: 'p', text: 'Before the new quay, boats tied up at the slip below the customs house.' }] },
    ed3: { id: 'ed3', kind: 'edition', title: 'Edition 1', items: [{ id: 'l1', t: 'child', ref: 'ch-s1' }] },
    'ch-s1': { id: 'ch-s1', kind: 'chapter', title: 'Crossing', items: [{ id: 'm1', t: 'p', text: 'The salt road ran white across the flat, and the carts left no mark on it at all.' }, { id: 'm2', t: 'p', text: 'By the third day the drivers had stopped talking about the weather and begun talking about water.' }, { id: 'm3', t: 'p', text: 'Mara counted the wells. Two were dry. The third was not a well at all.' }] }
  },
  works: [
    { id: 'harbour', kind: 'Book', title: 'The harbour tales', root: 'ed1', editions: ['ed1', 'ed2'], role: 'Author', edited: 'edited today', goal: 600 },
    { id: 'harbour-2', kind: 'Book', title: 'The harbour tales', root: 'ed2', role: 'Author', hidden: true },
    { id: 'sc-ledger', kind: 'Scene', title: 'The ledger', root: 'sc-ledger', role: 'Author', edited: 'edited yesterday' },
    { id: 'sc-bell', kind: 'Scene', title: 'The night bell', root: 'sc-bell', role: 'Author', edited: 'edited 3 days ago' },
    { id: 'ch-alt', kind: 'Chapter', title: 'Opening, other ways', root: 'ch-alt', role: 'Author', edited: 'edited last week', note: 'Not in a Book yet' },
    { id: 'car', kind: 'Carrier', title: 'The harbourmaster’s log', root: 'car', role: 'Author', edited: 'edited 2 weeks ago', note: 'Covers 1 Chapter' },
    { id: 'field-guide', kind: 'Book', title: 'Harbour field guide', root: 'ed4', role: 'Author', edited: 'copied from City of lanterns', source: 'City of lanterns', release: '1.3', upstream: '1.4', last: 'fg-lamps' },
    { id: 'salt', kind: 'Book', title: 'The salt road', root: 'ed3', role: 'Reviewer', edited: 'shared by Tobias Reyes', by: 'Tobias Reyes' }
  ],
  revisions: [['19:38', 'You', 'Saved text'], ['19:12', 'You', 'Before “Make a Chapter”'], ['Yesterday 22:04', 'You', 'Saved text'], ['Mon 18:30', 'Tobias Reyes', 'Saved text']],
  reviewers: [{ name: 'Tobias Reyes', email: 'tobias@example.org' }, { name: 'Ana Duarte', email: 'ana@example.org' }],
  beings: ['Imani Roe', 'The harbourmaster', 'Mara Quill'],
  notes: {},
  /* mentionable entries the person can see (names, a place, a calendar date), for reviewed suggestions (W8d) */
  entities: [{ name: 'Imani Roe', kind: 'Being', match: ['Imani'] }, { name: 'Imani Okoro', kind: 'Being', match: ['Imani'] }, { name: 'The harbourmaster', kind: 'Being', match: ['harbourmaster'] }, { name: 'Mara Quill', kind: 'Being', match: ['Mara'] }, { name: 'Customs house', kind: 'Location', match: ['customs house'] }],
  dates: [{ re: /day (\d+) of Year (\d+)/, to: (m) => `Year ${m[2]}, day ${m[1]}` }],
  /* manuscript updates from the repository a Book was copied from (W9): was is the copied release, now is upstream, yours is the local text */
  updates: [
    { id: 'u1', kind: 'changed', title: 'Lamps and lanterns', note: 'Changed upstream. You have not edited it.', was: 'A harbour lamp burns oil, and a lantern burns a wick.', now: 'A harbour lamp burns oil, and a lantern burns a wick. The difference matters when the wind is up.', yours: 'A harbour lamp burns oil, and a lantern burns a wick.' },
    { id: 'u2', kind: 'conflict', title: 'The east wall', note: 'Changed upstream and by you.', was: 'The east wall carries four lamps.', now: 'The east wall carries five lamps. The fifth is the harbourmaster’s complaint.', yours: 'The east wall carries four lamps. We added a note about the steps.' },
    { id: 'u3', kind: 'new', title: 'Quay rules', note: 'New upstream, with “Night rules” inside it.', was: '', now: 'Who may tie up, and when. Night rules sit inside this chapter.', yours: '' },
    { id: 'u4', kind: 'removed', title: 'Old harbour', note: 'Removed upstream. You edited it, so it is kept until you choose.', was: 'Before the new quay, boats tied up at the slip.', now: '', yours: 'Before the new quay, boats tied up at the slip below the customs house.' }
  ]
};
