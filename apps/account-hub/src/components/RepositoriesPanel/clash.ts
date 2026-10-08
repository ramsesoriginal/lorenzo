// One name clash as a card with its choices (ADR 0201, 0203): what the library already has, Keep
// both, Use the existing one and Leave it out with what each costs, the recommended one marked,
// and a name to type for Keep both. The copy wizard shows one for each clash of a copy, and the
// update inbox one for each new row that clashes. The cards use the templates the
// <RepositoriesPanel /> keeps, and the choices live in the map the caller gives.

import {
  CHOICE_LABEL,
  type Choice,
  type ChoiceAction,
  choiceExplanation,
  choiceProblem,
  collisionKey,
  collisionSentence,
  recommendedChoices,
  suggestedName,
} from '../../lib/copyWizard';
import { cloneRoot, requiredIn } from '../../lib/template';
import type { CollisionOut } from '../../lib/types';

const required = requiredIn('Name clash');

export type ClashOptions = {
  // Makes the radio buttons of this card a group of their own.
  index: string | number;
  // Where a copy came from, so that a new name can start from it.
  repositoryName: string;
  // What has been chosen, by `collisionKey`. The card reads and writes it.
  choices: Map<string, Choice>;
  // Called when a choice or a name changed.
  onChange(): void;
};

// `panel` holds the clash templates.
export function renderClashCard(
  panel: HTMLElement,
  collision: CollisionOut,
  options: ClashOptions,
): HTMLElement {
  const { index, repositoryName, choices: chosen, onChange } = options;
  const card = cloneRoot(panel, '[data-clash-template]');
  const key = collisionKey(collision);
  const recommended = recommendedChoices([collision], repositoryName).get(key);
  const nameField = required<HTMLElement>(card, '[data-name-field]');
  const nameInput = required<HTMLInputElement>(card, '[data-name]');
  const problem = required<HTMLElement>(card, '[data-problem]');
  const choices = required<HTMLElement>(card, '[data-choices]');

  required<HTMLElement>(card, '[data-sentence]').textContent = collisionSentence(collision);
  required<HTMLElement>(card, '[data-name-label]').textContent =
    collision.kind === 'slug' ? 'New link name' : 'New name';

  for (const action of collision.choices) {
    const option = cloneRoot(panel, '[data-choice-template]');
    const radio = required<HTMLInputElement>(option, '[data-radio]');

    radio.name = `clash-${index}`;
    radio.value = action;
    radio.checked = chosen.get(key)?.action === action;
    required<HTMLElement>(option, '[data-label]').textContent = CHOICE_LABEL[action];
    required<HTMLElement>(option, '[data-explanation]').textContent = choiceExplanation(
      collision,
      action,
    );
    required<HTMLElement>(option, '[data-recommended]').hidden = recommended?.action !== action;
    choices.append(option);
  }

  function paintProblem(): void {
    const choice = chosen.get(key);
    // Only a name that was typed is complained about: an empty one is the first thing to type.
    const text =
      choice?.action === 'rename' && choice.name !== '' ? choiceProblem(collision, choice) : null;

    problem.textContent = text ?? '';
    problem.hidden = text === null;
  }

  function paintName(): void {
    const choice = chosen.get(key);

    nameField.hidden = choice?.action !== 'rename';
    nameInput.value = choice?.name ?? '';
  }

  card.addEventListener('change', (event) => {
    const radio = event.target as HTMLInputElement;

    if (radio.type !== 'radio') return;

    const action = radio.value as ChoiceAction;
    const known = chosen.get(key);

    chosen.set(key, { action, name: known?.name || suggestedName(collision, repositoryName) });
    paintName();
    paintProblem();
    onChange();

    if (action === 'rename') nameInput.focus();
  });

  nameInput.addEventListener('input', () => {
    const choice = chosen.get(key);

    if (choice) choice.name = nameInput.value;

    paintProblem();
    onChange();
  });

  paintName();
  paintProblem();

  return card;
}
