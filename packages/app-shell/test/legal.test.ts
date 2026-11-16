import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it, vi } from 'vitest';
import AppPage from '../src/AppPage.astro';
import { bindLegalLinks, bindLegalLinksFromApi, langOf, legalLinks } from '../src/legal';

const registry = {
  links: {
    legal_notice_en: 'https://legal.example/en/legal-notice/',
    legal_notice_de: 'https://legal.example/de/impressum/',
    legal_privacy_en: 'https://legal.example/en/privacy-policy/',
    legal_privacy_de: 'https://legal.example/de/datenschutz/',
  },
  support_url: 'https://support.example/lorenzo',
};

async function page(options: { shell?: 'web'; lang?: 'en' | 'de' } = {}) {
  const container = await AstroContainer.create();
  const html = await container.renderToString(AppPage, {
    props: {
      title: 'Calendars — Lorenzo',
      product: 'Calendars',
      brandingUrl: 'https://brand.example',
      themeKey: 'test:theme',
      path: 'apps/calendars',
      welcome: { title: 'Calendars', text: 'Time.', status: 'Opening…' },
      ...options,
    },
    slots: { default: '<p>The page</p>' },
  });

  return new JSDOM(html).window.document;
}

function holders(document: Document): Record<string, HTMLElement> {
  return Object.fromEntries(
    [...document.querySelectorAll<HTMLElement>('[data-shell-link]')].map((holder) => [
      holder.dataset.shellLink,
      holder,
    ]),
  );
}

describe('legalLinks', () => {
  it('picks the page of the language, and the support address', () => {
    expect(legalLinks(registry, 'en')).toEqual({
      notice: 'https://legal.example/en/legal-notice/',
      privacy: 'https://legal.example/en/privacy-policy/',
      support: 'https://support.example/lorenzo',
    });
    expect(legalLinks(registry, 'de').notice).toBe('https://legal.example/de/impressum/');
  });

  it('has none when the deployment named none, and never a script', () => {
    expect(legalLinks({}, 'en')).toEqual({});
    expect(legalLinks({ links: {}, support_url: null }, 'en')).toEqual({});
    expect(
      legalLinks({ links: { legal_notice_en: 'javascript:alert(1)' }, support_url: '  ' }, 'en'),
    ).toEqual({});
  });

  it('reads the language of a page', () => {
    expect([
      langOf('de'),
      langOf('de-AT'),
      langOf('DE'),
      langOf('en'),
      langOf(''),
      langOf(null),
    ]).toEqual(['de', 'de', 'de', 'en', 'en', 'en']);
  });
});

describe.each([
  ['the web shell', { shell: 'web' as const }],
  ['the old footer', {}],
])('%s', (_name, options) => {
  it('shows no legal link until the registry names one', async () => {
    const document = await page(options);

    expect(Object.keys(holders(document)).sort()).toEqual(['notice', 'privacy', 'support']);
    for (const holder of Object.values(holders(document))) expect(holder.hidden).toBe(true);
  });

  it('shows the links the registry names, in English', async () => {
    const document = await page(options);

    bindLegalLinks(registry, document);

    const found = holders(document);
    expect(found.notice?.hidden).toBe(false);
    expect(found.notice?.querySelector('a')?.getAttribute('href')).toBe(
      'https://legal.example/en/legal-notice/',
    );
    expect(found.notice?.textContent).toContain('Legal notice (Impressum)');
    expect(found.privacy?.textContent).toContain('Privacy policy');
    expect(found.support?.querySelector('a')?.getAttribute('href')).toBe(
      'https://support.example/lorenzo',
    );
  });

  it('shows the German names on a German page', async () => {
    const document = await page({ ...options, lang: 'de' });

    expect(document.documentElement.lang).toBe('de');
    bindLegalLinks(registry, document);

    const found = holders(document);
    expect(found.notice?.textContent?.trim()).toMatch(/Impressum$/);
    expect(found.notice?.querySelector('a')?.getAttribute('href')).toBe(
      'https://legal.example/de/impressum/',
    );
    expect(found.privacy?.textContent).toContain('Datenschutzerklärung');
  });

  it('hides a link again that a later registry does not have', async () => {
    const document = await page(options);

    bindLegalLinks(registry, document);
    bindLegalLinks({ links: {} }, document);

    for (const holder of Object.values(holders(document))) expect(holder.hidden).toBe(true);
  });
});

describe('bindLegalLinksFromApi', () => {
  it('asks the API for the public registry and binds what it says', async () => {
    const document = await page({});
    const fetcher = vi.fn(async () => new Response(JSON.stringify(registry)));

    await bindLegalLinksFromApi('https://api.example/', fetcher as never, document);

    expect(fetcher).toHaveBeenCalledWith(
      'https://api.example/app-links',
      expect.objectContaining({ referrerPolicy: 'no-referrer', credentials: 'omit' }),
    );
    expect(holders(document).notice?.hidden).toBe(false);
  });

  it('leaves the links hidden when the API cannot be reached or refuses', async () => {
    const document = await page({});

    await bindLegalLinksFromApi(
      'https://api.example',
      (async () => {
        throw new TypeError('offline');
      }) as never,
      document,
    );
    await bindLegalLinksFromApi(
      'https://api.example',
      (async () => new Response('', { status: 500 })) as never,
      document,
    );

    for (const holder of Object.values(holders(document))) expect(holder.hidden).toBe(true);
  });
});
