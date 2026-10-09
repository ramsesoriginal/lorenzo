// The title bar: the repository picker on the left, who is signed in on the right.

import { chooseRepository, type Session, signIn, signOut } from './session';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

export function renderTitleBar(
  bar: HTMLElement,
  session: Session,
  onRepository: (id: string) => void,
) {
  bar.replaceChildren(el('strong', undefined, 'Lorenzo Bench'));
  const right = el('div', 'who');
  switch (session.kind) {
    case 'unconfigured':
      bar.append(el('span', 'note', 'Sample data. Sign-in is not set up for this build.'));
      break;
    case 'signed-out': {
      bar.append(el('span', 'note', 'Not signed in. Sample data.'));
      const b = el('button', 'btn', 'Sign in');
      b.type = 'button';
      b.addEventListener('click', () => void signIn());
      right.append(b);
      break;
    }
    case 'error':
      bar.append(el('span', 'note bad', session.message));
      break;
    case 'signed-in': {
      const label = el('label', 'picker');
      label.append(el('span', 'sr', 'Repository'));
      const select = el('select');
      select.setAttribute('aria-label', 'Repository');
      if (!session.repositories.length) {
        select.append(new Option('No repositories yet', ''));
        select.disabled = true;
      }
      for (const r of session.repositories)
        select.append(new Option(r.name, r.id, false, r.id === session.current?.id));
      select.addEventListener('change', () => {
        chooseRepository(session.userId, select.value);
        onRepository(select.value);
      });
      label.append(select);
      bar.append(label);
      right.append(el('span', 'name', session.name));
      break;
    }
  }
  if (session.kind === 'signed-in' || session.kind === 'error') {
    const out = el('button', 'btn', session.kind === 'error' ? 'Sign out and retry' : 'Sign out');
    out.type = 'button';
    out.addEventListener('click', () => void signOut());
    right.append(out);
  }
  bar.append(el('span', 'hint', 'Ctrl+K for commands'), right);
}
