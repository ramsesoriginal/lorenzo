// Three-state tag editing on the item page (ADR 0103, 0112): each bool stat in the tenant's
// `tags` group is inherited, on, or explicitly off.
import { LorenzoApiError } from '../../lib/api';
import { getEntityDetail } from '../../lib/items';
import { statLabel } from '../../lib/statLabel';
import { type Definition, STATES, setTag, tagDefinitions, tagState } from '../../lib/tagEditor';
import type { EntityDetail } from '../../lib/types';

export type TagEditorOptions = {
  root: HTMLElement;
  tenantId: string;
  // After every change, so the page can show the tags readers now see.
  onChanged: () => void;
};

export type RenderedTagEditor = {
  load(entityId: string): Promise<void>;
};

const reason = (error: unknown) => (error instanceof Error ? error.message : String(error));

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Tag editor is missing ${selector}.`);
  }

  return element;
}

// `root` is whatever contains <TagEditor />.
export function renderTagEditor(options: TagEditorOptions): RenderedTagEditor {
  const { root, tenantId } = options;
  const message = required<HTMLElement>(root, '[data-message]');
  const tags = required<HTMLElement>(root, '[data-tags]');
  const status = required<HTMLElement>(root, '[data-status]');
  const tagTemplate = required<HTMLTemplateElement>(root, '[data-tag-template]');
  const choiceTemplate = required<HTMLTemplateElement>(root, '[data-choice-template]');

  // The line above the tags says what's wrong, or that they're loading; the one below, what a
  // change is doing. Each shows only while it has something to say.
  function say(line: HTMLElement, text: string, failed = false) {
    line.textContent = text;
    line.classList.toggle('error-text', failed);
    line.hidden = !text;
  }

  const clone = (template: HTMLTemplateElement, selector: string) =>
    required<HTMLElement>(template.content.cloneNode(true) as DocumentFragment, selector);

  return {
    async load(entityId) {
      tags.replaceChildren();
      say(status, '');
      say(message, 'Loading tags…');

      let definitions: Definition[];
      let entity: EntityDetail;

      try {
        [definitions, entity] = await Promise.all([
          tagDefinitions(tenantId),
          getEntityDetail(tenantId, entityId),
        ]);
      } catch (error) {
        // Listing definitions needs tenant membership, unlike writing a tag (ADR 0112).
        const member = !(
          error instanceof LorenzoApiError &&
          (error.status === 403 || error.status === 404)
        );

        say(
          message,
          member
            ? `Couldn't load tags: ${reason(error)}`
            : 'Only tenant members can see the list of tags.',
        );

        return;
      }

      if (definitions.length === 0) {
        say(message, 'This tenant has no tags yet.');
        return;
      }

      say(message, '');

      const draw = () => {
        const stats = new Map(entity.stats.map((stat) => [stat.name, stat]));

        tags.replaceChildren(
          ...definitions.map((definition) => {
            const { state, hint } = tagState(stats.get(definition.name));
            const group = clone(tagTemplate, '[data-tag]');
            const label = required<HTMLElement>(group, '[data-label]');
            const choices = required<HTMLElement>(group, '[data-choices]');

            label.id = `tag-label-${definition.id}`;
            label.textContent = statLabel(definition.name);
            group.setAttribute('aria-labelledby', label.id);

            for (const [value, text] of STATES) {
              const choice = clone(choiceTemplate, 'label');
              const radio = required<HTMLInputElement>(choice, '[data-radio]');

              radio.name = `tag-${definition.id}`;
              radio.value = value;
              radio.checked = value === state;
              required<HTMLElement>(choice, '[data-text]').textContent =
                value === 'inherited' ? text + hint : text;
              radio.addEventListener('change', async () => {
                for (const input of tags.querySelectorAll('input')) input.disabled = true;

                say(status, 'Saving…');

                try {
                  entity = await setTag(tenantId, entityId, definition.id, value);
                  say(status, '');
                  options.onChanged();
                } catch (error) {
                  say(status, reason(error), true);
                }

                draw();
              });
              choices.append(choice);
            }

            return group;
          }),
        );
      };

      draw();
    },
  };
}
