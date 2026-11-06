// What repositories built on this one may use it for, on the Profile tab (RFC 0051 H1, ADR 0431): a
// card with the one switch, "May be included". Every member reads it; an Owner changes it, and it is
// saved when it is changed, not with the profile's Save: it is a decision of its own, and nothing about
// the rest of the profile is waiting on it. The words are lib/inclusion.ts's.

import { describeError } from '../../lib/describeError';
import {
  TERMS_HEADING,
  TERMS_INCLUDE_HELP,
  TERMS_INCLUDE_LABEL,
  TERMS_INTRO,
  TERMS_SAVED,
  TERMS_SAVING,
  termsLine,
  termsPatch,
} from '../../lib/inclusion';
import { ONLY_AN_OWNER } from '../../lib/profileEditor';
import { getRepositoryProfile, updateRepositoryProfile } from '../../lib/repositories';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { TenantSummaryOut, TermsOut } from '../../lib/types';

const required = requiredIn('Repository');

export type TermsCard = {
  clear(): void;
  load(repository: TenantSummaryOut, isCurrent: () => boolean): Promise<void>;
};

// `root` is the <Repository /> article.
export function createTermsCard(root: HTMLElement): TermsCard {
  const card = required<HTMLElement>(root, '[data-terms-card]');
  const include = required<HTMLInputElement>(card, '[data-terms-include]');
  const line = required<HTMLElement>(card, '[data-terms-line]');
  const ownerOnly = required<HTMLElement>(card, '[data-terms-owner-only]');
  const status = required<HTMLElement>(card, '[data-terms-status]');

  required<HTMLElement>(card, '[data-terms-heading]').textContent = TERMS_HEADING;
  required<HTMLElement>(card, '[data-terms-intro]').textContent = TERMS_INTRO;
  required<HTMLElement>(card, '[data-terms-include-label]').textContent = TERMS_INCLUDE_LABEL;
  required<HTMLElement>(card, '[data-terms-include-help]').textContent = TERMS_INCLUDE_HELP;
  ownerOnly.textContent = ONLY_AN_OWNER;

  let shown: TenantSummaryOut | null = null;

  function paint(terms: TermsOut): void {
    include.checked = terms.may_be_included;
    line.textContent = termsLine(terms);
  }

  include.addEventListener('change', () => {
    const repository = shown;

    if (repository?.role !== 'owner') return;

    const wanted = include.checked;

    include.disabled = true;
    say(status, TERMS_SAVING);

    void (async () => {
      try {
        const profile = await updateRepositoryProfile(repository.id, termsPatch(wanted));

        if (shown !== repository) return;

        paint(profile.terms);
        say(status, TERMS_SAVED);
      } catch (cause) {
        if (shown !== repository) return;

        include.checked = !wanted;
        say(status, describeError(cause), true);
      } finally {
        include.disabled = shown !== repository || repository.role !== 'owner';
      }
    })();
  });

  return {
    clear() {
      shown = null;
      card.hidden = true;
      say(status, '');
    },

    async load(repository, isCurrent) {
      shown = repository;
      card.hidden = true;

      try {
        const profile = await getRepositoryProfile(repository.id, { fresh: true });

        if (!isCurrent() || shown !== repository) return;

        paint(profile.terms);
        include.disabled = repository.role !== 'owner';
        ownerOnly.hidden = repository.role === 'owner';
        card.hidden = false;
      } catch {
        // The profile reports its own failure; a card that cannot be read is not shown.
      }
    },
  };
}
