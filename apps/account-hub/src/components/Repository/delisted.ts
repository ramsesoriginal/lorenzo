// The notice on a repository's Overview while the platform's operators have it off Discover (RFC 0038
// §6, ADR 0297): every member of the repository reads it, whatever their role, since they are the
// people who fix it. The words are lib/delisting.ts's. It reads the repository's profile fresh, since
// an operator can list it again at any moment, and shows nothing where the profile cannot be read:
// the rest of the Overview does not depend on it.

import { delistedNotice } from '../../lib/delisting';
import { getRepositoryProfile } from '../../lib/repositories';
import { requiredIn } from '../../lib/template';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type DelistedNotice = {
  clear(): void;
  paint(repository: TenantSummaryOut): Promise<void>;
};

// `root` is the <Repository /> article.
export function createDelistedNotice(root: HTMLElement): DelistedNotice {
  const box = required<HTMLElement>(root, '[data-delisted]');
  const pill = required<HTMLElement>(box, '[data-delisted-pill]');
  const title = required<HTMLElement>(box, '[data-delisted-title]');
  const reason = required<HTMLElement>(box, '[data-delisted-reason]');
  const effect = required<HTMLElement>(box, '[data-delisted-effect]');
  let shown: TenantSummaryOut | null = null;

  return {
    clear() {
      shown = null;
      box.hidden = true;
    },

    async paint(repository) {
      shown = repository;
      box.hidden = true;

      try {
        const profile = await getRepositoryProfile(repository.id, { fresh: true });

        if (shown !== repository) return;

        const notice = delistedNotice(profile.delisted);

        if (notice === null) return;

        pill.textContent = notice.pill;
        title.textContent = notice.title;
        reason.textContent = notice.reason;
        effect.textContent = notice.effect;
        box.hidden = false;
      } catch {
        // A notice that cannot be read is not shown; the Overview does not depend on it.
      }
    },
  };
}
