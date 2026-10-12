// The repository menu in the title bar, the start screen ("Your repositories") and the first-run
// welcome (ADR 0258). Plain DOM over a plain list, so the sample page can show the same things.

export interface RepoChoice {
  id: string;
  name: string;
  /** The person's role in it, as the API says it. */
  role: string;
}

import { icon } from './icons';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const ROLE: Record<string, string> = { owner: 'Owner', orga: 'Organiser', author: 'Author' };
export const roleText = (role: string): string => ROLE[role] ?? role;

/** The menu button: the open repository, and a list to switch to another or see them all. */
export function repositoryMenu(
  repos: readonly RepoChoice[],
  currentId: string | null,
  o: { choose: (id: string) => void; all: () => void },
): HTMLElement {
  const wrap = el('div', 'repo-menu');
  const current = repos.find((r) => r.id === currentId);
  const button = el('button', 'btn repo-button');
  button.append(document.createTextNode(current?.name ?? 'No repository'), icon('expand', 14));
  button.type = 'button';
  button.setAttribute('aria-haspopup', 'menu');
  button.setAttribute('aria-expanded', 'false');
  button.setAttribute('aria-label', `Repository: ${current?.name ?? 'none'}`);
  const menu = el('ul', 'repo-list');
  menu.setAttribute('role', 'menu');
  menu.hidden = true;

  const items: HTMLElement[] = [];
  const entry = (text: string, run: () => void, checked?: boolean, note?: string) => {
    const li = el('li');
    li.setAttribute('role', 'none');
    const b = el('button', 'repo-item', text);
    b.type = 'button';
    b.setAttribute('role', checked === undefined ? 'menuitem' : 'menuitemradio');
    if (checked !== undefined) b.setAttribute('aria-checked', String(checked));
    if (note) b.append(' ', el('span', 'muted', note));
    b.addEventListener('click', () => {
      close();
      run();
    });
    li.append(b);
    menu.append(li);
    items.push(b);
  };
  for (const r of repos)
    entry(r.name, () => r.id !== currentId && o.choose(r.id), r.id === currentId, roleText(r.role));
  entry('Your repositories…', o.all);

  const close = () => {
    menu.hidden = true;
    button.setAttribute('aria-expanded', 'false');
    document.removeEventListener('pointerdown', outside, true);
  };
  const outside = (e: Event) => {
    if (!wrap.contains(e.target as Node)) close();
  };
  const open = () => {
    menu.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    document.addEventListener('pointerdown', outside, true);
    (items.find((b) => b.getAttribute('aria-checked') === 'true') ?? items[0])?.focus();
  };
  button.addEventListener('click', () => (menu.hidden ? open() : close()));
  wrap.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !menu.hidden) {
      close();
      button.focus();
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (menu.hidden) return open();
      const at = items.indexOf(document.activeElement as HTMLElement);
      const next = (at + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    }
  });
  wrap.append(button, menu);
  return wrap;
}

/** The start screen: every repository the person authors, to open one. */
export function openStartScreen(
  repos: readonly RepoChoice[],
  currentId: string | null,
  choose: (id: string) => void,
): void {
  const dialog = el('dialog', 'confirm start-screen');
  dialog.setAttribute('aria-labelledby', 'start-title');
  const title = el('h2', undefined, 'Your repositories');
  title.id = 'start-title';
  dialog.append(title);
  if (!repos.length) {
    dialog.append(
      el(
        'p',
        undefined,
        'You do not author a repository yet. A repository is made with the lorenzo command line (lorenzo repo), or by an organiser who gives you the author role in one.',
      ),
    );
  } else {
    const list = el('ul', 'confirm-list');
    for (const r of repos) {
      const li = el('li');
      const open = el(
        'button',
        r.id === currentId ? 'btn' : 'btn primary',
        r.id === currentId ? 'Open now' : 'Open',
      );
      open.type = 'button';
      open.disabled = r.id === currentId;
      open.setAttribute('aria-label', `Open ${r.name}`);
      open.addEventListener('click', () => {
        dialog.close();
        dialog.remove();
        choose(r.id);
      });
      li.append(el('span', undefined, r.name), el('span', 'muted', roleText(r.role)), open);
      list.append(li);
    }
    dialog.append(list);
  }
  const close = el('button', 'btn', 'Close');
  close.type = 'button';
  close.addEventListener('click', () => {
    dialog.close();
    dialog.remove();
  });
  dialog.append(close);
  document.body.append(dialog);
  dialog.showModal();
  // The key that chose it may still be down: on a button it would press it at once.
  dialog.tabIndex = -1;
  dialog.focus();
}

const WELCOME_KEY = 'bench:welcomed';

/** Whether the welcome has been dismissed on this device. */
export function welcomed(): boolean {
  try {
    return localStorage.getItem(WELCOME_KEY) === '1';
  } catch {
    return false;
  }
}

/** The first-run explainer, in a strip under the title bar; shown until it is dismissed once. */
export function showWelcome(host: HTMLElement, force = false): void {
  if (!force && welcomed()) return;
  host.hidden = false;
  host.setAttribute('role', 'region');
  host.setAttribute('aria-label', 'Welcome to Bench');
  const list = el('ul');
  for (const text of [
    'Every change shows at once and is sent in order; it can be undone, and a conflict asks you.',
    'Ctrl+K opens the command palette: panes, entries, layouts.',
    'Drag a tab to split or float it, or use Write, Inspect and Compare for a ready layout.',
    'Type [[ in a text to link an entry, and {weight} to show one of its stats.',
  ])
    list.append(el('li', undefined, text));
  const got = el('button', 'btn', 'Got it');
  got.type = 'button';
  got.addEventListener('click', () => {
    try {
      localStorage.setItem(WELCOME_KEY, '1');
    } catch {
      /* shown again next time */
    }
    host.hidden = true;
    host.replaceChildren();
  });
  host.replaceChildren(el('strong', undefined, 'Welcome to Bench'), list, got);
}
