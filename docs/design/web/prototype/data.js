/* Made-up data in several settings. Nothing here is real and nothing is saved. */
const DATA = {
  user: { name: 'Dana Okafor', email: 'dana@example.org', initials: 'DO' },
  libraries: ['Thursday table', 'Convention weekend', 'Family archive'],
  apps: [
    { id: 'sessions', name: 'Sessions', group: 'Play', desc: 'Plan and run your games', icon: 'kind-session', route: 'home' },
    { id: 'beings', name: 'Beings', group: 'Play', desc: 'Characters and non-player characters', icon: 'kind-being', route: 'beings' },
    { id: 'inventory', name: 'Inventory', group: 'Play', desc: 'What people carry', icon: 'inventory', route: 'board' },
    { id: 'calendars', name: 'Calendars', group: 'World', desc: 'Time in your world', icon: 'kind-calendar', route: 'stub/calendars' },
    { id: 'maps', name: 'Maps', group: 'World', desc: 'Places and maps', icon: 'map', route: 'map' },
    { id: 'writing', name: 'Writing', group: 'Build', desc: 'Manuscripts and books', icon: 'manuscript', route: 'read' },
    { id: 'social', name: 'Social', group: 'World', desc: 'Who is tied to whom', icon: 'social', route: 'webs' },
    { id: 'bench', name: 'Bench', group: 'Build', desc: 'Build and edit a repository', icon: 'layout-write', route: 'stub/bench' },
    { id: 'account', name: 'Account', group: 'You', desc: 'People, libraries, repositories and tokens', icon: 'account', route: 'settings' }
  ],
  appTabs: {
    sessions: [['Home', 'home'], ['Upcoming', 'upcoming'], ['Scenes', 'scenes'], ['Notes', 'notes']],
    beings: [['All beings', 'beings'], ['Mine', 'beings-mine'], ['Updates', 'beings-updates']],
    inventory: [['Boards', 'board'], ['Items', 'items'], ['Notes', 'inv-notes']],
    maps: [['Maps', 'map'], ['Locations', 'locations'], ['Connections', 'connections']],
    writing: [['Read', 'read'], ['Write', 'write'], ['Books', 'books']],
    social: [['Webs', 'webs'], ['Relationships', 'relationships'], ['Types and standings', 'types'], ['Problems', 'problems']],
    account: [['Libraries', 'settings'], ['Profile', 'profile'], ['Tokens', 'tokens']],
    calendars: [['Calendars', 'stub/calendars']],
    bench: [['Entries', 'stub/bench']]
  },
  beings: [
    { id: 'mara-quill', name: 'Mara Quill', kind: 'Character', seen: 'Everyone', state: 'synced', blurb: 'A quartermaster who keeps the ledger and a second, smaller ledger.', initials: 'MQ', place: 'Orbital Station 4' },
    { id: 'harbour-master', name: 'Harbour master', kind: 'NPC', seen: 'Everyone', state: 'synced', blurb: 'Knows every ship by its sound. Does not know the one that arrived last night.', initials: 'HM', place: 'Harbour' },
    { id: 'imani-roe', name: 'Dr. Imani Roe', kind: 'Character', seen: 'Player note', state: 'waiting', blurb: 'A physician with a lantern she was told to leave on the shelf.', initials: 'IR', place: 'Orbital Station 4' },
    { id: 'tobias-reyes', name: 'Tobias Reyes', kind: 'Character', seen: 'Some characters', state: 'synced', blurb: 'Carries letters he has not delivered.', initials: 'TR', place: 'Old Mill Road' },
    { id: 'orla-venn', name: 'Orla Venn', kind: 'NPC', seen: 'GM only', state: 'conflict', blurb: 'An inspector with one question and a long memory.', initials: 'OV', place: 'Apartment 3B' },
    { id: 'unit-k7', name: 'Unit K-7', kind: 'NPC', seen: 'Everyone', state: 'stale', blurb: 'A maintenance unit that logs everything and reports nothing.', initials: 'K7', place: 'Orbital Station 4' },
    { id: 'aunt-pilar', name: 'Aunt Pilar', kind: 'NPC', seen: 'Everyone', state: 'synced', blurb: 'Keeps the family archive and a spare key.', initials: 'AP', place: 'Apartment 3B' },
    { id: 'the-cartographer', name: 'The cartographer', kind: 'NPC', seen: 'GM only', state: 'synced', blurb: 'Draws what is there and, once a year, what is not.', initials: 'TC', place: 'Harbour' }
  ],
  others: [
    { id: 'orbital-station-4', name: 'Orbital Station 4', kind: 'Place', app: 'Maps', appId: 'maps', route: 'map', blurb: 'A ring-shaped habitat with four docks and one working lift.' },
    { id: 'old-mill-road', name: 'Old Mill Road', kind: 'Place', app: 'Maps', appId: 'maps', route: 'map', blurb: 'A lane between the allotments and the river.' },
    { id: 'map-outer-ring', name: 'Map of the outer ring', kind: 'Map', app: 'Maps', appId: 'maps', route: 'map', blurb: 'Four docks, one lift, one sealed door.' },
    { id: 'lantern', name: 'Lantern of the Third Watch', kind: 'Item', app: 'Inventory', appId: 'inventory', route: 'board', blurb: 'Brass, dented, always warm.' },
    { id: 'brass-compass', name: 'Brass compass', kind: 'Item', app: 'Inventory', appId: 'inventory', route: 'board', blurb: 'Points toward whatever was lost last.' },
    { id: 'chapter-3', name: 'Chapter 3: The blackout', kind: 'Chapter', app: 'Writing', appId: 'writing', route: 'read', blurb: 'The lights went out a little after nineteen forty.' },
    { id: 'manuscripts', name: 'Manuscripts', kind: 'Collection', app: 'Writing', appId: 'writing', route: 'read', blurb: 'Everything written in this library.' },
    { id: 'night-station', name: 'Night on Station 4', kind: 'Session', app: 'Sessions', appId: 'sessions', route: 'home', blurb: 'Thursday 21 March, 19:30.' }
  ],
  inventory: {
    capacity: 120,
    columns: ['Equipped', 'Carried', 'Stored'],
    items: [
      { id: 'i1', name: 'Field jacket', w: 6, col: 0 },
      { id: 'i2', name: 'Lantern', w: 2, col: 0 },
      { id: 'i3', name: 'Short blade', w: 3, col: 0 },
      { id: 'i4', name: 'Rations ×5', w: 10, col: 1 },
      { id: 'i5', name: 'Rope, 15 m', w: 4, col: 1 },
      { id: 'i6', name: 'Repair kit', w: 3, col: 1 },
      { id: 'i7', name: 'Winter coat', w: 8, col: 2 },
      { id: 'i8', name: 'Spare lens', w: 1, col: 2 },
      { id: 'i9', name: 'Letters', w: 1, col: 2 }
    ],
    base: 22
  },
  notifications: [
    { id: 'n1', text: 'Mara Quill asked to move Thursday to Friday.', when: '2 hours ago', unread: true },
    { id: 'n2', text: 'A new player joined Thursday table.', when: 'Yesterday', unread: true },
    { id: 'n3', text: 'Orla Venn was changed by two people at once.', when: 'Yesterday', unread: true }
  ],
  people: [
    { name: 'Dana Okafor', role: 'Owner', you: true },
    { name: 'Mara Quill', role: 'Organizer' },
    { name: 'Tobias Reyes', role: 'Author' }
  ],
  places: [
    { id: 'harbour', name: 'Harbour', x: 140, y: 320 },
    { id: 'outer-ring', name: 'Outer ring', x: 380, y: 210, main: true },
    { id: 'old-mill', name: 'Old Mill Road', x: 590, y: 350 },
    { id: 'station-4', name: 'Station 4', x: 500, y: 130 }
  ],
  sessions: [
    { date: 'Thursday 21 March, 19:30', name: 'Night on Station 4', who: '4 of 5 players confirmed' },
    { date: 'Thursday 28 March, 19:30', name: 'Aftermath', who: 'Not planned yet' }
  ],
  outline: ['1. Arrival', '2. The harbour job', '3. The blackout', '4. Aftermath']
};

/* Icons for tabs in the phone tab bar (names from the brand atlas) */
const TAB_ICONS = { home: 'kind-session', upcoming: 'kind-calendar', scenes: 'kind-scene', notes: 'kind-fact', beings: 'kind-beings', 'beings-mine': 'kind-being', 'beings-updates': 'update-available', board: 'inventory', items: 'kind-items', 'inv-notes': 'kind-fact', map: 'map', locations: 'kind-locations', connections: 'kind-connection', read: 'manuscript', write: 'edit', books: 'kind-books', settings: 'library', profile: 'account', tokens: 'token' };
