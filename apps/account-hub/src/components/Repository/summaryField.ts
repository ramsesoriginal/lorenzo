// A repository's summary field, in the one place it is wired (ADR 0385): the Make public dialog's
// (ADR 0290) and the Profile tab's are both bound by this, so the help, the count and the rule are the
// same words and cannot disagree. What counts is the summary as the API keeps it, on one line
// (lib/visibility.ts). The checks are lib/visibility.ts's too; this is only the DOM around them.

import { SUMMARY_HELP, summaryCount } from '../../lib/visibility';

export type SummaryField = {
  // What is typed, as typed.
  value(): string;
  // Puts a saved summary in the field, as what it was drawn with, so that "was it typed in?" (lib/
  // editing.ts) means a change from it.
  set(text: string): void;
  // Told on every keystroke, after the count was updated.
  onInput(listener: () => void): void;
  focus(): void;
};

// `input` is the <textarea>, `help` the line that says what it is for, `count` the one that says how
// far it is from its limit.
export function bindSummaryField(parts: {
  input: HTMLTextAreaElement;
  help: HTMLElement;
  count: HTMLElement;
}): SummaryField {
  const { input, help, count } = parts;
  const listeners: (() => void)[] = [];

  help.textContent = SUMMARY_HELP;
  count.textContent = summaryCount(input.value);
  input.addEventListener('input', () => {
    count.textContent = summaryCount(input.value);
    for (const listener of listeners) listener();
  });

  return {
    value: () => input.value,
    set(text) {
      input.value = text;
      input.defaultValue = text;
      count.textContent = summaryCount(text);
    },
    onInput: (listener) => {
      listeners.push(listener);
    },
    focus: () => input.focus(),
  };
}
