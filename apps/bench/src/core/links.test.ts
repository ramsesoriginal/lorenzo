import { describe, expect, it } from 'vitest';
import { entryHref, entryIdOfHref, LinkResolver } from './links';
import { SampleTransport } from './sample';

const entries = [
  { id: 'a', name: 'Old Sword', kinds: ['item'], parents: [] },
  { id: 'b', name: 'Ashfang', kinds: ['being'], parents: [] },
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
    const { html } = await links.render('See [[Old Sword]] and [the dog](ashfang).');
    expect(html).toContain(`href="${entryHref('a')}"`);
    expect(html).toContain(`href="${entryHref('b')}"`);
    expect(html).toContain('title="Old Sword"');
    expect(html).toContain('class="ls-entity"');
  });

  it('leaves a link nothing holds as plain text, and says which', async () => {
    const { links } = setup();
    const out = await links.render('A [[Lost Crown]] and [[Old Sword]].');
    expect(out.html).not.toContain('Lost Crown</a>');
    expect(out.html).toContain('Lost Crown');
    expect(out.missing).toEqual(['lost-crown']);
  });

  it('asks about each name once, then from memory', async () => {
    const { links, asked } = setup();
    await links.render('[[Old Sword]] [[Old Sword]] [[Lost Crown]]');
    await links.render('[[Old Sword]] [[Lost Crown]] [[Ashfang]]');
    expect(asked).toEqual([['old-sword', 'lost-crown'], ['ashfang']]);
  });

  it('asks again about a name nothing held, after a while', async () => {
    const { links, asked, tick } = setup();
    await links.render('[[Lost Crown]]');
    tick(10_000);
    await links.render('[[Lost Crown]]');
    expect(asked).toHaveLength(1);
    tick(25_000);
    await links.render('[[Lost Crown]]');
    expect(asked).toHaveLength(2);
  });

  it('asks 100 names at a time', async () => {
    const { links, asked } = setup();
    const text = Array.from({ length: 250 }, (_, i) => `[[N ${i}]]`).join(' ');
    await links.render(text);
    expect(asked.map((a) => a.length)).toEqual([100, 100, 50]);
  });

  it('shows the text without links when there is no connection, and tries again later', async () => {
    const { links, server } = setup();
    server.offline = true;
    const offline = await links.render('[[Old Sword]]');
    expect(offline.html).toContain('Old Sword');
    expect(offline.html).not.toContain('<a');
    expect(offline.missing).toEqual([]);
    server.offline = false;
    expect((await links.render('[[Old Sword]]')).html).toContain('<a');
  });

  it('names an entry by its place in the page, and back', () => {
    expect(entryIdOfHref(entryHref('abc-1'))).toBe('abc-1');
    expect(entryIdOfHref('https://example.com')).toBeNull();
    expect(entryIdOfHref(null)).toBeNull();
  });
});
