/* Account hub: made-up data in several settings. Extends the shell's DATA. Nothing is real; nothing is saved. */
const HUB = {
  libraries: [
    { id: 'thursday', name: 'Thursday table', desc: 'Our weekly game and the notes we keep for it', role: 'Owner', people: [
        { name: 'Dana Okafor', role: 'Owner', you: true, by: '' }, { name: 'Mara Quill', role: 'Organizer', by: 'Dana Okafor' }, { name: 'Tobias Reyes', role: 'Author', by: 'Mara Quill' }],
      campaigns: [
        { id: 'harbour-job', name: 'The harbour job', system: 'Any system, or none', gms: ['Dana Okafor'], me: 'GM', players: [{ name: 'Mara Quill', ch: 'Quartermaster Quill' }, { name: 'Tobias Reyes', ch: 'Tobias' }, { name: 'Imani Roe', ch: 'Dr. Imani Roe' }],
          links: [{ id: 'l1', kind: 'Player link', made: '3 days ago', ends: 'in 2 days', uses: '3 of 10', status: 'active' }, { id: 'l2', kind: 'GM link', made: '2 weeks ago', ends: 'ended', uses: '1 of 1', status: 'used' }] },
        { id: 'aftermath', name: 'Aftermath', system: 'Any system, or none', gms: ['Mara Quill'], me: 'Player', players: [{ name: 'Dana Okafor', ch: 'Dana’s detective', you: true }], links: [] }
      ], repos: ['core-equipment', 'old-rules'] },
    { id: 'convention', name: 'Convention weekend', desc: 'One-shots we run at the club', role: 'Organizer', people: [
        { name: 'Ana Duarte', role: 'Owner', by: '' }, { name: 'Dana Okafor', role: 'Organizer', you: true, by: 'Ana Duarte' }],
      campaigns: [{ id: 'night-station', name: 'Night on Station 4', system: 'Any system, or none', gms: ['Ana Duarte'], me: 'Player', players: [{ name: 'Dana Okafor', ch: 'Dr. Imani Roe', you: true }, { name: 'Ken Oyelaran', ch: 'Unit K-7’s engineer' }], links: [] }], repos: ['field-notes'] },
    { id: 'family', name: 'Family archive', desc: 'Letters, trees and who lived where', role: 'Author', people: [], campaigns: [], repos: [] }
  ],
  repos: [
    { id: 'core-equipment', name: 'Core equipment', by: 'Ana Duarte', summary: 'Everyday gear for any setting: tools, clothing, containers and what they weigh.', state: 'Published', release: '2.1', rel: 'used', mine: null, visibility: 'Public', tags: ['gear', 'any setting'], system: 'Any system', lang: 'English', update: { changed: 4, added: 12, removed: 1, conflicts: 2 }, usedBy: ['thursday'], libs: 5, counts: { entries: 309, groups: 7, stats: 41, notes: 12 }, builtOn: [] },
    { id: 'harbour-station', name: 'Harbour and station', by: 'Dana Okafor', summary: 'A harbour town and an orbital station that share a ledger.', state: 'Draft', release: '', rel: 'publish', mine: 'Owner', visibility: 'Private', tags: ['places', 'mixed'], system: 'Any system', lang: 'English', update: null, usedBy: [], libs: 1, counts: { entries: 84, groups: 3, stats: 12, notes: 30 }, builtOn: ['core-equipment'] },
    { id: 'lanterns', name: 'City of lanterns', by: 'Dana Okafor', summary: 'Streets, guilds and rumours for a city that never quite goes dark.', state: 'Published', release: '1.3', rel: 'publish', mine: 'Author', visibility: 'Private', tags: ['city', 'intrigue'], system: 'Any system', lang: 'English', update: null, usedBy: ['thursday'], libs: 2, counts: { entries: 212, groups: 5, stats: 18, notes: 64 }, builtOn: ['core-equipment'] },
    { id: 'field-notes', name: 'Field notes', by: 'Ken Oyelaran', summary: 'Survey forms, specimen cards and a quiet kind of mystery.', state: 'Published', release: '0.9', rel: 'invited', mine: null, visibility: 'Private', tags: ['survey'], system: 'Any system', lang: 'English', update: null, usedBy: ['convention'], libs: 1, counts: { entries: 40, groups: 2, stats: 6, notes: 8 }, builtOn: [], copied: false },
    { id: 'old-rules', name: 'Old rules', by: 'Ana Duarte', summary: 'An earlier set of rules, kept for copies that still draw on it.', state: 'Published', release: '1.0', rel: 'gone', mine: null, visibility: 'Private', tags: ['legacy'], system: 'Any system', lang: 'English', update: null, usedBy: ['thursday'], libs: 3, counts: { entries: 120, groups: 4, stats: 20, notes: 0 }, builtOn: [], copied: true }
  ],
  discover: [
    { id: 'core-equipment', name: 'Core equipment', by: 'Ana Duarte', summary: 'Everyday gear for any setting.', tags: ['gear'], system: 'Any system', lang: 'English', release: '2.1', libs: 5 },
    { id: 'orbital-stations', name: 'Orbital stations', by: 'Ken Oyelaran', summary: 'Docks, rings, lifts and what goes wrong with them.', tags: ['space', 'places'], system: 'Any system', lang: 'English', release: '1.2', libs: 11 },
    { id: 'apartment-3b', name: 'Apartment 3B', by: 'Pilar Vega', summary: 'A building full of people with something to hide.', tags: ['mystery', 'modern'], system: 'Any system', lang: 'Español', release: '1.0', libs: 7 },
    { id: 'family-trees', name: 'Family trees', by: 'Mara Quill', summary: 'Kinds, links and a way to draw who belongs to whom.', tags: ['people'], system: 'Any system', lang: 'English', release: '0.4', libs: 3 },
    { id: 'harbour-towns', name: 'Harbour towns', by: 'Tobias Reyes', summary: 'Twenty harbours, their ledgers and their weather.', tags: ['places', 'sea'], system: 'Any system', lang: 'Deutsch', release: '1.1', libs: 9 },
    { id: 'detective-files', name: 'Detective files', by: 'Orla Venn', summary: 'Case cards, suspects and the thread between them.', tags: ['mystery'], system: 'Any system', lang: 'English', release: '2.0', libs: 14 }
  ],
  needs: [
    { id: 'n1', kind: 'Updates', icon: 'update-available', title: 'Core equipment has updates waiting', meta: 'Thursday table · 4 changed, 12 new, 1 removed upstream, 2 conflicts', act: 'Review updates', go: 'repo/core-equipment/use' },
    { id: 'n2', kind: 'Links', icon: 'waiting', title: 'The player link for The harbour job ends in 2 days', meta: 'Thursday table · used 3 of 10 times', act: 'Make a new link', go: 'library/thursday/campaigns' },
    { id: 'n3', kind: 'People', icon: 'kind-beings', title: 'A new player joined The harbour job', meta: 'Imani Roe · yesterday', act: 'See players', go: 'library/thursday/campaigns' },
    { id: 'n4', kind: 'Updates', icon: 'stale', title: 'Harbour and station is still a draft', meta: 'You are its Owner · 1 library has it open for testing', act: 'Open', go: 'repo/harbour-station' }
  ],
  notifications: [
    { id: 'a1', text: 'Core equipment was published as release 2.1.', when: '2 hours ago', unread: true, go: 'repo/core-equipment' },
    { id: 'a2', text: 'Imani Roe joined The harbour job as a player.', when: 'Yesterday', unread: true, go: 'library/thursday/campaigns' },
    { id: 'a3', text: 'Ana Duarte made you an Organizer of Convention weekend.', when: '3 days ago', unread: true, go: 'library/convention' },
    { id: 'a4', text: 'Old rules is no longer offered to Thursday table. Your copy stays.', when: 'Last week', unread: false, go: 'repo/old-rules' },
    { id: 'a5', text: 'A GM link for The harbour job was used.', when: '2 weeks ago', unread: false, go: 'library/thursday/campaigns' }
  ],
  tokens: [
    { id: 't1', name: 'Laptop command line', hint: 'x3Qf', made: '12 March', used: 'Today', ends: 'Never' },
    { id: 't2', name: 'Phone', hint: 'k9Lm', made: '2 February', used: '3 weeks ago', ends: '2 May' }
  ],
  updates: {
    New: [{ id: 'u1', what: 'Lantern, hooded', label: 'A new entry', from: '', now: 'Item · 2 lb', yours: '' }, { id: 'u2', what: 'Climbing kit', label: 'A new entry', from: '', now: 'Item · 6 lb', yours: '' }, { id: 'u3', what: 'Weight (stone)', label: 'A new stat', from: '', now: 'A number', yours: '' }],
    Changed: [{ id: 'u4', what: 'Rope, 15 m', label: 'Weight', from: '4 lb', now: '5 lb', yours: '', clean: true }, { id: 'u5', what: 'Field jacket', label: 'Weight', from: '6 lb', now: '5 lb', yours: '', clean: true }, { id: 'u6', what: 'Repair kit', label: 'Weight', from: '3 lb', now: '4 lb', yours: '3.5 lb', clean: false }, { id: 'u7', what: 'Short blade', label: 'Weight', from: '3 lb', now: '2.5 lb', yours: '3 lb, bound', clean: false }],
    'Removed upstream': [{ id: 'u8', what: 'Brass lamp', label: 'Removed from the repository', from: 'An item', now: 'Gone', yours: 'Still in your library', clean: false }],
    Conflict: [{ id: 'u9', what: 'Winter coat', label: 'Parents', from: 'Clothing', now: 'Outerwear', yours: 'Clothing, Heavy', clean: false }]
  },
  releases: [{ label: '2.1', when: 'Today', breaking: false, notes: 'New hooded lantern and climbing kit.' }, { label: '2.0', when: '3 months ago', breaking: true, notes: 'Weights are in pounds.' }],
  activity: ['Dana Okafor made a player link for The harbour job · 3 days ago', 'Imani Roe joined The harbour job · yesterday', 'Mara Quill was made an Organizer · last month']
};
/* The hub's own tabs in the shell's second tier (D12): Home, Libraries, Repositories, and Discover when public repositories are on */
DATA.apps.find((a) => a.id === 'account').route = 'hub';
DATA.appTabs.account = [['Home', 'hub'], ['Libraries', 'libraries'], ['Repositories', 'repositories'], ['Discover', 'discover']];
DATA.libraries = HUB.libraries.map((l) => l.name);
DATA.others.unshift(...HUB.libraries.map((l) => ({ id: 'lib-' + l.id, name: l.name, kind: 'Library', app: 'Account', appId: 'account', route: 'library/' + l.id, blurb: l.desc })), ...HUB.repos.map((r) => ({ id: 'repo-' + r.id, name: r.name, kind: 'Repository', app: 'Account', appId: 'account', route: 'repo/' + r.id, blurb: r.summary })));
DATA.beings = [];

DATA.notifications = HUB.notifications.map((n) => ({ ...n }));
