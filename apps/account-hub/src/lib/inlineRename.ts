// Renaming something in place: its name, a Rename button, and a form of the name that takes its
// place while it is edited. A character on a seat and a being are renamed the same way.
import { say, sayError } from './statusLine';

export type InlineRenameParts = {
  name: HTMLElement;
  renameButton: HTMLButtonElement;
  form: HTMLFormElement;
  input: HTMLInputElement;
  cancel: HTMLButtonElement;
  status: HTMLElement;
  // The row's other controls: out of the way while the name is edited, and back as they were after.
  alongside?: HTMLElement[];
};

// Binds the parts. `save` is given the new name; what it says on failure is shown in `status`, and
// a save that works is for it to follow up (a reload, usually).
export function bindInlineRename(
  parts: InlineRenameParts,
  currentName: string,
  save: (newName: string) => Promise<void>,
): void {
  const { name, renameButton, form, input, cancel, status, alongside = [] } = parts;

  // What the other controls were showing, so a button that was hidden stays hidden.
  let hiddenBefore: boolean[] = [];

  function showName(): void {
    form.hidden = true;
    name.hidden = false;
    renameButton.hidden = false;
    alongside.forEach((element, index) => {
      element.hidden = hiddenBefore[index] ?? element.hidden;
    });
  }

  renameButton.addEventListener('click', () => {
    hiddenBefore = alongside.map((element) => element.hidden);

    for (const element of alongside) element.hidden = true;

    name.hidden = true;
    renameButton.hidden = true;
    input.value = currentName;
    form.hidden = false;
    input.focus();
  });

  cancel.addEventListener('click', showName);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const newName = input.value.trim();

    if (newName === '' || newName === currentName) {
      showName();

      return;
    }

    say(status, 'Saving…');

    try {
      await save(newName);
    } catch (e) {
      sayError(status, e);
    }
  });
}
