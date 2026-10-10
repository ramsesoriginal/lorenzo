import { describe, expect, it } from 'vitest';
import { Bench } from './bench';
import { compare, inverseOf, sameValue } from './commands';
import { type SampleEntry, SampleTransport } from './sample';
import type { StatDef } from './transport';

const entries: SampleEntry[] = [
  { id: 'a', name: 'Monster', kinds: ['item'], parents: [] },
  { id: 'b', name: 'Beast', kinds: ['item'], parents: ['a'] },
  {
    id: 'c',
    name: 'Wolf',
    kinds: ['item'],
    parents: ['b'],
    description: 'Hunts in packs.',
    notes: [{ id: 'n1', text: 'A ranger note.' }],
  },
  { id: 'p', name: 'The Hollow', kinds: ['being'], parents: [] },
];

const defs: StatDef[] = [
  { id: 'armor', name: 'Armor', type: 'int', enumValues: [] },
  { id: 'magical', name: 'Magical', type: 'bool', enumValues: [] },
  { id: 'size', name: 'Size', type: 'enum', enumValues: ['small', 'medium', 'large'] },
  { id: 'weight', name: 'Weight', type: 'float', enumValues: [] },
];

async function setup() {
  const server = new SampleTransport(entries);
  let n = 0;
  const bench = new Bench(server, () => `new${++n}`);
  await bench.loadEntries();
  await bench.open('c');
  return { server, bench };
}
const settle = async (bench: Bench) => {
  await bench.run();
};

describe('compare', () => {
  it('sends when the server still has the base', () => {
    expect(compare('Wolf', 'Dire wolf', 'Wolf')).toBe('send');
  });
  it('is already there when the server has mine', () => {
    expect(compare('Wolf', 'Dire wolf', 'Dire wolf')).toBe('already');
  });
  it('is a conflict when all three differ', () => {
    expect(compare('Wolf', 'Dire wolf', 'Hound')).toBe('conflict');
  });
  it('compares parents as sets', () => {
    expect(sameValue(['a', 'b'], ['b', 'a'])).toBe(true);
    expect(compare(['a'], ['a', 'b'], ['a'])).toBe('send');
  });
});

describe('the view', () => {
  it('shows a change at once, before it is sent', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Dire wolf');
    expect(bench.view('c')?.name).toBe('Dire wolf');
    expect(bench.displayName('c')).toBe('Dire wolf');
  });
  it('is the mirror with every pending command applied, in order', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    bench.change('entry.set-name', 'c', 'Dire wolf');
    expect(bench.view('c')?.name).toBe('Dire wolf');
    expect(bench.outbox.map((c) => [c.base, c.mine])).toEqual([
      ['Wolf', 'Hound'],
      ['Hound', 'Dire wolf'],
    ]);
  });
  it('changes nothing when nothing changed', async () => {
    const { bench } = await setup();
    expect(bench.change('entry.set-name', 'c', 'Wolf')).toBeNull();
    expect(bench.outbox).toHaveLength(0);
  });
});

describe('the runner', () => {
  it('sends in the order written and ends synced', async () => {
    const { bench, server } = await setup();
    bench.change('entry.set-name', 'c', 'Hound');
    bench.change('entry.set-parents', 'c', ['a']);
    await settle(bench);
    expect(server.writes.map((w) => w.field)).toEqual(['name', 'parents']);
    expect(bench.outbox).toHaveLength(0);
    expect(bench.status('c')).toBe('synced');
    expect(bench.entries.find((e) => e.id === 'c')?.name).toBe('Hound');
  });
  it('keeps commands waiting with no connection, and sends them when it is back', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    await settle(bench);
    expect(bench.status('c')).toBe('offline');
    expect(bench.offline).toBe(true);
    server.offline = false;
    await bench.run();
    expect(bench.status('c')).toBe('synced');
    expect(bench.offline).toBe(false);
  });
  it('stops at a conflict, and what waits behind it on the same entry waits too', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    bench.change('entry.set-parents', 'c', ['a']);
    server.offline = false;
    server.renameElsewhere('c', 'Coyote');
    await bench.run();
    expect(bench.outbox.map((c) => c.state)).toEqual(['conflict', 'waiting']);
    expect(bench.outbox[0].theirs).toBe('Coyote');
    expect(bench.status('c')).toBe('conflict');
    expect(server.writes).toHaveLength(0);
  });
  it('carries on with other entries past a conflict', async () => {
    const { bench, server } = await setup();
    await bench.open('b');
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    bench.change('entry.set-name', 'b', 'Creature');
    server.offline = false;
    server.renameElsewhere('c', 'Coyote');
    await bench.run();
    expect(bench.status('c')).toBe('conflict');
    expect(bench.status('b')).toBe('synced');
  });
  it('keeping mine sends it over theirs; discarding leaves theirs', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    server.offline = false;
    server.renameElsewhere('c', 'Coyote');
    await bench.run();
    bench.keepMine(bench.outbox[0].id);
    await bench.run();
    expect(server.writes).toEqual([{ id: 'c', field: 'name', value: 'Hound' }]);

    const other = await setup();
    other.server.offline = true;
    other.bench.change('entry.set-name', 'c', 'Hound');
    other.server.offline = false;
    other.server.renameElsewhere('c', 'Coyote');
    await other.bench.run();
    other.bench.discard(other.bench.outbox[0].id);
    expect(other.bench.outbox).toHaveLength(0);
    expect(other.server.writes).toHaveLength(0);
  });
  it('a command already done on the server is synced without a write', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    server.offline = false;
    server.renameElsewhere('c', 'Hound');
    await bench.run();
    expect(bench.status('c')).toBe('synced');
    expect(server.writes).toHaveLength(0);
  });
  it('a refused command needs attention with what the server said, and can be retried', async () => {
    const { bench, server } = await setup();
    bench.change('entry.set-parents', 'c', ['c']);
    await settle(bench);
    expect(bench.status('c')).toBe('attention');
    expect(bench.outbox[0].error).toContain('own parent');
    bench.discard(bench.outbox[0].id);
    expect(bench.status('c')).toBe('synced');
    expect(server.writes).toHaveLength(0);
  });
});

describe('undo', () => {
  it('cancels a change that was not sent', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    expect(bench.canUndo('c')).toBe(true);
    bench.undo('c');
    expect(bench.view('c')?.name).toBe('Wolf');
    expect(bench.outbox).toHaveLength(0);
  });
  it('queues the inverse of a change that was sent', async () => {
    const { bench, server } = await setup();
    bench.change('entry.set-name', 'c', 'Hound');
    await settle(bench);
    expect(bench.undo('c')).toBe(true);
    await settle(bench);
    expect(server.writes.map((w) => w.value)).toEqual(['Hound', 'Wolf']);
    expect(bench.view('c')?.name).toBe('Wolf');
  });
  it('has nothing to undo on an entry nobody changed', async () => {
    const { bench } = await setup();
    expect(bench.canUndo('c')).toBe(false);
    expect(bench.undo('c')).toBe(false);
  });
  it('the inverse swaps base and mine', () => {
    expect(
      inverseOf({
        id: 1,
        type: 'entry.set-name',
        version: 1,
        entryId: 'c',
        base: 'a',
        mine: 'b',
        state: 'synced',
      }),
    ).toEqual({ type: 'entry.set-name', entryId: 'c', base: 'b', mine: 'a' });
  });
});

describe('what can be edited', () => {
  it('any kind of entry has a detail, and only an item can be renamed', async () => {
    const { bench } = await setup();
    await bench.open('p');
    expect(bench.view('p')?.kinds).toEqual(['being']);
    bench.change('entry.set-name', 'p', 'The Dell');
    await bench.run();
    expect(bench.status('p')).toBe('attention');
    expect(bench.outbox[0].error).toContain('Only an item');
  });
  it('the parents of a being can be set', async () => {
    const { bench, server } = await setup();
    await bench.open('p');
    bench.change('entry.set-parents', 'p', ['a']);
    await bench.run();
    expect(bench.status('p')).toBe('synced');
    expect(server.writes).toEqual([{ id: 'p', field: 'parents', value: ['a'] }]);
  });
});

describe('creating an entry', () => {
  const draft = { name: 'Dire wolf', kinds: ['item'], parents: ['c'] };

  it('shows at once, in the list and under its parent, before it is sent', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.create(draft);
    expect(bench.listing().map((e) => e.name)).toContain('Dire wolf');
    expect(bench.view(id)).toMatchObject({ name: 'Dire wolf', kinds: ['item'], parentIds: ['c'] });
    expect(bench.childrenOf('c')).toEqual([id]);
    expect(bench.status(id)).toBe('waiting');
  });

  it('is sent under the id the client made, with its kinds and parents', async () => {
    const { bench, server } = await setup();
    const id = bench.create(draft);
    await bench.run();
    expect(id).toBe('new1');
    expect(server.writes).toEqual([{ id, field: 'create', value: 'Dire wolf' }]);
    expect(bench.status(id)).toBe('synced');
    expect((await server.getEntry(id)).parentIds).toEqual(['c']);
    expect(bench.entries.map((e) => e.id)).toContain(id);
    expect(bench.childrenOf('c')).toEqual([id]);
  });

  it('a being and a bare entry can be made too', async () => {
    const { bench, server } = await setup();
    const being = bench.create({ name: 'Ashfang', kinds: ['being'], parents: [] });
    const bare = bench.create({ name: 'Groups', kinds: [], parents: [] });
    await bench.run();
    expect((await server.getEntry(being)).kinds).toEqual(['being']);
    expect((await server.getEntry(bare)).kinds).toEqual([]);
  });

  it('what is done to a new entry waits for it, and goes after it, in order', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.create(draft);
    bench.change('entry.set-name', id, 'Dire hound');
    bench.change('entry.set-parents', id, ['c', 'a']);
    server.offline = false;
    await bench.run();
    expect(server.writes.map((w) => w.field)).toEqual(['create', 'name', 'parents']);
    expect(await server.getEntry(id)).toMatchObject({ name: 'Dire hound', parentIds: ['c', 'a'] });
    expect(bench.outbox).toHaveLength(0);
  });

  it('an entry under one that is not made yet waits for it', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const parent = bench.create({ name: 'Pack', kinds: ['item'], parents: [] });
    const child = bench.create({ name: 'Pup', kinds: ['item'], parents: [parent] });
    server.offline = false;
    await bench.run();
    expect(server.writes.map((w) => w.value)).toEqual(['Pack', 'Pup']);
    expect((await server.getEntry(child)).parentIds).toEqual([parent]);
  });

  it('when the parent is stuck, the child waits and the rest carries on', async () => {
    const { bench, server } = await setup();
    server.heldElsewhere.add('new1');
    const parent = bench.create({ name: 'Pack', kinds: ['item'], parents: [] });
    const child = bench.create({ name: 'Pup', kinds: ['item'], parents: [parent] });
    await bench.open('b');
    bench.change('entry.set-name', 'b', 'Creature');
    await bench.run();
    expect(bench.status(parent)).toBe('attention');
    expect(bench.outbox.find((c) => c.entryId === parent)?.error).toBe('That id is not available.');
    expect(bench.commandsFor(child)[0].state).toBe('waiting');
    expect(bench.status('b')).toBe('synced');
    // giving the parent up takes the child with it
    bench.discard(bench.outbox.find((c) => c.entryId === parent)!.id);
    expect(bench.outbox).toHaveLength(0);
  });

  it('cancelling a create that was not sent cancels what waits on it', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.create(draft);
    bench.change('entry.set-name', id, 'Hound');
    const child = bench.create({ name: 'Pup', kinds: ['item'], parents: [id] });
    const first = bench.outbox[0].id;
    bench.cancel(first);
    expect(bench.outbox).toHaveLength(0);
    expect(bench.view(id)).toBeNull();
    expect(bench.view(child)).toBeNull();
  });

  it('an undo cancels a waiting create, and cannot delete one that was sent', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.create(draft);
    expect(bench.canUndo(id)).toBe(true);
    bench.undo(id);
    expect(bench.listing().map((e) => e.name)).not.toContain('Dire wolf');

    server.offline = false;
    const sent = bench.create(draft);
    await bench.run();
    expect(bench.canUndo(sent)).toBe(false);
    expect(bench.undo(sent)).toBe(false);
  });

  it('a create the server already has is a replay: synced, no second write', async () => {
    const { bench, server } = await setup();
    await server.createEntry({ id: 'new1', name: 'Dire wolf', kinds: ['item'], parents: ['c'] });
    server.writes.length = 0;
    bench.create(draft);
    await bench.run();
    expect(bench.status('new1')).toBe('synced');
    expect(server.writes).toEqual([]);
  });

  it('with no connection it stays waiting, and is sent when the connection is back', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.create(draft);
    await bench.run();
    expect(bench.status(id)).toBe('offline');
    server.offline = false;
    await bench.run();
    expect(bench.status(id)).toBe('synced');
  });
});

describe('description and notes', () => {
  it('the description shows at once, and goes to the server on the same payload', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.setDescription('c', 'Hunts in **packs**, at night.');
    expect(bench.view('c')?.description?.text).toBe('Hunts in **packs**, at night.');
    server.offline = false;
    await bench.run();
    expect(server.writes).toEqual([
      { id: 'c-description', field: 'description', value: 'Hunts in **packs**, at night.' },
    ]);
    expect(bench.status('c')).toBe('synced');
  });

  it('an entry without a description gets one, made under an id of the client', async () => {
    const { bench, server } = await setup();
    await bench.open('b');
    bench.setDescription('b', 'The beast.');
    await bench.run();
    expect(server.writes).toEqual([{ id: 'b', field: 'description', value: 'The beast.' }]);
    expect(bench.view('b')?.description).toMatchObject({ id: 'new1', text: 'The beast.' });
    // and the next change writes to it, not to a second one
    bench.setDescription('b', 'The beast, again.');
    await bench.run();
    expect(server.writes.at(-1)).toEqual({
      id: 'new1',
      field: 'description',
      value: 'The beast, again.',
    });
  });

  it('two changes to a description not there yet make it once, and write the second', async () => {
    const { bench, server } = await setup();
    await bench.open('b');
    server.offline = true;
    bench.setDescription('b', 'One.');
    bench.setDescription('b', 'Two.');
    server.offline = false;
    await bench.run();
    expect(server.writes.map((w) => [w.field, w.value])).toEqual([
      ['description', 'One.'],
      ['description', 'Two.'],
    ]);
  });

  it('a description changed elsewhere is a conflict, and keeping mine sends it', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.setDescription('c', 'Mine.');
    server.offline = false;
    server.editTextElsewhere('c', 'description', 'Theirs.');
    await bench.run();
    expect(bench.status('c')).toBe('conflict');
    expect(bench.outbox[0].theirs).toBe('Theirs.');
    expect(server.writes).toEqual([]);
    bench.keepMine(bench.outbox[0].id);
    await bench.run();
    expect(server.writes.at(-1)).toMatchObject({ field: 'description', value: 'Mine.' });
  });

  it('a note is added at once, under an id of the client, and sent', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.addNote('c', 'Check the den.');
    expect(bench.view('c')?.notes.map((n) => n.text)).toEqual(['A ranger note.', 'Check the den.']);
    server.offline = false;
    await bench.run();
    expect(server.writes).toEqual([{ id: 'c', field: 'note.add', value: 'Check the den.' }]);
    expect((await server.getEntry('c')).notes.map((n) => n.id)).toEqual(['n1', id]);
  });

  it('a note edited before it was sent goes after it', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.addNote('c', 'Draft.') as string;
    bench.setNoteText('c', id, 'Final.');
    server.offline = false;
    await bench.run();
    expect(server.writes.map((w) => [w.field, w.value])).toEqual([
      ['note.add', 'Draft.'],
      ['note.text', 'Final.'],
    ]);
  });

  it('cancelling a note that was not sent takes its edits with it', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    const id = bench.addNote('c', 'Draft.') as string;
    bench.setNoteText('c', id, 'Final.');
    bench.cancel(bench.outbox[0].id);
    expect(bench.outbox).toHaveLength(0);
    expect(bench.view('c')?.notes.map((n) => n.id)).toEqual(['n1']);
  });

  it('a note that was sent is not undone here, but an edit of one is', async () => {
    const { bench, server } = await setup();
    const id = bench.addNote('c', 'Draft.') as string;
    await bench.run();
    expect(bench.canUndo('c')).toBe(false);
    bench.setNoteText('c', id, 'Final.');
    await bench.run();
    expect(bench.canUndo('c')).toBe(true);
    bench.undo('c');
    await bench.run();
    expect(server.writes.map((w) => w.value)).toEqual(['Draft.', 'Final.', 'Draft.']);
  });

  it('a note edited elsewhere is a conflict; one that is gone needs attention', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.setNoteText('c', 'n1', 'Mine.');
    server.offline = false;
    server.editTextElsewhere('c', 'n1', 'Theirs.');
    await bench.run();
    expect(bench.status('c')).toBe('conflict');
    bench.discard(bench.outbox[0].id);
    expect(bench.view('c')?.notes[0].text).toBe('Theirs.');
  });

  it('an empty note is not added', async () => {
    const { bench } = await setup();
    expect(bench.addNote('c', '   ')).toBeNull();
    expect(bench.outbox).toHaveLength(0);
  });

  it('a note id the server refuses needs attention, and what waits on it waits', async () => {
    const { bench, server } = await setup();
    server.heldElsewhere.add('new1');
    const id = bench.addNote('c', 'Draft.') as string;
    bench.setNoteText('c', id, 'Final.');
    await bench.run();
    expect(bench.outbox.map((c) => c.state)).toEqual(['attention', 'waiting']);
    bench.discard(bench.outbox[0].id);
    expect(bench.outbox).toHaveLength(0);
  });
});

describe('stats', () => {
  async function withStats() {
    const server = new SampleTransport(
      entries.map((e) => (e.id === 'b' ? { ...e, stats: { armor: 12 } } : e)),
      defs,
    );
    const bench = new Bench(server, () => 'x');
    await bench.loadEntries();
    await bench.open('b');
    await bench.open('c');
    return { server, bench };
  }
  const stat = (bench: Bench, id: string, statId: string) =>
    bench.view(id)?.stats.find((x) => x.statId === statId);

  it('reads the definitions, and an inherited value is not own', async () => {
    const { bench } = await withStats();
    expect(bench.statDefs.map((d) => d.id)).toEqual(['armor', 'magical', 'size', 'weight']);
    expect(stat(bench, 'c', 'armor')).toMatchObject({ value: 12, own: false });
    expect(stat(bench, 'b', 'armor')).toMatchObject({ value: 12, own: true });
  });

  it('shows an own value at once, and writes it', async () => {
    const { bench, server } = await withStats();
    server.offline = true;
    bench.setStat('c', 'armor', 14);
    expect(stat(bench, 'c', 'armor')).toMatchObject({ value: 14, own: true });
    server.offline = false;
    await bench.run();
    expect(server.writes).toEqual([{ id: 'c', field: 'stat:armor', value: 14 }]);
    expect(bench.status('c')).toBe('synced');
    expect(stat(bench, 'c', 'armor')).toMatchObject({ value: 14, own: true });
  });

  it('a tag is a bool stat: on, then off', async () => {
    const { bench, server } = await withStats();
    bench.setStat('c', 'magical', true);
    await bench.run();
    bench.setStat('c', 'magical', false);
    await bench.run();
    expect(server.writes.map((w) => w.value)).toEqual([true, false]);
  });

  it('undoes a write exactly: the old own value, or none', async () => {
    const { bench, server } = await withStats();
    bench.setStat('b', 'armor', 15);
    await bench.run();
    expect(bench.undo('b')).toBe(true);
    await bench.run();
    expect(stat(bench, 'b', 'armor')).toMatchObject({ value: 12, own: true });
    bench.setStat('c', 'armor', 9);
    await bench.run();
    bench.undo('c');
    await bench.run();
    // The undo of a first value is clearing it: the entry inherits again.
    expect(stat(bench, 'c', 'armor')).toMatchObject({ value: 12, own: false });
    expect(server.writes.at(-1)).toEqual({ id: 'c', field: 'stat:armor', value: null });
  });

  it('removing an own value makes the entry inherit', async () => {
    const { bench, server } = await withStats();
    bench.setStat('b', 'armor', null);
    expect(stat(bench, 'b', 'armor')).toMatchObject({ own: false });
    await bench.run();
    expect(server.writes).toEqual([{ id: 'b', field: 'stat:armor', value: null }]);
  });

  it('writes nothing when nothing changes', async () => {
    const { bench } = await withStats();
    expect(bench.setStat('b', 'armor', 12)).toBeNull();
    expect(bench.setStat('c', 'armor', null)).toBeNull();
  });

  it('does not edit a float yet, nor a stat that is not defined', async () => {
    const { bench } = await withStats();
    expect(bench.setStat('c', 'weight', 3)).toBeNull();
    expect(bench.setStat('c', 'nothing', 3)).toBeNull();
  });

  it('is a conflict when the stat was changed elsewhere', async () => {
    const { bench, server } = await withStats();
    server.offline = true;
    bench.setStat('b', 'armor', 15);
    server.setStatElsewhere('b', 'armor', 18);
    server.offline = false;
    await bench.run();
    const [cmd] = bench.outbox;
    expect(cmd).toMatchObject({ state: 'conflict', theirs: 18, base: 12, mine: 15 });
    bench.keepMine(cmd.id);
    await bench.run();
    expect(server.writes.at(-1)).toEqual({ id: 'b', field: 'stat:armor', value: 15 });
  });

  it('is already there when the server has the same value', async () => {
    const { bench, server } = await withStats();
    server.offline = true;
    bench.setStat('b', 'armor', 15);
    server.setStatElsewhere('b', 'armor', 15);
    server.offline = false;
    await bench.run();
    expect(server.writes).toEqual([]);
    expect(bench.status('b')).toBe('synced');
  });

  it('keeps an enum to its values', async () => {
    const { bench } = await withStats();
    bench.setStat('c', 'size', 'huge');
    await bench.run();
    expect(bench.status('c')).toBe('attention');
    expect(bench.outbox[0].error).toMatch(/enum value for Size/);
  });
});

describe('kinds', () => {
  const kind = (bench: Bench, id: string) => bench.view(id)?.kinds;

  it('gives an entry a kind at once, and writes it', async () => {
    const { bench, server } = await setup();
    await bench.open('p');
    bench.setKind('p', 'item', true);
    expect(kind(bench, 'p')).toEqual(['item', 'being']);
    expect(bench.listing().find((e) => e.id === 'p')?.kinds).toEqual(['item', 'being']);
    await settle(bench);
    expect(server.writes).toEqual([{ id: 'p', field: 'kind:item', value: true }]);
    expect(bench.status('p')).toBe('synced');
  });

  it('takes a kind away, so the entry may become a bare entry, and undoes it', async () => {
    const { bench, server } = await setup();
    await bench.open('p');
    bench.setKind('p', 'being', false);
    await settle(bench);
    expect(kind(bench, 'p')).toEqual([]);
    expect(bench.undo('p')).toBe(true);
    await settle(bench);
    expect(kind(bench, 'p')).toEqual(['being']);
    expect(server.writes.map((w) => w.value)).toEqual([false, true]);
  });

  it('writes nothing when the entry already is that', async () => {
    const { bench } = await setup();
    await bench.open('p');
    expect(bench.setKind('p', 'being', true)).toBeNull();
  });

  it('is already there when someone else made the same change (a yes or no cannot conflict)', async () => {
    const { bench, server } = await setup();
    await bench.open('p');
    server.offline = true;
    bench.setKind('p', 'being', false);
    server.offline = false;
    server.setKindElsewhere('p', 'being', false);
    await settle(bench);
    // the server already has what was asked: nothing to send
    expect(bench.status('p')).toBe('synced');
    expect(server.writes).toEqual([]);
  });

  it('is refused for an inventory item taking item', async () => {
    const server = new SampleTransport([
      { id: 'x', name: 'Sword #1', kinds: ['item_instance'], parents: [] },
    ]);
    const bench = new Bench(server, () => 'n');
    await bench.loadEntries();
    await bench.open('x');
    bench.setKind('x', 'item', true);
    await settle(bench);
    expect(bench.status('x')).toBe('attention');
    expect(bench.outbox[0].error).toMatch(/inventory item/);
  });

  it('lists where entries are: the parents the server says, then the ones just set', async () => {
    const { bench } = await setup();
    expect(bench.listing().find((e) => e.id === 'c')?.parentIds).toEqual(['b']);
    await bench.open('c');
    bench.change('entry.set-parents', 'c', ['a', 'b']);
    expect(bench.listing().find((e) => e.id === 'c')?.parentIds).toEqual(['a', 'b']);
    await settle(bench);
    expect(bench.entries.find((e) => e.id === 'c')?.parentIds).toEqual(['a', 'b']);
  });
});

describe('what is not sent', () => {
  it('lists the changes not sent, by entry, and gives them up', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.change('entry.set-name', 'c', 'Hound');
    bench.setDescription('c', 'Barks.');
    bench.create({ name: 'Pup', kinds: ['item'], parents: ['c'] });
    expect(bench.unsent()).toEqual([
      { id: 'c', name: 'Hound', count: 2 },
      { id: 'new1', name: 'Pup', count: 1 },
    ]);
    await bench.discardUnsent();
    expect(bench.unsent()).toEqual([]);
    expect(bench.view('c')?.name).toBe('Wolf');
    expect(server.writes).toEqual([]);
  });

  it('has nothing to list once it is sent', async () => {
    const { bench } = await setup();
    bench.change('entry.set-name', 'c', 'Hound');
    await settle(bench);
    expect(bench.unsent()).toEqual([]);
  });
});

describe('link names', () => {
  it('makes a new entry with the link name its name makes', async () => {
    const { bench, server } = await setup();
    const id = bench.create({ name: 'Old Sword', kinds: ['item'], parents: [] });
    expect(bench.view(id)?.slug).toBe('old-sword');
    await settle(bench);
    expect((await server.getEntry(id)).slug).toBe('old-sword');
    expect((await server.resolveSlugs(['old-sword']))[0]?.id).toBe(id);
  });

  it('makes an entry without one when its name makes none, or another entry has it', async () => {
    const { bench, server } = await setup();
    const plain = bench.create({ name: '日本', kinds: [], parents: [] });
    const clash = bench.create({ name: 'Wolf', kinds: ['item'], parents: [] }); // c is "Wolf"
    await settle(bench);
    expect((await server.getEntry(plain)).slug).toBeNull();
    expect((await server.getEntry(clash)).slug).toBeNull();
  });

  it('sets, clears and undoes a link name', async () => {
    const { bench, server } = await setup();
    bench.setSlug('c', 'hound');
    expect(bench.view('c')?.slug).toBe('hound');
    await settle(bench);
    expect((await server.getEntry('c')).slug).toBe('hound');
    bench.undo('c');
    await settle(bench);
    expect((await server.getEntry('c')).slug).toBe('wolf');
    bench.setSlug('c', null);
    await settle(bench);
    expect((await server.getEntry('c')).slug).toBeNull();
  });

  it('does not write a link name the API would refuse, or the same one again', async () => {
    const { bench } = await setup();
    expect(bench.setSlug('c', 'two words')).toBeNull();
    expect(bench.setSlug('c', '-lead')).toBeNull();
    expect(bench.setSlug('c', 'wolf')).toBeNull();
  });

  it('is Needs attention when another entry has the link name', async () => {
    const { bench } = await setup();
    bench.setSlug('c', 'monster'); // a's
    await settle(bench);
    expect(bench.status('c')).toBe('attention');
    expect(bench.outbox[0].error).toMatch(/already in use/);
  });

  it('is a conflict when it was changed elsewhere to something else', async () => {
    const { bench, server } = await setup();
    server.offline = true;
    bench.setSlug('c', 'hound');
    server.setSlugElsewhere('c', 'lupus');
    server.offline = false;
    await settle(bench);
    expect(bench.outbox[0]).toMatchObject({
      state: 'conflict',
      theirs: 'lupus',
      base: 'wolf',
      mine: 'hound',
    });
  });
});
