// The release composer (ADR 0209), in whichever dialog holds one: the publish dialog (publish.ts) and
// the "Make public" dialog (visibility.ts, ADR 0290). A label, notes and a breaking flag, what the
// release will contain as the API's preview says it, and what it breaks, which has to be
// acknowledged. The words and the checks are lib/releases.ts's; this binds them to the markup of
// ReleaseComposer.astro.

import { ApiError } from '../../lib/apiError';
import {
  ACKNOWLEDGE_TEXT,
  breakingLines,
  type ComposerForm,
  contentLines,
  defaultLabel,
  descriptionsHint,
  LABEL_MAX,
  matchesSentence,
  TEXT_NOT_TRACKED,
  WARNING_TITLE,
  warningLines,
} from '../../lib/releases';
import { requiredIn } from '../../lib/template';
import type { BreakingRowOut, ReleasePreviewOut } from '../../lib/types';

const required = requiredIn('Repository');

export type Composer = {
  element: HTMLElement;
  // Empties the form and shows what a release made now would contain.
  show(preview: ReleasePreviewOut): void;
  form(): ComposerForm;
  // What the release would break, as the preview or the API's refusal says.
  hits(): BreakingRowOut[];
  // The API refused for what the preview did not see: the rows are shown, to be acknowledged. True
  // when that is what the refusal was.
  refused(cause: unknown): boolean;
};

function item(text: string): HTMLElement {
  const li = document.createElement('li');

  li.textContent = text;

  return li;
}

// `dialog` is the dialog (or any element) that holds a <ReleaseComposer />.
export function createComposer(dialog: ParentNode): Composer {
  const element = required<HTMLElement>(dialog, '[data-composer]');
  const label = required<HTMLInputElement>(element, '[data-composer-label]');
  const labelHelp = required<HTMLElement>(element, '[data-label-help]');
  const notes = required<HTMLTextAreaElement>(element, '[data-composer-notes]');
  const breaking = required<HTMLInputElement>(element, '[data-composer-breaking]');
  const matches = required<HTMLElement>(element, '[data-matches-line]');
  const contents = required<HTMLElement>(element, '[data-content-lines]');
  const hint = required<HTMLElement>(element, '[data-hint]');
  const breaksBox = required<HTMLElement>(element, '[data-breaks-box]');
  const breaksLines = required<HTMLElement>(element, '[data-breaks-lines]');
  const warnsBox = required<HTMLElement>(element, '[data-warns-box]');
  const warnsLines = required<HTMLElement>(element, '[data-warns-lines]');
  const acknowledge = required<HTMLInputElement>(element, '[data-composer-ack]');

  required<HTMLElement>(element, '[data-ack-text]').textContent = ACKNOWLEDGE_TEXT;
  required<HTMLElement>(element, '[data-not-tracked]').textContent = TEXT_NOT_TRACKED;
  required<HTMLElement>(element, '[data-warns-title]').textContent = WARNING_TITLE;
  label.maxLength = LABEL_MAX;

  let hits: BreakingRowOut[] = [];

  function showHits(rows: BreakingRowOut[]): void {
    hits = rows;
    breaksLines.replaceChildren(...breakingLines(rows).map(item));
    breaksBox.hidden = rows.length === 0;
  }

  // What the release only says: said, never refused, nothing to acknowledge.
  function showWarnings(rows: BreakingRowOut[]): void {
    warnsLines.replaceChildren(...warningLines(rows).map(item));
    warnsBox.hidden = rows.length === 0;
  }

  return {
    element,

    show(preview) {
      label.value = '';
      notes.value = '';
      breaking.checked = false;
      acknowledge.checked = false;
      labelHelp.textContent = `Free text, such as 1.3 or Spring errata. Left empty, it is ${defaultLabel(preview)}.`;
      matches.textContent = matchesSentence(preview);
      contents.replaceChildren(...contentLines(preview).map(item));

      const description = descriptionsHint(preview);

      hint.textContent = description ?? '';
      hint.hidden = description === null;
      showHits(preview.breaking);
      showWarnings(preview.warnings);
    },

    form() {
      return {
        label: label.value,
        notes: notes.value,
        breaking: breaking.checked,
        acknowledged: acknowledge.checked,
      };
    },

    hits() {
      return hits;
    },

    refused(cause) {
      if (!(cause instanceof ApiError) || cause.problemType !== 'release-has-breaking-changes') {
        return false;
      }

      const rows = cause.problem.breaking_rows;

      showHits(Array.isArray(rows) ? (rows as BreakingRowOut[]) : []);
      acknowledge.checked = false;

      return true;
    },
  };
}
