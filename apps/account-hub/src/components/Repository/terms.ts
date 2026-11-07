// What repositories built on this one may use it for, on the Profile tab (RFC 0051 H1 and H3, ADR 0431
// and ADR 0434): a card with the two presets, "Open" and "Stay hidden", and the switches under them,
// "May be included" and "May be shown". Every member reads it; an Owner changes it, and it is saved when
// it is changed, not with the profile's Save: it is a decision of its own, and nothing about the rest of
// the profile is waiting on it. "May be shown" can be turned off only while the repository is protected;
// the card says so where it is not. The third switch, "May be hidden" (RFC 0051 H4, ADR 0435), is the same
// under the same presets. The words are lib/inclusion.ts's.

import { describeError } from '../../lib/describeError';
import {
  presetOf,
  presetPatch,
  TERMS_HEADING,
  TERMS_HIDDEN_HELP,
  TERMS_HIDDEN_LABEL,
  TERMS_INCLUDE_HELP,
  TERMS_INCLUDE_LABEL,
  TERMS_INTRO,
  TERMS_PRESET_LEGEND,
  TERMS_PRESETS,
  TERMS_SAVED,
  TERMS_SAVING,
  TERMS_SHOWN_HELP,
  TERMS_SHOWN_LABEL,
  type TermsPreset,
  termsHiddenLine,
  termsHiddenPatch,
  termsLine,
  termsPatch,
  termsShownLine,
  termsShownPatch,
} from '../../lib/inclusion';
import { ONLY_AN_OWNER } from '../../lib/profileEditor';
import { getRepositoryProfile, updateRepositoryProfile } from '../../lib/repositories';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { MemberProfileOut, TenantSummaryOut, TermsOut } from '../../lib/types';

const required = requiredIn('Repository');

export type TermsCard = {
  clear(): void;
  load(repository: TenantSummaryOut, isCurrent: () => boolean): Promise<void>;
};

// `root` is the <Repository /> article.
export function createTermsCard(root: HTMLElement): TermsCard {
  const card = required<HTMLElement>(root, '[data-terms-card]');
  const include = required<HTMLInputElement>(card, '[data-terms-include]');
  const shown = required<HTMLInputElement>(card, '[data-terms-shown]');
  const line = required<HTMLElement>(card, '[data-terms-line]');
  const shownLine = required<HTMLElement>(card, '[data-terms-shown-line]');
  const hidden = required<HTMLInputElement>(card, '[data-terms-hidden]');
  const hiddenLine = required<HTMLElement>(card, '[data-terms-hidden-line]');
  const presets = required<HTMLElement>(card, '[data-terms-presets]');
  const ownerOnly = required<HTMLElement>(card, '[data-terms-owner-only]');
  const status = required<HTMLElement>(card, '[data-terms-status]');

  required<HTMLElement>(card, '[data-terms-heading]').textContent = TERMS_HEADING;
  required<HTMLElement>(card, '[data-terms-intro]').textContent = TERMS_INTRO;
  required<HTMLElement>(card, '[data-terms-include-label]').textContent = TERMS_INCLUDE_LABEL;
  required<HTMLElement>(card, '[data-terms-include-help]').textContent = TERMS_INCLUDE_HELP;
  required<HTMLElement>(card, '[data-terms-shown-label]').textContent = TERMS_SHOWN_LABEL;
  required<HTMLElement>(card, '[data-terms-shown-help]').textContent = TERMS_SHOWN_HELP;
  required<HTMLElement>(card, '[data-terms-hidden-label]').textContent = TERMS_HIDDEN_LABEL;
  required<HTMLElement>(card, '[data-terms-hidden-help]').textContent = TERMS_HIDDEN_HELP;
  required<HTMLElement>(card, '[data-terms-presets-legend]').textContent = TERMS_PRESET_LEGEND;
  ownerOnly.textContent = ONLY_AN_OWNER;

  // The two presets, as a radio group built here, each with what it says.
  const radios = new Map<TermsPreset, HTMLInputElement>();

  for (const preset of TERMS_PRESETS) {
    const row = document.createElement('label');
    const radio = document.createElement('input');
    const text = document.createElement('span');

    row.className = 'field-row';
    radio.type = 'radio';
    radio.name = 'terms-preset';
    radio.value = preset.id;
    radio.dataset.termsPreset = preset.id;
    text.textContent = `${preset.label}: ${preset.help}`;
    row.append(radio, text);
    presets.append(row);
    radios.set(preset.id, radio);
  }

  let repositoryShown: TenantSummaryOut | null = null;
  let visibility = 'private';
  let current: TermsOut | null = null;

  function lock(locked: boolean): void {
    const owner = repositoryShown?.role === 'owner';
    // Only a protected repository can ask not to be shown: the switch and its preset wait for it.
    const mayHide = visibility === 'protected';

    include.disabled = locked || !owner;
    shown.disabled = locked || !owner || !mayHide;
    hidden.disabled = locked || !owner || !mayHide;
    for (const [id, radio] of radios) {
      radio.disabled = locked || !owner || (id === 'stay-hidden' && !mayHide);
    }
  }

  function paint(terms: TermsOut): void {
    current = terms;
    include.checked = terms.may_be_included;
    line.textContent = termsLine(terms, visibility);
    shown.checked = terms.may_be_shown;
    shownLine.textContent = termsShownLine(terms, visibility);
    hidden.checked = terms.may_be_hidden;
    hiddenLine.textContent = termsHiddenLine(terms, visibility);

    const preset = presetOf(terms, visibility);

    for (const [id, radio] of radios) radio.checked = id === preset;
  }

  // One change, saved at once: what the API answered is what the card says after.
  function save(patch: Parameters<typeof updateRepositoryProfile>[1], undo: () => void): void {
    const repository = repositoryShown;

    if (repository?.role !== 'owner') return;

    lock(true);
    say(status, TERMS_SAVING);

    void (async () => {
      try {
        const profile = await updateRepositoryProfile(repository.id, patch);

        if (repositoryShown !== repository) return;

        paint(profile.terms);
        say(status, TERMS_SAVED);
      } catch (cause) {
        if (repositoryShown !== repository) return;

        undo();
        say(status, describeError(cause), true);
      } finally {
        if (repositoryShown === repository) lock(false);
      }
    })();
  }

  include.addEventListener('change', () => {
    const wanted = include.checked;

    save(termsPatch(wanted), () => {
      include.checked = !wanted;
    });
  });

  shown.addEventListener('change', () => {
    const wanted = shown.checked;

    save(termsShownPatch(wanted), () => {
      shown.checked = !wanted;
    });
  });

  hidden.addEventListener('change', () => {
    const wanted = hidden.checked;

    save(termsHiddenPatch(wanted), () => {
      hidden.checked = !wanted;
    });
  });

  for (const [id, radio] of radios) {
    radio.addEventListener('change', () => {
      if (!radio.checked) return;

      const before = current;

      save(presetPatch(id), () => {
        if (before) paint(before);
      });
    });
  }

  return {
    clear() {
      repositoryShown = null;
      current = null;
      card.hidden = true;
      say(status, '');
    },

    async load(repository, isCurrent) {
      repositoryShown = repository;
      card.hidden = true;

      try {
        const profile: MemberProfileOut = await getRepositoryProfile(repository.id, {
          fresh: true,
        });

        if (!isCurrent() || repositoryShown !== repository) return;

        visibility = profile.visibility;
        paint(profile.terms);
        lock(false);
        ownerOnly.hidden = repository.role === 'owner';
        card.hidden = false;
      } catch {
        // The profile reports its own failure; a card that cannot be read is not shown.
      }
    },
  };
}
