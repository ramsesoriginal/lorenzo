// @vitest-environment jsdom
import type { LorenzoClient } from '@lorenzo/api-client';
import { describe, expect, it, vi } from 'vitest';
import { renderFactsAbout } from '../src/Facts';
import { renderLibraryList } from '../src/LibraryList';

const libraryMarkup = `<section data-library-list hidden>
  <p data-loading></p><p data-empty hidden></p><p data-error hidden></p><ul data-list></ul>
  <template data-library-template>
    <li><a data-link><strong data-name></strong><span data-kind hidden></span><span data-role></span></a></li>
  </template>
</section>`;

const library = (id: string, kind = 'play') =>
  ({ id, name: `Library ${id}`, role: 'gm', kind }) as never;

function libraryRoot() {
  document.body.innerHTML = libraryMarkup;

  return document.querySelector<HTMLElement>('[data-library-list]') as HTMLElement;
}

describe('renderLibraryList', () => {
  it('links each library to where the app starts in it', async () => {
    const root = libraryRoot();
    const remember = vi.fn();

    await renderLibraryList(
      {
        list: async () => ({ items: [library('a'), library('b', 'test')] }),
        remember,
        href: (id) => `/beings/?tenant=${id}`,
      },
      root,
    ).load();

    const links = [...root.querySelectorAll<HTMLAnchorElement>('[data-link]')];

    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/beings/?tenant=a',
      '/beings/?tenant=b',
    ]);
    expect(root.querySelectorAll('[data-kind]:not([hidden])')).toHaveLength(1);
    expect(remember).not.toHaveBeenCalled();
  });

  it('says so when there is none', async () => {
    const root = libraryRoot();

    await renderLibraryList(
      { list: async () => ({ items: [] }), remember: vi.fn(), href: String },
      root,
    ).load();

    expect(root.querySelector<HTMLElement>('[data-empty]')?.hidden).toBe(false);
  });

  it('remembers the one library there is and opens it', async () => {
    const root = libraryRoot();
    const remember = vi.fn();
    const assign = vi.fn();

    // jsdom navigates by assigning; watch it without leaving the page.
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        set href(value: string) {
          assign(value);
        },
      },
    });

    await renderLibraryList(
      {
        list: async () => ({ items: [library('only')] }),
        remember,
        href: (id) => `/board/?tenant=${id}`,
      },
      root,
    ).load();

    expect(remember).toHaveBeenCalledWith('only');
    expect(assign).toHaveBeenCalledWith('/board/?tenant=only');
  });
});

describe('renderFactsAbout', () => {
  const clientWith = (facts: { id: string; name: string }[]) =>
    ({
      GET: vi.fn(async () => ({
        data: { items: facts, total: facts.length, page: 1, size: 100, pages: 1 },
        response: new Response(),
      })),
    }) as unknown as LorenzoClient;

  const draw = async (facts: { id: string; name: string }[]) => {
    const host = document.createElement('section');

    renderFactsAbout(
      {
        client: clientWith(facts),
        factPageHref: (t, id) => `/fact/?tenant=${t}&id=${id}`,
        heading: 'Facts about this being',
      },
      host,
      't',
      'e',
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    return host;
  };

  it('shows its facts under the app’s own heading, each linking to its page', async () => {
    const host = await draw([{ id: 'f1', name: 'Rumour' }]);

    expect(host.hidden).toBe(false);
    expect(host.querySelector('h2')?.textContent).toBe('Facts about this being');
    expect(host.querySelector('a')?.getAttribute('href')).toBe('/fact/?tenant=t&id=f1');
  });

  it('adds nothing when there are none', async () => {
    const host = await draw([]);

    expect(host.hidden).toBe(true);
    expect(host.childElementCount).toBe(0);
  });
});
