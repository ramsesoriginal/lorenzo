import { renderInformationPayloads } from '@lorenzo/information-editor';
import { listInformation } from '../../lib/information';
import { renderFactsAbout } from '../Facts/renderer';
// One rendering of an item for the dialog and the item page (ADR 0112): its stat groups, tags,
// pictures, and descriptions, its own and those it inherits from its prototypes (ADR 0111).

import { blobUrl, type components } from '../../lib/api';
import { type Renderer, showDescriptions } from '../../lib/descriptions';
import { itemPageHref } from '../../lib/entityLinks';
import { statLabel } from '../../lib/statLabel';
import { fromTemplate, requiredIn } from '../../lib/template';
import {
  HIDDEN_SOURCE_LABEL,
  isFromHiddenEntry,
  type TextOrigin,
  textHome,
  textSources,
} from '../../lib/textSources';
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

    link.href = itemPageHref(options.tenantId, { entity_id: source.id });
    link.textContent = source.name;
  }

  function sourceLabel(source: Source): HTMLElement | null {
    if (!source) return null;

    const label = required<HTMLElement>(fromTemplate(root, '[data-source-template]'), 'p');

    fillSource(label, source);

    return label;
  }

  // "From a hidden entry": what an item inherits from an entry its library hides, never named
  // (ADR 0437).
  function hiddenLabel(): HTMLElement {
    const label = document.createElement('p');

    label.className = 'caption';
    label.textContent = HIDDEN_SOURCE_LABEL;

    return label;
  }

  const labelOf = (part: TextOrigin): HTMLElement | null =>
    isFromHiddenEntry(part) ? hiddenLabel() : sourceLabel(part.from_entity ?? null);

  let turn = 0;
  let facts: HTMLElement | null = null;
  return {
    show(item) {
      const mine = ++turn;
      facts?.remove();
      facts = document.createElement('section');
      root.append(facts);
      renderFactsAbout(facts, options.tenantId, item.entity_id);
      descriptions.replaceChildren();
      pictures.replaceChildren();
      pictures.hidden = true;
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

      const fallback = () =>
        showDescriptions(
          descriptions,
          options.renderer,
          item.descriptions.map((description) => ({
            text: description.content,
            label: labelOf(description),
            home: textHome(description, item.entity_id),
          })),
        );
      // The item read retains its flat text/picture contract. Read each visible source's
      // description bundles for their shared order, including image-only descriptions. What a
      // hidden entry gives is not readable by its address, so it comes from the item read.
      const sources = textSources(item.entity_id, [...item.descriptions, ...item.pictures]);
      void Promise.all(
        sources.map(async (source) => ({
          source,
          infos:
            source.kind === 'hidden'
              ? []
              : await listInformation(options.tenantId, source.id, ['description']),
        })),
      )
        .then((found) => {
          if (mine !== turn) return;
          const bundledUrls = new Set(
            found.flatMap(({ infos }) =>
              infos.flatMap((info) =>
                info.payloads.filter((p) => p.kind === 'picture').map((p) => p.url),
              ),
            ),
          );
          descriptions.replaceChildren();
          for (const { source, infos } of found) {
            if (source.kind === 'hidden') {
              for (const description of item.descriptions.filter(isFromHiddenEntry)) {
                const mount = document.createElement('div');
                descriptions.append(hiddenLabel(), mount);
                void showDescriptions(mount, options.renderer, [
                  { text: description.content, home: textHome(description, item.entity_id) },
                ]);
              }
              continue;
            }
            const home = source.id;
            for (const info of infos) {
              const mount = document.createElement('div');
              const label = source.kind === 'entry' ? sourceLabel(source.source) : null;
              if (label) descriptions.append(label);
              descriptions.append(mount);
              renderInformationPayloads(mount, {
                information: info,
                loadFile: (payload) => blobUrl(payload.url),
                renderText: (host, text) =>
                  showDescriptions(host, options.renderer, [{ text, home }]),
              });
            }
          }
          const remainingPictures = item.pictures.filter(
            (picture) => !bundledUrls.has(picture.url),
          );
          pictures.hidden = remainingPictures.length === 0;
          pictures.replaceChildren(
            ...remainingPictures.map((picture) => {
              const figure = required<HTMLElement>(
                fromTemplate(root, '[data-picture-template]'),
                'figure',
              );
              const image = required<HTMLImageElement>(figure, '[data-image]');
              const caption = required<HTMLElement>(figure, '[data-caption]');

              image.alt = picture.from_entity
                ? `Picture of ${picture.from_entity.name}`
                : isFromHiddenEntry(picture)
                  ? 'Picture from a hidden entry'
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
              } else if (isFromHiddenEntry(picture)) {
                caption.textContent = HIDDEN_SOURCE_LABEL;
                caption.hidden = false;
              } else {
                caption.remove();
              }

              return figure;
            }),
          );
        })
        .catch(() => {
          if (mine === turn) void fallback();
        });
    },
  };
}
