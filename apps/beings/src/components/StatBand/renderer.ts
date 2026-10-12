// The stat area of a being's sheet (RFC 0043): a surface of its own with a group at a time, numbers as
// tiles and the rest as rows. The grammar of the brand's information visualisation: solid is set on
// the being, dashed is inherited or calculated, and the words say so too.

import { type BandGroup, bandOf, type Tile, valueText } from '../../lib/statBand';
import { statDefinitions } from '../../lib/statValues';
import { requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

export type RenderedStatBand = {
  /** Loads the library's stat groups; stats of a library whose list can't be read go ungrouped. */
  load(tenantId: string): Promise<void>;
  /** Draws the being's stats and returns the groups drawn. */
  show(entity: EntityDetail): BandGroup[];
};

const required = requiredIn('Stat band');

/** What the tile says about where its number comes from, or nothing for a plain one. */
function provenance(tile: Tile): string {
  if (tile.computed) return 'Calculated';
  if (!tile.own && tile.from) return `From ${tile.from}`;
  if (!tile.own) return 'Inherited';

  return '';
}

function tileElement(tile: Tile): HTMLElement {
  const root = document.createElement('div');
  const label = document.createElement('span');
  const value = document.createElement('span');
  const sub = document.createElement('span');
  const foot = document.createElement('div');
  const derived = !tile.own || tile.computed;

  root.className = derived ? 'stat-tile is-derived' : 'stat-tile';
  label.className = 'stat-label';
  label.textContent = tile.label;
  value.className = 'stat-value';
  value.textContent = String(tile.value);

  if (tile.unit) {
    const unit = document.createElement('span');

    unit.className = 'unit';
    unit.textContent = tile.unit;
    value.append(unit);
  }

  sub.className = 'stat-sub';
  foot.className = 'stat-foot';

  const source = provenance(tile);

  if (source) {
    const note = document.createElement('span');

    note.className = 'stat-prov';
    note.textContent = source;
    foot.append(note);
  }

  root.dataset.stat = tile.name;
  root.append(label, value, sub, foot);

  return root;
}

function groupElement(group: BandGroup): HTMLElement {
  const root = document.createElement('div');

  root.className = 'stat-group';

  if (group.name) {
    const heading = document.createElement('h3');
    const count = document.createElement('span');
    const total = group.tiles.length + group.rows.length;

    heading.textContent = `${group.name} `;
    count.className = 'caption';
    count.textContent = `${total} ${total === 1 ? 'stat' : 'stats'}`;
    heading.append(count);
    root.append(heading);
  }

  if (group.tiles.length > 0) {
    const grid = document.createElement('div');

    grid.className = 'stat-grid';
    grid.replaceChildren(...group.tiles.map(tileElement));
    root.append(grid);
  }

  if (group.rows.length > 0) {
    const list = document.createElement('dl');

    list.className = 'stat-rows';
    list.replaceChildren(
      ...group.rows.flatMap((row) => {
        const term = document.createElement('dt');
        const detail = document.createElement('dd');

        term.textContent = row.label;
        detail.textContent = valueText(row);
        if (!row.own || row.computed) detail.className = 'is-derived';

        return [term, detail];
      }),
    );
    root.append(list);
  }

  return root;
}

// `root` is the <StatBand />.
export function renderStatBand(root: HTMLElement): RenderedStatBand {
  const groups = required<HTMLElement>(root, '[data-groups]');
  let definitions: Awaited<ReturnType<typeof statDefinitions>> = [];

  return {
    async load(tenantId) {
      // Listing definitions needs library membership; without it the stats are drawn ungrouped.
      definitions = await statDefinitions(tenantId).catch(() => []);
    },
    show(entity) {
      const drawn = bandOf(definitions, entity);

      groups.replaceChildren(...drawn.map(groupElement));

      return drawn;
    },
  };
}
