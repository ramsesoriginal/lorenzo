import { describe, expect, it } from 'vitest';
import { entryHref, entryIdOfHref, LinkResolver } from './links';
import { SampleTransport } from './sample';

const entries = [
  { id: 'a', name: 'Old Sword', kinds: ['item'], parents: [] },
  { id: 'b', name: 'Ashfang', kinds: ['being'], parents: [], picture: '#a33' },
];

function setup() {
  const server = new SampleTransport(entries);
  const asked: string[][] = [];
  const spy = server.resolveSlugs.bind(server);
  server.resolveSlugs = async (slugs) => {
    asked.push([...slugs]);
    return spy(slugs);
  };
  let clock = 0;
  return {
    server,
    asked,
    links: new LinkResolver(server, () => clock),
    tick: (ms: number) => (clock += ms),
  };
}

describe('entry links', () => {
  it('resolves [[Name]] and [text](slug) to the entry, titled with its name', async () => {
    const { links } = setup();
    const { html } = await links.render('See [[Old Sword]] and [the dog](ashfang).', 'home');
    expect(html).toContain(`href="${entryHref('a')}"`);
    expect(html).toContain(`href="${entryHref('b')}"`);
    expect(html).toContain('title="Old Sword"');
    expect(html).toContain('class="ls-entity"');
  });

  it('leaves a link nothing holds as plain text, and says which', async () => {
    const { links } = setup();
    const out = await links.render('A [[Lost Crown]] and [[Old Sword]].', 'home');
    expect(out.html).not.toContain('Lost Crown</a>');
    expect(out.html).toContain('Lost Crown');
    expect(out.missing).toEqual(['lost-crown']);
  });

  it('asks about each name once, then from memory', async () => {
    const { links, asked } = setup();
    await links.render('[[Old Sword]] [[Old Sword]] [[Lost Crown]]', 'home');
    await links.render('[[Old Sword]] [[Lost Crown]] [[Ashfang]]', 'home');
    expect(asked).toEqual([['old-sword', 'lost-crown'], ['ashfang']]);
  });

  it('asks again about a name nothing held, after a while', async () => {
    const { links, asked, tick } = setup();
    await links.render('[[Lost Crown]]', 'home');
    tick(10_000);
    await links.render('[[Lost Crown]]', 'home');
    expect(asked).toHaveLength(1);
    tick(25_000);
    await links.render('[[Lost Crown]]', 'home');
    expect(asked).toHaveLength(2);
  });

  it('asks 100 names at a time', async () => {
    const { links, asked } = setup();
    const text = Array.from({ length: 250 }, (_, i) => `[[N ${i}]]`).join(' ');
    await links.render(text, 'home');
    expect(asked.map((a) => a.length)).toEqual([100, 100, 50]);
  });

  it('shows the text without links when there is no connection, and tries again later', async () => {
    const { links, server } = setup();
    server.offline = true;
    const offline = await links.render('[[Old Sword]]', 'home');
    expect(offline.html).toContain('Old Sword');
    expect(offline.html).not.toContain('<a');
    expect(offline.missing).toEqual([]);
    server.offline = false;
    expect((await links.render('[[Old Sword]]', 'home')).html).toContain('<a');
  });

  it('names an entry by its place in the page, and back', () => {
    expect(entryIdOfHref(entryHref('abc-1'))).toBe('abc-1');
    expect(entryIdOfHref('https://example.com')).toBeNull();
    expect(entryIdOfHref(null)).toBeNull();
  });
});

describe('pictures in text', () => {
  it('shows ![alt](slug) as the main picture of the entry', async () => {
    const { links } = setup();
    const { html } = await links.render('Here: ![the dog](ashfang)', 'home');
    expect(html).toMatch(/<img src="blob:[^"]+" alt="the dog" title="Ashfang"/);
  });

  it('shows the alt text when the entry has no picture, or nothing holds the name', async () => {
    const { links } = setup();
    const out = await links.render('![a sword](old-sword) and ![nothing](lost)', 'home');
    expect(out.html).not.toContain('<img');
    expect(out.html).toContain('a sword');
  });

  it('shows nothing yet in the instant render, then the picture once fetched', async () => {
    const { links } = setup();
    expect(links.renderNow('![dog](ashfang)', 'home').html).not.toContain('<img');
    await links.render('![dog](ashfang)', 'home');
    expect(links.renderNow('![dog](ashfang)', 'home').html).toContain('<img');
  });

  it('fetches each picture once, and only for images (not for links)', async () => {
    const { links, server } = setup();
    await links.render('[[Ashfang]]', 'home');
    expect(server.pictureReads).toEqual([]);
    await links.render('![a](ashfang) ![b](ashfang)', 'home');
    await links.render('![c](ashfang)', 'home');
    expect(server.pictureReads).toEqual(['b']);
  });

  it('keeps the text when a picture cannot be fetched, and tries again next time', async () => {
    const { links, server } = setup();
    const real = server.pictureOf.bind(server);
    let fail = true;
    server.pictureOf = async (id) => {
      if (fail) throw new Error('down');
      return real(id);
    };
    expect((await links.render('![dog](ashfang)', 'home')).html).not.toContain('<img');
    fail = false;
    expect((await links.render('![dog](ashfang)', 'home')).html).toContain('<img');
  });
});

describe('my/ links', () => {
  const world = [
    { id: 'sword', name: 'Longsword', kinds: ['item'], parents: [] },
    { id: 'stone', name: 'Whetstone', kinds: ['item'], parents: [] },
    { id: 'aldras', name: 'Aldras', kinds: ['being'], parents: [] },
    { id: 'bryn', name: 'Bryn', kinds: ['being'], parents: [] },
    {
      id: 'blade',
      name: 'Aldras blade',
      kinds: ['item_instance'],
      parents: ['sword'],
      heldBy: 'aldras',
    },
    {
      id: 'bryn-blade',
      name: 'Bryn blade',
      kinds: ['item_instance'],
      parents: ['sword'],
      heldBy: 'bryn',
    },
    {
      id: 'aldras-stone',
      name: 'Aldras stone',
      kinds: ['item_instance'],
      parents: ['stone'],
      heldBy: 'aldras',
    },
    { id: 'rock', name: 'Loose rock', kinds: ['item_instance'], parents: [] },
  ];
  const mine = () => {
    const server = new SampleTransport(world);
    const asked: { slugs: string[]; from?: string }[] = [];
    const spy = server.resolveSlugs.bind(server);
    server.resolveSlugs = async (slugs, from) => {
      asked.push({ slugs: [...slugs], from });
      return spy(slugs, from);
    };
    let clock = 0;
    return {
      asked,
      links: new LinkResolver(server, () => clock),
      tick: (ms: number) => (clock += ms),
    };
  };

  it('means the instance the entry the text belongs to holds, and asks with that entry', async () => {
    const { links, asked } = mine();
    const { html } = await links.render('She draws [[my/Longsword]].', 'aldras');
    expect(html).toContain(`href="${entryHref('blade')}"`);
    expect(html).toContain('title="Aldras blade"');
    expect(asked).toEqual([{ slugs: ['my/longsword'], from: 'aldras' }]);
  });

  it('is a different sword in another being’s text, and from something the being holds', async () => {
    const { links } = mine();
    const bryn = await links.render('[[my/Longsword]]', 'bryn');
    const fromStone = await links.render('[[my/Longsword]]', 'aldras-stone');
    expect(bryn.html).toContain(entryHref('bryn-blade'));
    expect(fromStone.html).toContain(entryHref('blade'));
  });

  it('keeps plain and my/ links apart in one text, in two requests', async () => {
    const { links, asked } = mine();
    const { html } = await links.render('[[Longsword]] and [[my/Longsword]]', 'aldras');
    expect(html).toContain(entryHref('sword'));
    expect(html).toContain(entryHref('blade'));
    expect(asked).toEqual([
      { slugs: ['longsword'], from: undefined },
      { slugs: ['my/longsword'], from: 'aldras' },
    ]);
  });

  it('stays text, and says so apart from a missing name, when nothing is held', async () => {
    const { links } = mine();
    const out = await links.render('[[my/Longsword]] and [[Lost Crown]]', 'rock');
    expect(out.html).not.toContain('<a');
    expect(out.notMine).toEqual(['longsword']);
    expect(out.missing).toEqual(['lost-crown']);
  });

  it('shows a picture of the held instance for ![alt](my/slug)', async () => {
    const server = new SampleTransport(
      world.map((e) => (e.id === 'blade' ? { ...e, picture: '#a33' } : e)),
    );
    const out = await new LinkResolver(server).render('![blade](my/longsword)', 'aldras');
    expect(out.html).toMatch(/<img src="blob:[^"]+" alt="blade"/);
  });

  it('asks again after a while, since who holds what changes', async () => {
    const { links, asked, tick } = mine();
    await links.render('[[my/Longsword]]', 'aldras');
    tick(10_000);
    await links.render('[[my/Longsword]]', 'aldras');
    expect(asked).toHaveLength(1);
    tick(25_000);
    await links.render('[[my/Longsword]]', 'aldras');
    expect(asked).toHaveLength(2);
  });

  it('remembers a my/ answer per entry, not per name', async () => {
    const { links, asked } = mine();
    await links.render('[[my/Longsword]]', 'aldras');
    await links.render('[[my/Longsword]]', 'bryn');
    expect(asked.map((a) => a.from)).toEqual(['aldras', 'bryn']);
  });
});
