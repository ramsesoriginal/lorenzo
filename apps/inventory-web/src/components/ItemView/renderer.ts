// One rendering of an item for the dialog and the item page (ADR 0112): its stat groups, tags,
// pictures, and descriptions, its own and those it inherits from its prototypes (ADR 0111).

import { blobUrl, type components } from '../../lib/api';
import { type Renderer, showDescriptions } from '../../lib/descriptions';
import { statLabel } from '../../lib/statLabel';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { ItemBase } from '../../lib/types';

type Source = components['schemas']['EntitySummary'] | null;

const GROUPS = [
  ['Physical', 'physical_stats'],
  ['Economic', 'economic_stats'],
  ['Destroyable', 'destroyable_stats'],
  ['Damaging', 'damaging_stats'],
] as const;

export type ItemViewOptions = { tenantId: string; renderer: Renderer };

export type RenderedItemView = {
  // Shows `item`, replacing what was shown. Descriptions render as LorenzoScript.
  show(item: ItemBase): void;
};

const required = requiredIn('Item view');

// `root` is whatever contains <ItemView />.
export function renderItemView(root: HTMLElement, options: ItemViewOptions): RenderedItemView {
  const groups = required<HTMLElement>(root, '[data-groups]');
  const tags = required<HTMLUListElement>(root, '[data-tags]');
  const pictures = required<HTMLElement>(root, '[data-pictures]');
  const descriptions = required<HTMLElement>(root, '[data-descriptions]');

  // "From Longsword", linking to it, for something an item inherits; any participant may follow
  // (ADR 0116).
  function fillSource(label: HTMLElement, source: NonNullable<Source>) {
    const link = required<HTMLAnchorElement>(label, '[data-link]');

    link.href = `/item/?tenant=${options.tenantId}&id=${source.id}`;
    link.textContent = source.name;
  }

  function sourceLabel(source: Source): HTMLElement | null {
    if (!source) return null;

    const label = required<HTMLElement>(fromTemplate(root, '[data-source-template]'), 'p');

    fillSource(label, source);

    return label;
  }

  return {
    show(item) {
      groups.replaceChildren(
        ...GROUPS.flatMap(([heading, key]) => {
          const set = item[key].filter((stat) => stat.value !== null);

          if (set.length === 0) return [];

          const group = fromTemplate(root, '[data-group-template]');
          const stats = required<HTMLElement>(group, '[data-stats]');

          required<HTMLElement>(group, '[data-heading]').textContent = heading;
          stats.replaceChildren(
            ...set.flatMap((stat) => {
              const pair = fromTemplate(root, '[data-stat-template]');

              required<HTMLElement>(pair, '[data-name]').textContent = statLabel(stat.name);
              required<HTMLElement>(pair, '[data-value]').textContent = String(stat.value);

              return [...pair.children];
            }),
          );

          return [required<HTMLElement>(group, 'section')];
        }),
      );

      const on = item.tags.filter((tag) => tag.value === true);

      tags.hidden = on.length === 0;
      tags.replaceChildren(
        ...on.map((tag) => {
          const chip = required<HTMLLIElement>(fromTemplate(root, '[data-tag-template]'), 'li');

          chip.textContent = statLabel(tag.name);

          return chip;
        }),
      );

      pictures.hidden = item.pictures.length === 0;
      pictures.replaceChildren(
        ...item.pictures.map((picture) => {
          const figure = required<HTMLElement>(
            fromTemplate(root, '[data-picture-template]'),
            'figure',
          );
          const image = required<HTMLImageElement>(figure, '[data-image]');
          const caption = required<HTMLElement>(figure, '[data-caption]');

          image.alt = picture.from_entity
            ? `Picture of ${picture.from_entity.name}`
            : `Picture of ${item.title}`;
          blobUrl(picture.url).then(
            (src) => {
              image.src = src;
            },
            () => figure.remove(),
          );

          if (picture.from_entity) {
            fillSource(caption, picture.from_entity);
            caption.hidden = false;
          } else {
            caption.remove();
          }

          return figure;
        }),
      );

      void showDescriptions(
        descriptions,
        options.renderer,
        item.descriptions.map((description) => ({
          text: description.content,
          label: sourceLabel(description.from_entity),
        })),
      );
    },
  };
}
