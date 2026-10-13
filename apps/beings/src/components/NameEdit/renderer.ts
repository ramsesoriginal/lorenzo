// Renaming a being (ADR 0272): one field and a button. The API's rename gate is the real one.

import { errorMessage } from '../../lib/errorMessage';
import { renameBeing } from '../../lib/people';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Name edit');

export type NameEditOptions = {
  root: HTMLFormElement;
  tenantId: string;
  // The being has this name now.
  onSaved: (name: string) => void;
};

export type RenderedNameEdit = {
  load(entityId: string, name: string): void;
};

export function renderNameEdit(options: NameEditOptions): RenderedNameEdit {
  const { root, tenantId } = options;
  const input = required<HTMLInputElement>(root, '[data-name]');
  const save = required<HTMLButtonElement>(root, '[data-save]');
  const status = required<HTMLElement>(root, '[data-status]');

  let entityId: string | null = null;
  let current = '';

  root.addEventListener('submit', async (event) => {
    event.preventDefault();

    const wanted = input.value.trim();

    if (!entityId || !wanted || wanted === current) return;

    save.disabled = true;
    say(status, 'Saving…');

    try {
      await renameBeing(tenantId, entityId, wanted);
      current = wanted;
      say(status, 'Saved.');
      options.onSaved(wanted);
    } catch (error) {
      say(status, errorMessage(error), true);
    } finally {
      save.disabled = false;
    }
  });

  return {
    load(id, name) {
      entityId = id;
      current = name;
      input.value = name;
      root.hidden = false;
      say(status, '');
    },
  };
}
