let fields = 0;

// A give's checkbox with a note saying what happens without it: "Hand it over" (ADR 0115),
// only offered for what's in a container, or "Also give what's inside" (ADR 0125), only for
// a container with something in it.
export function checkboxField(label: string, otherwise: string) {
  const input = Object.assign(document.createElement('input'), { type: 'checkbox' });
  const row = document.createElement('label');
  row.className = 'field-row';
  row.append(input, label);

  const note = document.createElement('p');
  note.className = 'field-note';
  note.id = `checkbox-note-${++fields}`;
  note.textContent = otherwise;
  input.setAttribute('aria-describedby', note.id);

  const element = document.createElement('div');
  element.append(row, note);

  return { element, input };
}
