import { describe, expect, it } from 'vitest';
import { Bench } from './bench';
import { compare, inverseOf, sameValue } from './commands';
import { type SampleEntry, SampleTransport } from './sample';

const entries: SampleEntry[] = [
  { id: 'a', name: 'Monster', kinds: ['item'], parents: [] },
  { id: 'b', name: 'Beast', kinds: ['item'], parents: ['a'] },
  { id: 'c', name: 'Wolf', kinds: ['item'], parents: ['b'] },
  { id: 'p', name: 'The Hollow', kinds: ['being'], parents: [] },
];

async function setup() {
  const server = new SampleTransport(entries);
  const bench = new Bench(server);
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
  it('only items have a detail to edit', async () => {
    const { bench } = await setup();
    expect(bench.isItem('c')).toBe(true);
    expect(bench.isItem('p')).toBe(false);
    await bench.open('p');
    expect(bench.view('p')).toBeNull();
  });
});
