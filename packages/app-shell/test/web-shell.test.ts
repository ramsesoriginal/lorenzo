// The components are rendered by Astro in Node, then driven in a jsdom window made by hand (the .astro
// imports do not render under vitest's own jsdom environment).
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppPage from '../src/AppPage.astro';
import type { Shell } from '../src/index';
import { bindShell } from '../src/index';

const nav = [
  { label: 'Home', href: '/', icon: 'library' },
  { label: 'Events', href: '/events/', needsLibrary: true, icon: 'kind-event' },
  { label: 'Settings', href: '/settings/' },
  { label: 'Import', href: '/import/' },
  { label: 'Export', href: '/export/' },
];

async function render(shell?: 'web') {
  const container = await AstroContainer.create();
  const props = {
    title: 'Calendars — Lorenzo',
    product: 'Calendars',
    brandingUrl: 'https://brand.example',
    themeKey: 'test:theme',
    nav,
    path: 'apps/calendars',
    welcome: { title: 'Calendars', text: 'Time in your world.', status: 'Opening…' },
    ...(shell ? { shell, version: '1.2.0', legal: { notice: '/legal/' } } : {}),
  };

  return container.renderToString(AppPage, { props, slots: { default: '<p>The page</p>' } });
}

let dom: JSDOM;

function mount(html: string, path = '/'): Shell {
  dom = new JSDOM(html, { url: `http://localhost:3000${path}` });
  const { window } = dom;

  // jsdom has no dialog methods or media queries.
  const proto = window.HTMLDialogElement.prototype;

  proto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  };
  proto.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open');
  };
  window.matchMedia = (() => ({ matches: false, addEventListener() {} })) as never;
  vi.stubGlobal('window', window);
  vi.stubGlobal('document', window.document);
  vi.stubGlobal('Option', window.Option);

  const shell = bindShell({ themeKey: 'test:theme', onLogin: () => {}, onLogout: () => {} });

  if (!shell) throw new Error('no header');

  return shell;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 10, 6, 9, 41));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('the old header is still the default', () => {
  it('draws the one-row header and no web shell', async () => {
    const html = await render();

    expect(html).toContain('data-site-header');
    expect(html).not.toContain('data-shell-status');
    expect(html).not.toContain('shell-container');
  });

  it('does nothing when the web-shell calls are made on it', async () => {
    const shell = mount(await render());

    expect(() => {
      shell.strip({ kind: 'offline', text: 'x' });
      shell.statusBar({ sync: 'waiting' });
      shell.apps({ apps: {} });
      shell.notifications({ count: 1, href: '/n' });
    }).not.toThrow();
  });
});

describe('the web shell', () => {
  it('draws a global bar, an app bar, a status bar, a tab bar and the sheet', async () => {
    const html = await render('web');

    for (const hook of [
      'shell-container',
      'shell-bar',
      'shell-apps',
      'data-shell-strip',
      'data-shell-status',
      'data-shell-tabbar',
      'data-shell-sheet',
    ]) {
      expect(html, hook).toContain(hook);
    }
  });

  it('puts the first three links in the tab bar and the rest in the sheet', async () => {
    mount(await render('web'));

    const bar = [...document.querySelectorAll('[data-shell-tabbar] a')].map((a) =>
      a.textContent?.trim(),
    );
    const more = [...document.querySelectorAll('[data-shell-more] a')].map((a) =>
      a.textContent?.trim(),
    );

    expect(bar).toEqual(['Home', 'Events', 'Settings']);
    expect(more).toEqual(['Import', 'Export']);
  });

  it('marks the current page in the app bar, the tab bar and the sheet', async () => {
    const shell = mount(await render('web'), '/settings/');

    shell.library('my library');
    const current = [...document.querySelectorAll('[aria-current="page"]')].map((a) =>
      a.getAttribute('data-path'),
    );

    expect(current).toEqual(['/settings/', '/settings/']);
    expect(
      (document.querySelector('.shell-apps a[data-path="/events/"]') as HTMLAnchorElement).href,
    ).toContain('/events/?tenant=my%20library');
    expect(
      (document.querySelector('[data-shell-tabbar] a[data-path="/events/"]') as HTMLElement).hidden,
    ).toBe(false);
  });

  it('shows the real date and time, and keeps it', async () => {
    mount(await render('web'));

    const clock = document.querySelector('[data-shell-clock]') as HTMLTimeElement;

    expect(clock.textContent).toMatch(/09:41/);
    vi.setSystemTime(new Date(2026, 10, 6, 9, 52));
    vi.advanceTimersByTime(30_000);
    expect(clock.textContent).toMatch(/09:52/);
  });
});

describe('the state strip', () => {
  it('opens with words and an action, and closes to nothing', async () => {
    const shell = mount(await render('web'));
    const strip = document.querySelector('[data-shell-strip]') as HTMLElement;
    const run = vi.fn();

    expect(strip.hasAttribute('data-open')).toBe(false);
    shell.strip({ kind: 'conflict', text: 'Two edits met.', action: { label: 'Review', run } });
    expect(strip.hasAttribute('data-open')).toBe(true);
    expect(strip.querySelector('.shell-strip-in')?.getAttribute('data-kind')).toBe('conflict');
    expect(strip.querySelector('[data-shell-strip-text]')?.textContent).toBe('Two edits met.');
    expect(strip.querySelector('[data-shell-strip-icon]')?.getAttribute('href')).toBe(
      'https://brand.example/icons.svg#icon-conflict',
    );

    (strip.querySelector('[data-shell-strip-action]') as HTMLButtonElement).click();
    expect(run).toHaveBeenCalledOnce();

    shell.strip(null);
    expect(strip.hasAttribute('data-open')).toBe(false);
  });
});

describe('the status bar', () => {
  it('says the sync state with a word and an icon, and the app’s own meta', async () => {
    const shell = mount(await render('web'));

    // Nothing is claimed until the app says something.
    expect((document.querySelector('[data-shell-sync]') as HTMLElement).hidden).toBe(true);

    shell.statusBar({ sync: 'waiting', meta: '12 beings' });
    expect((document.querySelector('[data-shell-sync]') as HTMLElement).hidden).toBe(false);
    expect(document.querySelector('[data-shell-sync]')?.getAttribute('data-kind')).toBe('waiting');
    expect(document.querySelector('[data-shell-sync-text]')?.textContent).toBe('Waiting to sync');
    expect(document.querySelector('[data-shell-sync-icon]')?.getAttribute('href')).toContain(
      '#icon-waiting',
    );
    expect((document.querySelector('[data-shell-meta]') as HTMLElement).hidden).toBe(false);
    expect(document.querySelector('[data-shell-meta]')?.textContent).toBe('12 beings');

    shell.statusBar({ meta: null });
    expect((document.querySelector('[data-shell-meta]') as HTMLElement).hidden).toBe(true);
  });
});

describe('the apps sheet', () => {
  const registry = {
    apps: {
      sessions: { url: 'https://sessions.example' },
      calendars: { url: 'http://localhost:3000' },
      account_hub: { url: 'https://hub.example' },
    },
  };

  it('lists the deployed apps by job and marks the one the person is in', async () => {
    const shell = mount(await render('web'));

    shell.apps(registry);
    const links = [...document.querySelectorAll('[data-shell-apps] a')] as HTMLAnchorElement[];

    expect(links.map((a) => a.textContent)).toEqual(['Sessions', 'Calendars', 'Account']);
    expect(
      [...document.querySelectorAll('[data-shell-apps] .menu-label')].map((l) => l.textContent),
    ).toEqual(['Play', 'World', 'You']);
    // The page is at http://localhost:3000, which is where this registry puts Calendars.
    expect(links.find((a) => a.dataset.app === 'calendars')?.getAttribute('aria-current')).toBe(
      'page',
    );
    expect(
      links.find((a) => a.dataset.app === 'sessions')?.getAttribute('aria-current'),
    ).toBeNull();
  });

  it('opens from "Apps and about" and from "More", and closes with the fade', async () => {
    mount(await render('web'));

    const sheet = document.querySelector('[data-shell-sheet]') as HTMLDialogElement;
    const openers = document.querySelectorAll('[data-shell-open-sheet]');

    expect(openers.length).toBe(2);
    (openers[0] as HTMLElement).click();
    expect(sheet.hasAttribute('open')).toBe(true);

    sheet.dispatchEvent(new dom.window.Event('cancel', { cancelable: true }));
    expect(sheet.hasAttribute('data-closing')).toBe(true);
    expect(sheet.hasAttribute('open')).toBe(true); // still there while it fades
    vi.advanceTimersByTime(500);
    expect(sheet.hasAttribute('open')).toBe(false);
    expect(sheet.hasAttribute('data-closing')).toBe(false);

    (openers[1] as HTMLElement).click();
    expect(sheet.hasAttribute('open')).toBe(true);
  });

  it('names the source, the version and the legal pages it has', async () => {
    mount(await render('web'));

    const about = document.querySelector('[data-shell-sheet]')?.textContent ?? '';

    expect(about).toContain('Legal notice');
    expect(about).not.toContain('Privacy policy');
    expect(about).toContain('Source code');
    expect(about).toContain('Lorenzo 1.2.0');
  });
});

describe('the notifications bell', () => {
  it('is hidden until an app has somewhere to send it', async () => {
    const shell = mount(await render('web'));
    const bell = document.querySelector('[data-shell-bell]') as HTMLAnchorElement;

    expect(bell.hidden).toBe(true);
    shell.notifications({ count: 3, href: '/notifications/' });
    expect(bell.hidden).toBe(false);
    expect(bell.getAttribute('aria-label')).toBe('Notifications, 3 unread');
    expect(bell.querySelector('[data-shell-bell-count]')?.textContent).toBe('3');
    shell.notifications(null);
    expect(bell.hidden).toBe(true);
  });
});

describe('the palette and the keys', () => {
  const registry = {
    apps: {
      sessions: { url: 'https://sessions.example/' },
      beings: { url: 'https://beings.example/' },
    },
  };

  function press(key: string, init: KeyboardEventInit = {}, target: EventTarget = document) {
    const event = new dom.window.KeyboardEvent('keydown', {
      key,
      bubbles: true,
      cancelable: true,
      ...init,
    });

    target.dispatchEvent(event);

    return event;
  }

  async function open() {
    const shell = mount(await render('web'));
    const assign = vi.fn();
    const run = vi.fn();

    shell.apps(registry);
    shell.palette({
      navigate: assign,
      commands: [{ id: 'beings.new', name: 'New being…', icon: 'add', keys: 'N', run }],
    });

    return { shell, assign, run };
  }

  it('does nothing until an app asks for it, and the buttons stay hidden', async () => {
    mount(await render('web'));

    expect(press('k', { ctrlKey: true }).defaultPrevented).toBe(false);
    expect((document.querySelector('[data-shell-open-palette]') as HTMLElement).hidden).toBe(true);
    expect(document.querySelector('dialog.palette')).toBeNull();
  });

  it('shows the buttons once an app asks, and Ctrl K opens a palette with the apps and the commands', async () => {
    await open();

    for (const button of document.querySelectorAll<HTMLElement>('[data-shell-open-palette]')) {
      expect(button.hidden).toBe(false);
    }
    expect(press('k', { ctrlKey: true }).defaultPrevented).toBe(true);

    const palette = document.querySelector('dialog.palette') as HTMLDialogElement;

    expect(palette.hasAttribute('open')).toBe(true);
    const rows = [...palette.querySelectorAll('.p-opt')].map(
      (r) => r.querySelector('.grow')?.textContent,
    );

    expect(rows).toEqual(
      expect.arrayContaining(['Home', 'Sessions', 'Beings', 'Change theme', 'New being…']),
    );
    expect(palette.querySelector('.p-opt[aria-selected="true"]')).not.toBeNull();
  });

  it('types to find, arrows to move, Enter to run, and remembers it', async () => {
    const { run } = await open();

    press('k', { ctrlKey: true });
    const palette = document.querySelector('dialog.palette') as HTMLDialogElement;
    const input = palette.querySelector('input') as HTMLInputElement;

    input.value = 'new';
    input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    expect([...palette.querySelectorAll('.p-opt .grow')].map((n) => n.textContent)).toEqual([
      'New being…',
    ]);
    expect(palette.querySelector('mark')?.textContent).toBe('New');

    press('Enter', {}, palette);
    expect(run).toHaveBeenCalledOnce();
    expect(JSON.parse(window.localStorage.getItem('lorenzo:palette-recent') ?? '[]')).toEqual([
      'beings.new',
    ]);
  });

  it('Tab narrows to a scope, and a click on a row runs it', async () => {
    const { assign } = await open();

    press('k', { ctrlKey: true });
    const palette = document.querySelector('dialog.palette') as HTMLDialogElement;

    press('Tab', {}, palette); // Entries: nothing to show without a query
    expect(palette.querySelector('.p-tabs [aria-selected="true"]')?.textContent).toBe('Entries');
    press('Tab', {}, palette); // Apps
    expect([...palette.querySelectorAll('.p-opt .grow')].map((n) => n.textContent)).toEqual([
      'Home',
      'Sessions',
      'Beings',
    ]);

    (palette.querySelectorAll('.p-opt')[1] as HTMLElement).click();
    expect(assign).toHaveBeenCalledWith('https://sessions.example/');
  });

  it('asks an app for entries as the person types, and ignores a late answer to an older query', async () => {
    const shell = mount(await render('web'));
    let resolveFirst: (items: never[]) => void = () => {};
    const entries = vi
      .fn()
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
      .mockResolvedValueOnce([
        {
          id: 'entry:mara',
          group: 'Entries',
          name: 'Mara Quill',
          kind: 'Character',
          app: 'Beings',
          run: () => {},
        },
      ]);

    shell.palette({ entries });
    press('k', { ctrlKey: true });
    const input = document.querySelector('dialog.palette input') as HTMLInputElement;
    const type = (value: string) => {
      input.value = value;
      input.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
    };

    type('m');
    type('mara');
    await vi.advanceTimersByTimeAsync(0);
    resolveFirst([]);
    await vi.advanceTimersByTimeAsync(0);

    expect(entries).toHaveBeenCalledTimes(2);
    expect([...document.querySelectorAll('.p-opt .grow')].map((n) => n.textContent)).toEqual([
      'Mara Quill',
    ]);
  });

  it('G then S goes to Sessions; a key in a field is left alone; the switch turns the single keys off', async () => {
    const { assign } = await open();

    press('g');
    press('s');
    expect(assign).toHaveBeenCalledWith('https://sessions.example/');

    assign.mockClear();
    const field = document.createElement('input');

    document.body.append(field);
    press('g', {}, field);
    press('s', {}, field);
    expect(assign).not.toHaveBeenCalled();

    press('?');
    const dialogs = [...document.querySelectorAll('dialog')];
    const shortcuts = dialogs.find(
      (d) => d.getAttribute('aria-labelledby') === 'shell-shortcuts-title',
    ) as HTMLDialogElement;

    expect(shortcuts.hasAttribute('open')).toBe(true);
    expect(shortcuts.textContent).toContain('Go to Sessions');
    expect(shortcuts.textContent).toContain('Change the theme');
    expect(shortcuts.textContent).not.toContain('Go to Calendars'); // not deployed

    const toggle = shortcuts.querySelector('input[type="checkbox"]') as HTMLInputElement;

    toggle.checked = false;
    toggle.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    press('g');
    press('s');
    expect(assign).not.toHaveBeenCalled();
    // Ctrl K still works with them off.
    expect(press('k', { ctrlKey: true }).defaultPrevented).toBe(true);
  });
});
