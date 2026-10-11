// What a being's page says about it (ADR 0271): its picture, its description as LorenzoScript, its
// tags and the stats it has (its own or inherited, ADR 0111). Read-only; the editors are separate.

import { blobUrl } from '../../lib/api';
import { descriptionOf, pictureOf } from '../../lib/being';
import { type Renderer, showDescriptions } from '../../lib/descriptions';
import { statLabel } from '../../lib/statLabel';
import { cloneTemplate, fromTemplate, requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

export type BeingViewOptions = { renderer: Renderer };

export type RenderedBeingView = {
  /** Shows `entity`, replacing what was shown. */
  show(entity: EntityDetail): void;
};

const required = requiredIn('Being view');

/** A stat's value as text; a tag is on or off. */
const valueText = (value: number | string | boolean): string =>
  typeof value === 'boolean' ? (value ? 'On' : 'Off') : String(value);

// `root` is the <BeingView /> block.
export function renderBeingView(root: HTMLElement, options: BeingViewOptions): RenderedBeingView {
  const figure = required<HTMLElement>(root, '[data-picture-figure]');
  const picture = required<HTMLImageElement>(root, '[data-picture]');
  const description = required<HTMLElement>(root, '[data-description]');
  const tags = required<HTMLUListElement>(root, '[data-tags]');
  const groups = required<HTMLElement>(root, '[data-groups]');
  const nothing = required<HTMLElement>(root, '[data-nothing]');
  const tagTemplate = required<HTMLTemplateElement>(root, '[data-tag-template]');

  // The picture shown, so an unrelated change does not fetch it again.
  let pictureId: string | null = null;

  return {
    show(entity) {
      const text = descriptionOf(entity);
      const main = pictureOf(entity);

      if (main?.kind !== 'picture') {
        pictureId = null;
        figure.hidden = true;
      } else if (main.id !== pictureId || main.updated_at !== picture.dataset.version) {
        pictureId = main.id;
        picture.dataset.version = main.updated_at;
        blobUrl(
          `${main.url}${main.url.includes('?') ? '&' : '?'}v=${encodeURIComponent(main.updated_at)}`,
        ).then(
          (src) => {
            picture.src = src;
            figure.hidden = false;
          },
          () => {
            figure.hidden = true;
          },
        );
      }

      picture.alt = `Picture of ${entity.name}`;

      void showDescriptions(description, options.renderer, text ? [{ text, home: entity.id }] : []);

      const on = entity.stats.filter((stat) => stat.value === true);
      const values = entity.stats.filter((stat) => typeof stat.value !== 'boolean');

      tags.hidden = on.length === 0;
      tags.replaceChildren(
        ...on.map((tag) => {
          const chip = cloneTemplate<HTMLLIElement>(tagTemplate, 'li');

          chip.textContent = statLabel(tag.name);

          return chip;
        }),
      );

      if (values.length === 0) {
        groups.replaceChildren();
      } else {
        const list = document.createElement('dl');

        list.className = 'key-values';
        list.setAttribute('aria-label', 'Stats');
        list.replaceChildren(
          ...[...values]
            .sort((a, b) => a.name.localeCompare(b.name))
            .flatMap((stat) => {
              const pair = fromTemplate(root, '[data-stat-template]');

              required<HTMLElement>(pair, '[data-name]').textContent = statLabel(stat.name);
              required<HTMLElement>(pair, '[data-value]').textContent = valueText(stat.value);

              return [...pair.children];
            }),
        );
        groups.replaceChildren(list);
      }

      nothing.hidden = Boolean(text) || on.length > 0 || values.length > 0 || main !== undefined;
    },
  };
}
