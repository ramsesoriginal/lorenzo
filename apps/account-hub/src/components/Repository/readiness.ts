// "Before this can be public", beside the visibility card on a repository's Overview (RFC 0038 §2,
// ADR 0385): what a private repository still lacks, each with a link to where it is fixed. It is only a
// list: the flip's rules stand, and the Make public dialog reads the API again before it does anything.
// What it says of what the repository is built on is what ADR 0290's flip check returned, not
// something worked out again here. It is read again when the profile or the cover was saved.

import {
  READINESS_HEADING,
  READINESS_NOTE,
  type ReadinessItem,
  type ReadinessTarget,
  readinessOf,
  showsReadiness,
} from '../../lib/readiness';
import { getRepositoryProfile } from '../../lib/repositories';
import { requiredIn } from '../../lib/template';
import type { FlipCheckOut, TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type ReadinessControls = {
  clear(): void;
  // Draws the list for what the flip check read, for an Owner of a private repository that can be
  // made public here, and hides it for anything else.
  paint(repository: TenantSummaryOut, check: FlipCheckOut): Promise<void>;
};

// Where a link without a page of its own goes in the address, so that it is a link and not a button.
function hrefOf(target: ReadinessTarget): string {
  switch (target.kind) {
    case 'summary':
      return '#profile-summary';
    case 'cover':
      return '#profile-cover';
    case 'built-on':
      return '#built-on';
    case 'page':
      return target.href;
  }
}

// `root` is the <Repository /> article. `jump` opens where a target is: the tab, and the field.
export function createReadiness(
  root: HTMLElement,
  jump: (target: ReadinessTarget) => void,
): ReadinessControls {
  const box = required<HTMLElement>(root, '[data-readiness]');
  const list = required<HTMLElement>(box, '[data-readiness-list]');

  required<HTMLElement>(box, '[data-readiness-heading]').textContent = READINESS_HEADING;
  required<HTMLElement>(box, '[data-readiness-note]').textContent = READINESS_NOTE;

  let shown: TenantSummaryOut | null = null;

  function row(item: ReadinessItem): HTMLElement {
    const li = document.createElement('li');
    const pill = document.createElement('span');
    const text = document.createElement('span');

    li.className = 'row';
    li.dataset.need = item.need;
    li.dataset.done = String(item.done);
    pill.className = item.done ? 'pill pill-success' : 'pill pill-warning';
    pill.textContent = item.done ? 'Done' : item.need === 'required' ? 'Needed' : 'Recommended';
    text.className = 'grow';
    text.textContent = item.text;
    li.append(pill, text);

    if (item.link) {
      const { label, target } = item.link;
      const link = document.createElement('a');

      link.className = 'shelf-link';
      link.href = hrefOf(target);
      link.textContent = label;

      if (target.kind !== 'page') {
        link.addEventListener('click', (event) => {
          event.preventDefault();
          jump(target);
        });
      }

      li.append(link);
    }

    return li;
  }

  return {
    clear() {
      shown = null;
      box.hidden = true;
      list.replaceChildren();
    },

    async paint(repository, check) {
      shown = repository;

      if (!showsReadiness(check, repository.role)) {
        box.hidden = true;

        return;
      }

      try {
        const profile = await getRepositoryProfile(repository.id, { fresh: true });

        if (shown !== repository) return;

        list.replaceChildren(...readinessOf(check, profile.has_cover).map(row));
        box.hidden = false;
      } catch {
        // A list that cannot be read is not shown; the rest of the Overview does not depend on it.
        box.hidden = true;
      }
    },
  };
}
