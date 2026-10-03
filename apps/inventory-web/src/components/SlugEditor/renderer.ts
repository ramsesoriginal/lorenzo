// The item page's slug editor for GMs (ADR 0113): the field, holding the entity's slug or a
// suggestion, and Save.
import { errorMessage } from '../../lib/errorMessage';
import { getEntityDetail } from '../../lib/items';
import { type SlugKind, saveSlug, suggestSlug } from '../../lib/slugs';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

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

const required = requiredIn('Slug editor');

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
      say(status, errorMessage(error), true);
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
        say(message, `Couldn't load the slug: ${errorMessage(error)}`);
        return;
      }

      entityId = id;
      say(message, '');
      form.hidden = false;
    },
  };
}
