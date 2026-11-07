// How a repository carries one it is built on (RFC 0051 H1, ADR 0431): the two choices as a radio group,
// what each does, why one is not offered, and the note on changing it. Used by the Built on tab and by
// the "Make public" dialog, so the choice is made the same way in both. The words and the decisions
// are lib/inclusion.ts's; this binds them to a fieldset built here, so that neither markup has to
// hold it.

import { describeError } from '../../lib/describeError';
import {
  BREAKING_NOTE,
  INCLUSION_CHOICES,
  INCLUSION_LABEL,
  INCLUSION_LEGEND,
  type Inclusion,
  inclusionEffect,
  inclusionSaved,
} from '../../lib/inclusion';
import { setInclusion } from '../../lib/repositories';
import { say } from '../../lib/statusLine';
import type { InclusionOut } from '../../lib/types';

export type InclusionChoice = {
  // The repository that is built on another, and the other.
  repositoryId: string;
  sourceId: string;
  name: string;
  inclusion: Inclusion;
  // The choices to offer: `include` is left out where the user may not include it.
  offered: readonly Inclusion[];
  // Why `include` is not offered, said under the choices.
  notOffered: string | null;
  // Said once a release carried it: changing it makes a breaking release.
  note: string | null;
  // The repository is protected: what keeping it separate means says so (ADR 0433).
  protected?: boolean;
  // Only an Owner chooses.
  editable: boolean;
  // Called with what the API answered after a choice was saved; `failed` after one was refused.
  onSaved?: (answer: InclusionOut) => void;
  onFailed?: (cause: unknown) => void;
};

let counter = 0;

function paragraph(className: string): HTMLParagraphElement {
  const p = document.createElement('p');

  p.className = className;

  return p;
}

export function createInclusionChoice(options: InclusionChoice): HTMLFieldSetElement {
  const fieldset = document.createElement('fieldset');
  const legend = document.createElement('legend');
  const effect = paragraph('caption');
  const refusal = paragraph('caption');
  const note = paragraph('caption');
  const status = paragraph('status-text');
  const group = `inclusion-${++counter}`;
  const radios = new Map<Inclusion, HTMLInputElement>();
  let chosen = options.inclusion;

  fieldset.className = 'inclusion stack-tight';
  fieldset.dataset.inclusion = options.sourceId;
  legend.className = 'caption';
  legend.textContent = INCLUSION_LEGEND;
  fieldset.append(legend);

  for (const choice of INCLUSION_CHOICES) {
    if (!options.offered.includes(choice)) continue;

    const row = document.createElement('label');
    const radio = document.createElement('input');

    row.className = 'field-row';
    radio.type = 'radio';
    radio.name = group;
    radio.value = choice;
    radio.checked = choice === chosen;
    radio.disabled = !options.editable;
    radio.dataset.inclusionChoice = choice;
    row.append(radio, INCLUSION_LABEL[choice]);
    fieldset.append(row);
    radios.set(choice, radio);
  }

  effect.dataset.inclusionEffect = '';
  effect.textContent = inclusionEffect(chosen, options.name, options.protected === true);
  refusal.dataset.inclusionNotOffered = '';
  refusal.textContent = options.notOffered ?? '';
  refusal.hidden = options.notOffered === null;
  note.dataset.inclusionNote = '';
  note.textContent = options.note ?? '';
  note.hidden = options.note === null;
  status.dataset.inclusionStatus = '';
  status.hidden = true;
  fieldset.append(effect, refusal, note, status);

  for (const [choice, radio] of radios) {
    radio.addEventListener('change', () => {
      if (!radio.checked || choice === chosen) return;

      const before = chosen;

      for (const other of radios.values()) other.disabled = true;
      say(status, 'Saving…');

      void (async () => {
        try {
          const answer = await setInclusion(options.repositoryId, options.sourceId, choice);

          chosen = answer.inclusion;
          effect.textContent = inclusionEffect(chosen, options.name, options.protected === true);
          note.textContent = BREAKING_NOTE;
          note.hidden = answer.inclusion_in_release === null;
          say(status, inclusionSaved(answer));
          options.onSaved?.(answer);
        } catch (cause) {
          const back = radios.get(before);

          if (back) back.checked = true;
          say(status, describeError(cause), true);
          options.onFailed?.(cause);
        } finally {
          for (const other of radios.values()) other.disabled = !options.editable;
        }
      })();
    });
  }

  return fieldset;
}
