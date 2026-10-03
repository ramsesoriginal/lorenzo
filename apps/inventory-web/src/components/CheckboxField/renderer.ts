import { cloneTemplate, requiredIn } from '../../lib/template';

const required = requiredIn('Checkbox field');

let fields = 0;

// A give's checkbox with a note saying what happens without it: "Hand it over" (ADR 0115),
// only offered for what's in a container, or "Also give what's inside" (ADR 0125), only for
// a container with something in it.
export function renderCheckboxField(
  label: string,
  otherwise: string,
): { element: HTMLElement; input: HTMLInputElement } {
  const element = cloneTemplate<HTMLElement>(
    required<HTMLTemplateElement>(document, '[data-checkbox-field-template]'),
  );
  const input = required<HTMLInputElement>(element, '[data-input]');
  const note = required<HTMLElement>(element, '[data-note]');

  required<HTMLElement>(element, '[data-label]').textContent = label;
  note.textContent = otherwise;
  note.id = `checkbox-note-${++fields}`;
  input.setAttribute('aria-describedby', note.id);

  return { element, input };
}
