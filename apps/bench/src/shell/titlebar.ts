// The title bar: the repository picker on the left, who is signed in on the right.

import { openStartScreen, type RepoChoice, repositoryMenu } from './repositories';
import { chooseRepository, type Session, signIn } from './session';

const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};

const SAMPLE_REPO: RepoChoice = { id: 'sample', name: 'Sample repository', role: 'owner' };

export function renderTitleBar(
  bar: HTMLElement,
  session: Session,
  onRepository: (id: string) => void,
  onSignOut: () => void,
) {
  const brand = el('span', 'brand');
  // The real brand mark (identity §17.1: the spark is the logo, not an interface icon).
  const mark = el('img', 'brand-mark');
  mark.src = '/favicon.svg';
  mark.alt = '';
  mark.width = 16;
  mark.height = 16;
  brand.append(mark, el('b', undefined, 'Bench'));
  bar.replaceChildren(brand, el('span', 'sep'));
  const right = el('div', 'who');
  switch (session.kind) {
    case 'unconfigured':
      // One sample repository, so the menu and the start screen can be tried.
      bar.append(
        repositoryMenu([SAMPLE_REPO], SAMPLE_REPO.id, {
          choose: () => {},
          all: () => openStartScreen([SAMPLE_REPO], SAMPLE_REPO.id, () => {}),
        }),
        el('span', 'note', 'Sample data. Sign-in is not set up for this build.'),
      );
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
      const choices: RepoChoice[] = session.repositories.map((r) => ({
        id: r.id,
        name: r.name,
        role: r.role as string,
      }));
      const choose = (id: string) => {
        chooseRepository(session.userId, id);
        onRepository(id);
      };
      bar.append(
        repositoryMenu(choices, session.current?.id ?? null, {
          choose,
          all: () => openStartScreen(choices, session.current?.id ?? null, choose),
        }),
      );
      right.append(el('span', 'name', session.name));
      break;
    }
  }
  if (session.kind === 'signed-in' || session.kind === 'error') {
    const out = el('button', 'btn', session.kind === 'error' ? 'Sign out and retry' : 'Sign out');
    out.type = 'button';
    out.addEventListener('click', onSignOut);
    right.append(out);
  }
  bar.append(right);
}
