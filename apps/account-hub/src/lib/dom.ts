// Shared DOM builders reused across pages - see ADR 0080. These build
// real elements and call real async callbacks, so (unlike format.ts's
// pure helpers) there's no import-chain purity to protect here; they
// simply live alongside the other lib/*.ts modules.

export function createStatusSpan(): HTMLSpanElement {
  const span = document.createElement('span');
  span.className = 'status-text';
  span.setAttribute('role', 'status');
  return span;
}

// The rename-with-inline-edit-form pattern duplicated verbatim between
// characters.astro and beings.astro before ADR 0080 - both called the
// same updateCharacter(tenantId, entityId, { name }) underneath, just for
// what's semantically a PC vs a being. Returns the <li> with
// name/rename-button/status already attached; callers append anything
// extra (the being handoff button, for instance) rather than this helper
// needing to know about every page's own additional actions.
export function renderRenameableItem(
  name: string,
  onRename: (newName: string) => Promise<void>,
): HTMLLIElement {
  const item = document.createElement('li');
  const nameEl = document.createElement('span');
  nameEl.textContent = name;

  const renameButton = document.createElement('button');
  renameButton.type = 'button';
  renameButton.textContent = 'Rename';

  const status = createStatusSpan();

  renameButton.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'text';
    input.value = name;
    const saveButton = document.createElement('button');
    saveButton.type = 'button';
    saveButton.textContent = 'Save';
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.textContent = 'Cancel';

    item.replaceChildren(input, saveButton, cancelButton, status);

    cancelButton.addEventListener('click', () => {
      item.replaceChildren(nameEl, renameButton, status);
    });
    saveButton.addEventListener('click', async () => {
      const newName = input.value.trim();
      if (newName === '' || newName === name) {
        item.replaceChildren(nameEl, renameButton, status);
        return;
      }
      status.textContent = 'Saving…';
      try {
        await onRename(newName);
        // Caller's onRename triggers a full refresh (the established
        // pattern throughout this app) - no local state to reset here.
      } catch (e) {
        status.textContent = e instanceof Error ? e.message : String(e);
      }
    });
  });

  item.append(nameEl, renameButton, status);
  return item;
}

// The single-text-input create/invite form pattern, likewise duplicated
// between characters.astro and beings.astro before ADR 0080.
export function renderCreateForm(
  placeholder: string,
  buttonLabel: string,
  onCreate: (name: string) => Promise<void>,
): HTMLFormElement {
  const form = document.createElement('form');
  form.className = 'inline-form';
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = placeholder;
  input.required = true;
  const button = document.createElement('button');
  button.type = 'submit';
  button.textContent = buttonLabel;
  const status = createStatusSpan();

  form.append(input, button, status);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = input.value.trim();
    if (name === '') return;
    status.textContent = 'Creating…';
    try {
      await onCreate(name);
      input.value = '';
      status.textContent = '';
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });
  return form;
}
