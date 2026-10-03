// Three-state tag editing on the item page (ADR 0103, 0112): each bool stat in the tenant's
// `tags` group is inherited, on, or explicitly off.

import { LorenzoApiError } from '../../lib/api';
import { errorMessage } from '../../lib/errorMessage';
import { getEntityDetail } from '../../lib/items';
import { statLabel } from '../../lib/statLabel';
import { say } from '../../lib/statusLine';
import { type Definition, STATES, setTag, tagDefinitions, tagState } from '../../lib/tagEditor';
import { cloneTemplate, requiredIn } from '../../lib/template';
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

const required = requiredIn('Tag editor');

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
            ? `Couldn't load tags: ${errorMessage(error)}`
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
            const group = cloneTemplate<HTMLElement>(tagTemplate, '[data-tag]');
            const label = required<HTMLElement>(group, '[data-label]');
            const choices = required<HTMLElement>(group, '[data-choices]');

            label.id = `tag-label-${definition.id}`;
            label.textContent = statLabel(definition.name);
            group.setAttribute('aria-labelledby', label.id);

            for (const [value, text] of STATES) {
              const choice = cloneTemplate<HTMLLabelElement>(choiceTemplate, 'label');
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
                  say(status, errorMessage(error), true);
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
