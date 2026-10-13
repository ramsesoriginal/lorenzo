// A note's audience (ADR 0271): one of the four names identity §14.3 gives, as radio buttons with a
// line under them saying what it means, and for "Some characters" the characters to choose. The
// field is read by the form that holds it; the API decides what is allowed.

import { AUDIENCES, type Audience } from '../../lib/notes';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { BeingRef } from '../../lib/types';

const required = requiredIn('Audience field');

export type AudienceFieldOptions = {
  /** Which audiences are offered, in order. */
  offer: readonly Audience[];
  initial: Audience;
  /** The characters already told, for "Some characters". */
  told: readonly string[];
  /** The characters that can be told, fetched when first needed. */
  candidates: () => Promise<BeingRef[]>;
};

export type RenderedAudienceField = {
  element: HTMLElement;
  value(): { audience: Audience; characters: string[] };
};

let groups = 0;

// `templates` is whatever contains <AudienceField />.
export function renderAudienceField(
  templates: ParentNode,
  options: AudienceFieldOptions,
): RenderedAudienceField {
  const holder = cloneTemplate<HTMLElement>(
    required<HTMLTemplateElement>(templates, '[data-audience-template]'),
    '[data-audience]',
  );
  const choiceTemplate = required<HTMLTemplateElement>(templates, '[data-choice-template]');
  const candidateTemplate = required<HTMLTemplateElement>(templates, '[data-candidate-template]');
  const choices = required<HTMLElement>(holder, '[data-choices]');
  const hint = required<HTMLElement>(holder, '[data-hint]');
  const characters = required<HTMLElement>(holder, '[data-characters]');
  const find = required<HTMLInputElement>(holder, '[data-find]');
  const candidatesBox = required<HTMLElement>(holder, '[data-candidates]');

  const name = `audience-${++groups}`;
  const radios = new Map<Audience, HTMLInputElement>();
  const checked = new Set(options.told);
  let loaded: BeingRef[] | null = null;

  function drawCandidates() {
    const wanted = find.value.trim().toLowerCase();

    candidatesBox.replaceChildren(
      ...(loaded ?? [])
        .filter((being) => being.name.toLowerCase().includes(wanted))
        .map((being) => {
          const row = cloneTemplate<HTMLLabelElement>(candidateTemplate, 'label');
          const box = required<HTMLInputElement>(row, '[data-check]');

          box.checked = checked.has(being.entity_id);
          box.addEventListener('change', () => {
            if (box.checked) checked.add(being.entity_id);
            else checked.delete(being.entity_id);
          });
          required<HTMLElement>(row, '[data-text]').textContent = being.name;

          return row;
        }),
    );
  }

  async function update() {
    const audience = current();

    hint.textContent = AUDIENCES[audience].hint;
    characters.hidden = audience !== 'some';

    if (audience === 'some' && loaded === null) {
      candidatesBox.textContent = 'Loading characters…';
      loaded = await options.candidates().catch(() => []);
      drawCandidates();
    }
  }

  function current(): Audience {
    for (const [audience, radio] of radios) if (radio.checked) return audience;

    return options.initial;
  }

  for (const audience of options.offer) {
    const choice = cloneTemplate<HTMLLabelElement>(choiceTemplate, 'label');
    const radio = required<HTMLInputElement>(choice, '[data-radio]');

    radio.name = name;
    radio.value = audience;
    radio.checked = audience === options.initial;
    radio.addEventListener('change', () => void update());
    required<HTMLElement>(choice, '[data-text]').textContent = AUDIENCES[audience].label;
    radios.set(audience, radio);
    choices.append(choice);
  }

  find.addEventListener('input', drawCandidates);
  void update();

  return {
    element: holder,
    value: () => ({ audience: current(), characters: [...checked] }),
  };
}
