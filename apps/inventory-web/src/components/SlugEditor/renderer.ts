// The item page's slug editor for GMs (ADR 0113): the field, holding the entity's slug or a
// suggestion, and Save.
import { getEntityDetail } from '../../lib/items';
import { type SlugKind, saveSlug, suggestSlug } from '../../lib/slugs';

export type SlugEditorOptions = {
  // Whatever contains <SlugEditor />.
  root: HTMLElement;
  tenantId: string;
  // Gets the slug the entity has now, or null.
  onSaved: (slug: string | null) => void;
};

export type RenderedSlugEditor = {
  // `title` and `kind` decide the slug it suggests for an entity that has none.
  load(entityId: string, title: string, kind: SlugKind): Promise<void>;
};

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Slug editor is missing ${selector}.`);
  }

  return element;
}

export function renderSlugEditor(options: SlugEditorOptions): RenderedSlugEditor {
  const { root, tenantId } = options;
  const message = required<HTMLElement>(root, '[data-message]');
  const form = required<HTMLFormElement>(root, '[data-form]');
  const input = required<HTMLInputElement>(root, '[data-slug]');
  const save = required<HTMLButtonElement>(root, '[data-save]');
  const status = required<HTMLElement>(root, '[data-status]');

  // The entity being edited, and the slug it has as far as this editor knows.
  let entityId: string | null = null;
  let current: string | null = null;

  function say(line: HTMLElement, text: string, failed = false) {
    line.textContent = text;
    line.classList.toggle('error-text', failed);
    line.hidden = !text;
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (!entityId) return;

    save.disabled = true;
    say(status, 'Saving…');

    try {
      await saveSlug(tenantId, entityId, current, input.value);
      current = input.value.trim() || null;
      say(status, current ? 'Saved.' : 'Cleared.');
      options.onSaved(current);
    } catch (error) {
      say(status, reason(error), true);
    } finally {
      save.disabled = false;
    }
  });

  return {
    async load(id, title, kind) {
      entityId = null;
      form.hidden = true;
      say(status, '');
      say(message, 'Loading the slug…');

      try {
        current = (await getEntityDetail(tenantId, id)).slug;
        input.value = current ?? (await suggestSlug(tenantId, title, kind));
      } catch (error) {
        say(message, `Couldn't load the slug: ${reason(error)}`);
        return;
      }

      entityId = id;
      say(message, '');
      form.hidden = false;
    },
  };
}
