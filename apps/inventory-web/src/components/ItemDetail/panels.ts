import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { BoardState } from '../Board/state';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';

// What the dialog's actions need to know about the page they sit on.
export type ActionContext = {
  tenantId: string;
  viewerIsGm: boolean;
  board: BoardState;
  undo: RenderedUndoBanner;
  // The dialog, whose <ActionPanels /> templates the panels copy.
  root: HTMLElement;
  // Closes the dialog onto the board as it is now.
  finish(): void;
};

const required = requiredIn('Action panels');

const template = (ctx: ActionContext, selector: string) =>
  required<HTMLTemplateElement>(ctx.root, selector);

// A number field: for how many of a stack to give, or to split off.
export function quantityField(
  ctx: ActionContext,
  label: string,
  max: number | undefined,
): { element: HTMLElement; input: HTMLInputElement } {
  const element = cloneTemplate<HTMLElement>(template(ctx, '[data-quantity-field-template]'));
  const input = required<HTMLInputElement>(element, '[data-quantity]');

  required<HTMLElement>(element, '[data-label]').textContent = label;

  if (max) input.max = String(max);

  return { element, input };
}

export type SplitPanel = {
  element: HTMLElement;
  input: HTMLInputElement;
  submit: HTMLButtonElement;
  status: HTMLElement;
};

export function splitPanelParts(ctx: ActionContext, label: string, max: number): SplitPanel {
  const element = cloneTemplate<HTMLElement>(template(ctx, '[data-split-panel-template]'));
  const field = quantityField(ctx, label, max);

  required<HTMLElement>(element, '[data-quantity-mount]').replaceWith(field.element);

  return {
    element,
    input: field.input,
    submit: required<HTMLButtonElement>(element, '[data-submit]'),
    status: required<HTMLElement>(element, '[data-status]'),
  };
}

export type UnpackPanel = {
  element: HTMLElement;
  question: HTMLElement;
  submit: HTMLButtonElement;
  status: HTMLElement;
};

export function unpackPanelParts(ctx: ActionContext): UnpackPanel {
  const element = cloneTemplate<HTMLElement>(template(ctx, '[data-unpack-panel-template]'));

  return {
    element,
    question: required<HTMLElement>(element, '[data-question]'),
    submit: required<HTMLButtonElement>(element, '[data-submit]'),
    status: required<HTMLElement>(element, '[data-status]'),
  };
}

export type ChoicesPanel = {
  element: HTMLElement;
  // Adds a button that does `onChoose` when pressed.
  addChoice(text: string, onChoose: () => void): void;
  // Every choice at once, while one is being acted on.
  setDisabled(disabled: boolean): void;
  // What went wrong, under the choices.
  fail(message: string): void;
};

// A panel of choices, or only `empty` when there's none to make.
export function choicesPanel(ctx: ActionContext, empty: string | null): ChoicesPanel {
  const element = cloneTemplate<HTMLElement>(template(ctx, '[data-choices-panel-template]'));
  const choices = required<HTMLElement>(element, '[data-choices]');
  const status = required<HTMLElement>(element, '[data-status]');
  const choice = required<HTMLTemplateElement>(element, '[data-choice-template]');

  if (empty !== null) {
    const note = required<HTMLElement>(element, '[data-note]');

    note.textContent = empty;
    note.hidden = false;
    choices.hidden = true;
  }

  return {
    element,

    addChoice(text, onChoose) {
      const button = cloneTemplate<HTMLButtonElement>(choice, 'button');

      button.textContent = text;
      button.addEventListener('click', onChoose);
      choices.append(button);
    },

    setDisabled(disabled) {
      for (const button of choices.querySelectorAll('button')) button.disabled = disabled;
    },

    fail: (message) => say(status, message, true),
  };
}
