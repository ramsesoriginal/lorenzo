// The components are rendered by Astro in Node, then driven in a jsdom window made by hand (the .astro
// imports do not render under vitest's own jsdom environment).
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AppPage from '../src/AppPage.astro';
import type { Shell, ShellOptions } from '../src/index';
import { bindShell, initials, placeMenu } from '../src/index';
import { createToastTimer } from '../src/toast-timer';

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

function mount(html: string, path = '/', extra: Partial<ShellOptions> = {}): Shell {
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

  const shell = bindShell({
    themeKey: 'test:theme',
    onLogin: () => {},
    onLogout: () => {},
    ...extra,
  });

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

describe('toasts', () => {
  async function shellWithToasts() {
    return mount(await render('web'));
  }

  const cards = () => [...document.querySelectorAll<HTMLElement>('.toast-card')];

  it('shows a quiet confirmation that leaves by itself after ten seconds', async () => {
    const shell = await shellWithToasts();

    shell.toast({ title: 'Saved' });
    expect(cards()).toHaveLength(1);
    expect(cards()[0]?.getAttribute('role')).toBe('status');
    expect(document.querySelector('.toast-bar')).not.toBeNull();

    vi.advanceTimersByTime(9_999);
    expect(cards()).toHaveLength(1);
    vi.advanceTimersByTime(1);
    vi.advanceTimersByTime(300);
    expect(cards()).toHaveLength(0);
  });

  it('offers Undo, which runs once and dismisses', async () => {
    const shell = await shellWithToasts();
    const undo = vi.fn();

    shell.undoable({ title: 'Moved to the bin', text: '3 entries', undo });
    const button = document.querySelector<HTMLButtonElement>('.toast-action');

    expect(button?.textContent).toBe('Undo');
    button?.click();
    expect(undo).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(300);
    expect(cards()).toHaveLength(0);
  });

  it('keeps an error until it is dismissed, and offers Try again', async () => {
    const shell = await shellWithToasts();
    const retry = vi.fn();

    shell.toast({
      kind: 'error',
      title: 'Could not save',
      action: { label: 'Try again', run: retry },
    });
    expect(cards()[0]?.getAttribute('role')).toBe('alert');
    expect(document.querySelector('.toast-bar')).toBeNull();
    vi.advanceTimersByTime(60_000);
    expect(cards()).toHaveLength(1);

    document.querySelector<HTMLButtonElement>('.toast-card .icon-button')?.click();
    vi.advanceTimersByTime(300);
    expect(cards()).toHaveLength(0);
  });

  it('shows at most three, the oldest going first', async () => {
    const shell = await shellWithToasts();

    for (const title of ['one', 'two', 'three', 'four']) shell.toast({ title });
    expect(cards().map((c) => c.querySelector('.toast-title')?.textContent)).toEqual([
      'two',
      'three',
      'four',
    ]);
  });

  it('does nothing in the old header', async () => {
    const shell = mount(await render());

    expect(() => shell.toast({ title: 'Saved' })).not.toThrow();
    expect(document.querySelector('.toast-card')).toBeNull();
  });

  it('the timer holds, and starts again from the full time', () => {
    const done = vi.fn();
    const timer = createToastTimer(10_000, done);

    timer.start();
    vi.advanceTimersByTime(8_000);
    timer.hold();
    vi.advanceTimersByTime(60_000);
    expect(done).not.toHaveBeenCalled();
    timer.release();
    vi.advanceTimersByTime(9_999);
    expect(done).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(done).toHaveBeenCalledTimes(1);
  });
});

describe('confirmations', () => {
  it('resolves true on the button and false on Cancel, naming what it does', async () => {
    const shell = mount(await render('web'));
    const yes = shell.confirm({
      title: 'Delete 12 entries?',
      body: 'They are gone.',
      confirm: 'Delete 12 entries',
      danger: true,
    });
    const dialog = document.querySelector('dialog:not([data-shell-sheet])') as HTMLDialogElement;

    expect(dialog.querySelector('h2')?.textContent).toBe('Delete 12 entries?');
    expect(dialog.querySelector('.btn-danger')?.textContent).toBe('Delete 12 entries');
    (dialog.querySelector('.btn-danger') as HTMLButtonElement).click();
    expect(await yes).toBe(true);

    const no = shell.confirm({ title: 'Sure?', body: ['a', 'b'], confirm: 'Go' });
    const second = [...document.querySelectorAll('dialog')].pop() as HTMLDialogElement;

    expect(second.querySelectorAll('p')).toHaveLength(2);
    (second.querySelector('.btn-secondary') as HTMLButtonElement).click();
    expect(await no).toBe(false);
  });

  it('keeps the button off until the name is typed, with the reason beside it', async () => {
    const shell = mount(await render('web'));
    const result = shell.confirm({
      title: 'Delete the library?',
      body: 'All of it.',
      confirm: 'Delete the library',
      danger: true,
      typeToConfirm: 'Mara',
    });
    const dialog = [...document.querySelectorAll('dialog')].pop() as HTMLDialogElement;
    const input = dialog.querySelector('input') as HTMLInputElement;
    const button = dialog.querySelector('.btn-danger') as HTMLButtonElement;

    expect(button.getAttribute('aria-disabled')).toBe('true');
    expect(dialog.textContent).toContain('works once you have typed');
    button.click();
    input.value = 'Mar';
    input.dispatchEvent(new dom.window.Event('input'));
    expect(button.getAttribute('aria-disabled')).toBe('true');
    input.value = 'Mara';
    input.dispatchEvent(new dom.window.Event('input'));
    expect(button.getAttribute('aria-disabled')).toBe('false');
    input.dispatchEvent(
      new dom.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }),
    );
    expect(await result).toBe(true);
  });
});

describe('placing a menu', () => {
  const view = { width: 1000, height: 700 };
  const size = { width: 240, height: 200 };

  it('goes under its anchor on the left edge', () => {
    expect(placeMenu({ left: 100, right: 140, top: 10, bottom: 50 }, size, view)).toEqual({
      left: 100,
      top: 56,
    });
  });

  it("goes to the anchor's right edge when it would run off, and above when there is no room below", () => {
    expect(placeMenu({ left: 900, right: 960, top: 600, bottom: 640 }, size, view)).toEqual({
      left: 720,
      top: 394,
    });
  });

  it('stays inside the window', () => {
    const at = placeMenu({ left: -50, right: -10, top: 0, bottom: 20 }, size, view);

    expect(at.left).toBeGreaterThanOrEqual(8);
    expect(at.top).toBeGreaterThanOrEqual(8);
  });
});

describe('the account menu', () => {
  const press = (key: string, target: EventTarget = document) =>
    target.dispatchEvent(
      new dom.window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }),
    );

  async function signedIn(extra: Partial<ShellOptions> = {}) {
    const html = await render('web');
    const onLogout = vi.fn();
    const shell = mount(html, '/', { onLogout, ...extra });

    shell.account({ state: 'signed-in', label: 'mara.quill@example.com' });
    shell.accountLink('https://account.example/');
    const button = document.querySelector('[data-shell-account-button]') as HTMLButtonElement;

    return { shell, onLogout, button };
  }

  const items = () => [...document.querySelectorAll<HTMLElement>('.menu [role^="menuitem"]')];

  it('takes its initials from the account', () => {
    expect(initials('mara.quill@example.com')).toBe('MQ');
    expect(initials('Mara Quill Jr')).toBe('MQ');
    expect(initials('mara')).toBe('M');
    expect(initials(undefined)).toBe('·');
  });

  it('shows the initials on the button, and opens the items in the order of the design', async () => {
    const { button } = await signedIn();

    expect(button.textContent).toBe('MQ');
    button.click();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(document.querySelector('.menu-head')?.textContent).toBe('mara.quill@example.com');
    expect(items().map((i) => i.querySelector('.grow')?.textContent)).toEqual([
      'Profile',
      'Notifications',
      'Libraries and people',
      'Access tokens and devices',
      'Dark theme',
      'Keyboard shortcuts',
      'Sign out',
    ]);
    expect((items()[0] as HTMLAnchorElement).href).toBe('https://account.example/profile/');
  });

  it('moves with the arrows, closes on Escape and gives focus back', async () => {
    const { button } = await signedIn();

    button.click();
    expect(document.activeElement).toBe(items()[0]);
    press('ArrowDown', items()[0] as HTMLElement);
    expect(document.activeElement).toBe(items()[1]);
    press('End', items()[1] as HTMLElement);
    expect(document.activeElement).toBe(items()[6]);
    press('Escape', items()[6] as HTMLElement);
    expect(document.querySelector('.menu')).toBeNull();
    expect(document.activeElement).toBe(button);
    expect(button.getAttribute('aria-expanded')).toBe('false');
  });

  it('signs out at once when nothing is unsent', async () => {
    const { button, onLogout } = await signedIn({ unsent: () => null });

    button.click();
    items()[6]?.click();
    vi.advanceTimersByTime(10);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it('asks first when something is only on the device, and signs out only if confirmed', async () => {
    const { button, onLogout } = await signedIn({
      unsent: () => ['2 changes are only on this device.', 'They are sent when you sign in again.'],
    });

    button.click();
    items()[6]?.click();
    vi.advanceTimersByTime(10);
    expect(onLogout).not.toHaveBeenCalled();

    const dialog = [...document.querySelectorAll('dialog')].pop() as HTMLDialogElement;

    expect(dialog.textContent).toContain('2 changes are only on this device.');
    expect(dialog.querySelector('.btn-danger')?.textContent).toBe('Sign out anyway');
    (dialog.querySelector('.btn-danger') as HTMLButtonElement).click();
    await vi.advanceTimersByTimeAsync(10);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it('the Keyboard shortcuts item opens the list', async () => {
    const { button } = await signedIn();

    button.click();
    items()[5]?.click();
    vi.advanceTimersByTime(10);
    const title = document.querySelector('#shell-shortcuts-title');

    expect(title?.closest('dialog')?.hasAttribute('open')).toBe(true);
  });
});
