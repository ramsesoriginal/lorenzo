/*
 * Made-up beings for the prototype. The shapes follow what apps/beings already reads from the API
 * (ADR 0271/0272): an entry with a main picture, a description (LorenzoScript, here already
 * rendered), tags (bool stats: on, off or inherited), stat groups with typed values that are
 * `own`, inherited from a prototype, or computed by a formula, notes with one of four audiences,
 * the players, and what it owns. Nothing here needs an API change.
 *
 * Five beings on purpose: the same sheet has to serve a 5e-style character, a bare NPC, a heist
 * crew member, a skirmish operative and an author's character who has no numbers at all.
 */
window.BEINGS = [
  {
    id: "brannoch",
    slug: "brannoch-ironweather",
    name: "Brannoch Ironweather",
    kind: "Character",
    library: "The Ashfang Road",
    pictureTone: "blue",
    initials: "BI",
    players: [
      { name: "Dana Okafor", campaign: "The Ashfang Road", owner: true },
    ],
    keywords: ["Dwarf", "Cleric"],
    tags: [
      { label: "Dwarf", state: "inherited", from: "Dwarf" },
      { label: "Blessed", state: "on" },
      { label: "Poisoned", state: "off" },
      { label: "Concentrating", state: "off" },
    ],
    groups: [
      {
        name: "Vitals",
        stats: [
          { label: "Hit points", type: "int", value: 31, adjustable: true },
          { label: "Hit point maximum", type: "int", value: 38 },
          {
            label: "Armour class",
            type: "int",
            value: 15,
            formula: {
              text: "10 + Dexterity modifier + worn armour",
              parts: [
                ["Base", "10"],
                ["Dexterity modifier", "+2"],
                ["Chain shirt (worn)", "+3"],
              ],
            },
          },
          {
            label: "Initiative",
            type: "int",
            value: "+2",
            formula: {
              text: "Dexterity modifier",
              parts: [["Dexterity modifier", "+2"]],
            },
          },
          { label: "Speed", type: "int", value: 25, unit: "ft", from: "Dwarf" },
        ],
      },
      {
        name: "Abilities",
        stats: [
          { label: "Strength", type: "int", value: 16, sub: "+3" },
          { label: "Dexterity", type: "int", value: 14, sub: "+2" },
          {
            label: "Constitution",
            type: "int",
            value: 15,
            sub: "+2",
            from: "Dwarf",
          },
          { label: "Intelligence", type: "int", value: 10, sub: "+0" },
          { label: "Wisdom", type: "int", value: 17, sub: "+3" },
          { label: "Charisma", type: "int", value: 8, sub: "−1" },
        ],
      },
      {
        name: "Character",
        stats: [
          { label: "Level", type: "int", value: 5 },
          {
            label: "Proficiency bonus",
            type: "int",
            value: "+3",
            formula: {
              text: "2 + (level − 1) ÷ 4, rounded down",
              parts: [
                ["Base", "2"],
                ["Level 5", "+1"],
              ],
            },
          },
          { label: "Class", type: "enum", value: "Cleric" },
          {
            label: "Background",
            type: "text",
            value: "Hermit, left the abbey at Thistlemere",
          },
        ],
      },
    ],
    descriptionSource:
      "Brannoch is a **dwarf cleric** of the [[Hearth of Moru]] who left the abbey at [[Thistlemere]] three winters ago.\n\nShe walks the [[Ashfang Road]] with a dented silver symbol and a mace she says she never uses.",
    description: `
      <p>Brannoch is a <strong>dwarf cleric</strong> of the <a href="#" class="entity-link">Hearth of Moru</a> who left the abbey at <a href="#" class="entity-link">Thistlemere</a> three winters ago.</p>
      <p>She walks the <a href="#" class="entity-link">Ashfang Road</a> with a dented silver symbol and a mace she says she never uses. Strangers find her patient. People who know her find her stubborn, usually in the same breath.</p>
      <h4>Manner</h4>
      <ul><li>Counts steps on stairs, out loud, under her breath.</li><li>Will not eat anything she did not watch being cooked.</li></ul>`,
    notes: [
      {
        id: 1,
        label: "Seen by the party",
        audience: "everyone",
        author: "GM",
        body: "<p>Carries a dented silver holy symbol and never lets it out of reach.</p>",
      },
      {
        id: 2,
        label: "Why she left the abbey",
        audience: "player",
        author: "Dana Okafor",
        body: "<p>The abbey burned the night before she was due to take her vows. She still has the key to a door that no longer exists.</p>",
      },
      {
        id: 3,
        label: "What she told Tobias",
        audience: "some",
        to: ["Tobias Reyes", "Mara Quill"],
        author: "Dana Okafor",
        body: "<p>Brannoch suspects the fire was set from inside.</p>",
      },
      {
        id: 4,
        label: "Who set the fire",
        audience: "gm",
        author: "GM",
        body: "<p>Brother Aldric, on the instructions of the Ashfang cult. He is now travelling with the caravan the party joins in chapter 4.</p>",
      },
    ],
    items: [
      { name: "Mace", qty: 1, weight: 4, where: "Equipped", stats: {} },
      { name: "Chain shirt", qty: 1, weight: 20, where: "Equipped", stats: {} },
      {
        name: "Silver holy symbol",
        qty: 1,
        weight: 1,
        where: "Equipped",
        stats: {},
      },
      { name: "Healer's kit", qty: 1, weight: 3, where: "Backpack", stats: {} },
      { name: "Rations", qty: 5, weight: 10, where: "Backpack", stats: {} },
      {
        name: "Hemp rope, 50 ft",
        qty: 1,
        weight: 10,
        where: "Backpack",
        stats: {},
      },
      { name: "Backpack", qty: 1, weight: 5, where: "Equipped", stats: {} },
    ],
    capacity: { label: "Carried weight", value: 53, of: 120, unit: "lb" },
  },

  {
    id: "orla",
    slug: "inspector-orla-venn",
    name: "Inspector Orla Venn",
    kind: "NPC",
    library: "The Gaslight Ledger",
    pictureTone: "ink",
    initials: "OV",
    players: [],
    keywords: ["Official", "Harrow Division"],
    tags: [
      { label: "Official", state: "on" },
      { label: "Armed", state: "off" },
      { label: "Off duty", state: "off" },
    ],
    groups: [
      {
        name: "Disposition",
        stats: [
          { label: "Attitude", type: "enum", value: "Wary" },
          {
            label: "Trust in the party",
            type: "int",
            value: 2,
            sub: "of 5",
            adjustable: true,
          },
          {
            label: "Patience",
            type: "int",
            value: 3,
            sub: "of 5",
            adjustable: true,
          },
        ],
      },
      {
        name: "Standing",
        stats: [
          { label: "Rank", type: "text", value: "Inspector, Harrow Division" },
          { label: "Years in service", type: "int", value: 19 },
          {
            label: "Reach",
            type: "text",
            value: "Can open any police file; cannot open a magistrate's",
          },
        ],
      },
    ],
    descriptionSource:
      "Orla Venn has run the Harrow Division since the winter of the fog…",
    description: `
      <p>Orla Venn has run the Harrow Division since the winter of the fog, and she remembers every name that was in the room.</p>
      <p>She keeps a small grey notebook and writes in it only when someone tells her something that is not true. People have learned to watch her hands.</p>`,
    notes: [
      {
        id: 1,
        label: "Known to dislike",
        audience: "everyone",
        author: "GM",
        body: "<p>Being called “Constable”. Anyone who does so gets the long version of the next question.</p>",
      },
      {
        id: 2,
        label: "What she is really doing",
        audience: "gm",
        author: "GM",
        body: "<p>Has taken money from the Lamplight Guild every month since March. She tells herself it buys her the Guild's silence about her brother.</p><p>If the party shows her the ledger page, she will ask for ten minutes alone with it.</p>",
      },
    ],
    items: [
      {
        name: "Grey notebook",
        qty: 1,
        weight: 0.5,
        where: "Equipped",
        stats: {},
      },
      {
        name: "Police whistle",
        qty: 1,
        weight: 0.1,
        where: "Equipped",
        stats: {},
      },
      {
        name: "Revolver, Harrow pattern",
        qty: 1,
        weight: 2,
        where: "Not carried",
        stats: {},
      },
    ],
  },

  {
    id: "wren",
    slug: "wren-halloran",
    name: "Wren Halloran",
    kind: "Character",
    library: "The Cinderwick Crew",
    pictureTone: "gold",
    initials: "WH",
    players: [
      { name: "Priya Nair", campaign: "The Cinderwick Crew", owner: true },
    ],
    keywords: ["Scoundrel", "Lurk"],
    tags: [
      { label: "Lurk", state: "on" },
      { label: "Vice: obligation", state: "on" },
      { label: "Wanted", state: "off" },
    ],
    groups: [
      {
        name: "Condition",
        stats: [
          {
            label: "Stress",
            type: "int",
            value: 3,
            sub: "of 9",
            adjustable: true,
          },
          {
            label: "Trauma",
            type: "int",
            value: 1,
            sub: "of 4",
            adjustable: true,
          },
          { label: "Harm", type: "text", value: "Level 1: bruised ribs" },
          { label: "Coin", type: "int", value: 2, adjustable: true },
          { label: "Stash", type: "int", value: 14, adjustable: true },
        ],
      },
      {
        name: "Insight",
        stats: [
          { label: "Hunt", type: "int", value: 0 },
          { label: "Study", type: "int", value: 1 },
          { label: "Survey", type: "int", value: 2 },
          { label: "Tinker", type: "int", value: 1 },
        ],
      },
      {
        name: "Prowess",
        stats: [
          { label: "Finesse", type: "int", value: 2 },
          { label: "Prowl", type: "int", value: 3 },
          { label: "Skirmish", type: "int", value: 0 },
          { label: "Wreck", type: "int", value: 0 },
        ],
      },
      {
        name: "Resolve",
        stats: [
          { label: "Attune", type: "int", value: 1 },
          { label: "Command", type: "int", value: 0 },
          { label: "Consort", type: "int", value: 1 },
          { label: "Sway", type: "int", value: 2 },
        ],
      },
    ],
    descriptionSource:
      "Wren grew up above a lamp-oil chandler on Cinderwick Lane…",
    description: `
      <p>Wren grew up above a lamp-oil chandler on Cinderwick Lane and can tell which street she is on by the smell of the gutters.</p>
      <p>She does the quiet part of the job: the roof, the lock, the hour before anyone notices.</p>`,
    notes: [
      {
        id: 1,
        label: "The Vauxhall counting-house",
        audience: "some",
        to: ["Priya Nair", "Jonah Pike", "Sable Ames"],
        author: "Priya Nair",
        body: `<p><strong>Goal:</strong> the Ashworth ledger, not the cash.</p>
          <ol><li>Wren: roof access over the dye works, before the night watch changes.</li><li>Jonah: the side door, with Sable's key copy.</li><li>Sable: keeps the clerk talking at the front.</li><li>Out through the cellar, <em>not</em> the roof.</li></ol>
          <p><strong>Flashback to buy:</strong> the key copy was made last week (1 stress).</p>`,
      },
      {
        id: 2,
        label: "Ghost veil",
        audience: "everyone",
        author: "Priya Nair",
        body: "<p>Once per score, Wren can pass through a solid wall as a ghost for a few seconds.</p>",
      },
      {
        id: 3,
        label: "The obligation",
        audience: "gm",
        author: "GM",
        body: "<p>Her brother's debt is held by the Lampblack Dogs. They will call it in at the end of the next score.</p>",
      },
    ],
    items: [
      { name: "Lockpicks", qty: 1, weight: 1, where: "Equipped", stats: {} },
      { name: "Dark lantern", qty: 1, weight: 1, where: "Equipped", stats: {} },
      { name: "Crowbar", qty: 1, weight: 1, where: "Equipped", stats: {} },
      {
        name: "Rope and grapple",
        qty: 1,
        weight: 1,
        where: "Equipped",
        stats: {},
      },
    ],
    capacity: { label: "Load", value: 4, of: 6, unit: "" },
  },

  {
    id: "kolb",
    slug: "sergeant-imre-kolb",
    name: "Sergeant Imre Kolb",
    kind: "Character",
    library: "Ostrava Line",
    pictureTone: "ink",
    initials: "IK",
    players: [
      { name: "Lukas Brandt", campaign: "Kill team: Cold Sector", owner: true },
    ],
    keywords: ["Leader", "Veteran", "Garrison", "Ostrava Line"],
    tags: [
      { label: "Leader", state: "on" },
      { label: "Veteran", state: "on" },
      { label: "Activated", state: "off" },
      { label: "Injured", state: "off" },
    ],
    groups: [
      {
        name: "Profile",
        stats: [
          { label: "Move", type: "int", value: 6, unit: "in" },
          { label: "Action points", type: "int", value: 3 },
          { label: "Save", type: "text", value: "4+" },
          { label: "Wounds", type: "int", value: 12, adjustable: true },
        ],
      },
    ],
    descriptionSource: "Kolb has held the Cold Sector gate for eleven winters…",
    description: `<p>Kolb has held the Cold Sector gate for eleven winters and counts his people at every dusk, whether or not they are all supposed to be there.</p>`,
    notes: [
      {
        id: 1,
        label: "Rally",
        audience: "everyone",
        author: "Lukas Brandt",
        body: "<p><strong>Once per turning point</strong>, a friendly operative within 6 in. of Kolb may ignore the first wound dealt to it.</p>",
      },
      {
        id: 2,
        label: "Hold the line",
        audience: "everyone",
        author: "Lukas Brandt",
        body: "<p>While Kolb is in cover, enemy operatives cannot use <em>charge</em> against friendly operatives within 3 in. of him.</p>",
      },
    ],
    items: [
      {
        name: "Autorifle",
        qty: 1,
        weight: 0,
        where: "Equipped",
        kind: "Ranged",
        stats: { A: "4", Hit: "3+", Dmg: "3/4", Rules: "Rapid fire 1" },
      },
      {
        name: "Sidearm",
        qty: 1,
        weight: 0,
        where: "Equipped",
        kind: "Ranged",
        stats: { A: "4", Hit: "4+", Dmg: "2/3", Rules: "Range 8 in." },
      },
      {
        name: "Combat blade",
        qty: 1,
        weight: 0,
        where: "Equipped",
        kind: "Melee",
        stats: { A: "3", Hit: "3+", Dmg: "3/4", Rules: "—" },
      },
    ],
  },

  {
    id: "ilse",
    slug: "ilse-quennell",
    name: "Ilse Quennell",
    kind: "NPC",
    library: "The Salt Roads",
    pictureTone: "blue",
    initials: "IQ",
    players: [],
    keywords: ["Cartographer", "Widowed"],
    tags: [
      { label: "Cartographer", state: "on" },
      { label: "Widowed", state: "on" },
    ],
    groups: [],
    descriptionSource: "Ilse Quennell drew the first map of the Salt Roads…",
    description: `
      <p>Ilse Quennell drew the first map of the Salt Roads, and later spent a decade pretending she had not.</p>
      <h4>Before the maps</h4>
      <p>She was a surveyor's assistant in the port of <a href="#" class="entity-link">Marrowgate</a>, paid by the day to hold the far end of a chain. She noticed that the surveyors measured the roads and never the people who walked them, and began to write the second thing down in the margins.</p>
      <blockquote>“A road is a promise that someone will keep walking it.”</blockquote>
      <h4>Why she stopped</h4>
      <p>After the flood season her husband's name was removed from the harbour roll. She stopped signing her maps and started drawing them smaller, so that no one could read the margins without leaning in.</p>
      <h4>In the book</h4>
      <p>She first appears in chapter 3, <a href="#" class="entity-link">The Salt Ledger</a>, and is the reason the courier knows which door to knock on.</p>`,
    notes: [
      {
        id: 1,
        label: "Chapter 12 reveal",
        audience: "gm",
        author: "You",
        body: "<p>She did not sign the maps because the first one was copied from her husband's field book. Do not say so before the flood scene.</p>",
      },
      {
        id: 2,
        label: "Timeline",
        audience: "everyone",
        author: "You",
        body: "<ul><li><strong>Year 1:</strong> assistant at Marrowgate.</li><li><strong>Year 9:</strong> first map of the Salt Roads.</li><li><strong>Year 12:</strong> the flood.</li><li><strong>Year 22:</strong> the book opens.</li></ul>",
      },
    ],
    items: [],
  },
];
