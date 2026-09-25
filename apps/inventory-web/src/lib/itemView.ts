// One rendering of an item for the board's panel and the item page (ADR 0112):
// its stat groups, tags, pictures, and descriptions, its own and those it
// inherits from its prototypes (ADR 0111).
import { blobUrl, type components } from './api';
import { type Renderer, showDescriptions } from './descriptions';

type Item = components['schemas']['ItemOut'];
type Source = components['schemas']['EntitySummary'] | null;

const GROUPS = [
  ['Physical', 'physical_stats'],
  ['Economic', 'economic_stats'],
  ['Destroyable', 'destroyable_stats'],
  ['Damaging', 'damaging_stats'],
] as const;

/**
 * A stat or tag name as readers see it: `is_magical` is "Magical", `max_hp` "Max HP". A word of
 * one or two letters is an abbreviation, like HP or AC.
 */
export function statLabel(name: string): string {
  const words = name
    .replace(/^is_/, '')
    .split('_')
    .map((word) => (word.length <= 2 ? word.toUpperCase() : word));
  const label = words.join(' ');
  return label.charAt(0).toUpperCase() + label.slice(1);
}

const make = <K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text = '') =>
  Object.assign(document.createElement(tag), { className, textContent: text });

/** "From Longsword", linking to it, for something an item inherits; nothing for its own. */
function sourceLabel(
  source: Source,
  tenantId: string,
  tag: 'p' | 'figcaption' = 'p',
): HTMLElement | null {
  if (!source) return null;
  const label = make(tag, 'item-view-source', 'From ');
  const link = make('a', '', source.name);
  link.href = `/item/?tenant=${tenantId}&id=${source.id}`;
  label.append(link);
  return label;
}

/** Renders `item` into `container`, replacing what was there. Descriptions render as LorenzoScript. */
export function renderItemView(
  container: HTMLElement,
  item: Item,
  options: { tenantId: string; renderer: Renderer },
): void {
  const sections: HTMLElement[] = [];

  for (const [heading, key] of GROUPS) {
    const set = item[key].filter((stat) => stat.value !== null);
    if (set.length === 0) continue;
    const section = make('section', 'item-view-group');
    const list = make('dl', 'item-detail-stats');
    for (const stat of set)
      list.append(make('dt', '', statLabel(stat.name)), make('dd', '', String(stat.value)));
    section.append(make('h3', '', heading), list);
    sections.push(section);
  }

  const on = item.tags.filter((tag) => tag.value === true);
  if (on.length > 0) {
    const tags = make('ul', 'chip-list item-view-tags');
    tags.append(...on.map((tag) => make('li', 'chip', statLabel(tag.name))));
    sections.push(tags);
  }

  if (item.pictures.length > 0) {
    const pictures = make('div', 'item-view-pictures');
    for (const picture of item.pictures) {
      const figure = make('figure', '');
      const img = make('img', '');
      img.alt = picture.from_entity
        ? `Picture of ${picture.from_entity.name}`
        : `Picture of ${item.title}`;
      blobUrl(picture.url).then(
        (src) => {
          img.src = src;
        },
        () => figure.remove(),
      );
      const caption = sourceLabel(picture.from_entity, options.tenantId, 'figcaption');
      figure.append(img, ...(caption ? [caption] : []));
      pictures.append(figure);
    }
    sections.push(pictures);
  }

  const descriptions = make('div', 'item-detail-descriptions');
  sections.push(descriptions);
  container.replaceChildren(...sections);
  void showDescriptions(
    descriptions,
    options.renderer,
    item.descriptions.map((description) => ({
      text: description.content,
      label: sourceLabel(description.from_entity, options.tenantId),
    })),
  );
}
