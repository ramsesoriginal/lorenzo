// The stat area of a being's sheet (RFC 0043): a surface of its own with a group at a time, numbers as
// tiles and the rest as rows, and the being's tags as chips in its header. The grammar of the brand's
// information visualisation: solid is set on the being, dashed is inherited or calculated, and the
// words say so too.
//
// What a mode does here: Read draws and nothing more. Play lets the person change what the library
// calls adjustable, one change at a time and each one undoable: a number with a stepper and an
// adjuster ("take away 7"), a tag with a toggle. Edit makes every value a field. Every control is a
// convenience; the API refuses what the viewer may not do, and the page says so.

import { nextValue, parseAmount, UndoStack } from '../../lib/adjust';
import { getEntityDetail } from '../../lib/entities';
import { errorMessage } from '../../lib/errorMessage';
import { explain } from '../../lib/explain';
import type { Layout, Mode } from '../../lib/sheetMode';
import {
  type BandGroup,
  bandOf,
  captionOf,
  type Tag,
  type Tile,
  tagsOf,
  valueText,
} from '../../lib/statBand';
import { statLabel } from '../../lib/statLabel';
import {
  clearStat,
  getExplanation,
  parseStat,
  StatChangedError,
  setStat,
  statVocabulary,
} from '../../lib/statValues';
import { setTag } from '../../lib/tagEditor';
import { requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

type Vocabulary = Awaited<ReturnType<typeof statVocabulary>>;

export type StatBandVocabulary = Vocabulary;

export type StatBandOptions = {
  // The <StatBand />.
  root: HTMLElement;
  // The page, where the tag chips and the undo bar are.
  page: HTMLElement;
  // Where the datasheet's stat lines go; the same stats, drawn as cells (RFC 0043).
  lines: HTMLElement;
  tenantId: string;
  // After a write, with the being as it now is, so the whole page can show it.
  onChanged: (entity: EntityDetail) => void;
  // Says what changed to screen readers.
  announce: (message: string) => void;
  // A line that says Saving, Saved or what went wrong.
  say: (message: string, failed?: boolean) => void;
};

export type RenderedStatBand = {
  /** Loads the library's stat vocabulary; without it (not a member) stats are drawn ungrouped. */
  load(): Promise<void>;
  /** Draws the being as `mode` shows it, for someone who `canEdit` or not; returns the groups drawn. */
  show(entity: EntityDetail, mode: Mode, canEdit: boolean, layout: Layout): BandGroup[];
  /** The library's stat vocabulary, as loaded. */
  vocabulary(): Vocabulary;
  /** Takes the last change back, if there is one. */
  undo(): Promise<void>;
};

const required = requiredIn('Stat band');

/** What the tile says about where its number comes from, or nothing for a plain one. */
function provenance(tile: Tile): string {
  if (tile.computed) return 'Calculated';
  if (!tile.own && tile.value !== null && tile.from) return `From ${tile.from}`;
  if (!tile.own && tile.value !== null) return 'Inherited';

  return '';
}

const el = <K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className = '',
  text = '',
): HTMLElementTagNameMap[K] => {
  const element = document.createElement(tag);

  if (className) element.className = className;
  if (text) element.textContent = text;

  return element;
};

function iconButton(label: string, text: string, onClick: () => void): HTMLButtonElement {
  const button = el('button', 'icon-btn', text);

  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.addEventListener('click', onClick);

  return button;
}

const quoted = (name: string) => CSS.escape(name);

// `options.root` is the <StatBand />.
export function renderStatBand(options: StatBandOptions): RenderedStatBand {
  const { root, page, lines, tenantId } = options;
  const groups = required<HTMLElement>(root, '[data-groups]');
  const message = required<HTMLElement>(root, '[data-message]');
  const chips = required<HTMLUListElement>(page, '[data-tag-chips]');
  const undoBar = required<HTMLElement>(page, '[data-undo-bar]');
  const undoText = required<HTMLElement>(undoBar, '[data-undo-text]');
  const undoButton = required<HTMLButtonElement>(undoBar, '[data-undo]');

  let vocabulary: Vocabulary = [];
  let entity: EntityDetail | null = null;
  let mode: Mode = 'read';
  let canEdit = false;
  let layout: Layout = 'sheet';
  let busy = false;
  // The name of the tile whose adjuster is open.
  let adjusting: string | null = null;
  // The tile just changed and by how much, drawn for a moment.
  let flash: { name: string; delta: string } | null = null;
  const history = new UndoStack(30);
  let undoTimer: number | undefined;
  let drawn: BandGroup[] = [];

  const names = () =>
    new Map(vocabulary.map((entry) => [entry.definition.id, entry.definition.name]));

  function showUndoBar(label: string) {
    undoText.textContent = label;
    undoBar.hidden = false;
    window.clearTimeout(undoTimer);
    undoTimer = window.setTimeout(() => {
      undoBar.hidden = true;
    }, 9000);
  }

  /** The being as it is now, after a write that found it changed (or that failed). */
  async function reread() {
    if (!entity) return;

    entity = await getEntityDetail(tenantId, entity.id).catch(() => entity);
    if (entity) options.onChanged(entity);
  }

  /** Every change in Play goes through here: write it, remember how to take it back, say what happened. */
  async function change(
    label: string,
    flashed: { name: string; delta: string } | null,
    write: () => Promise<EntityDetail>,
    revert: () => Promise<EntityDetail>,
  ) {
    if (busy) return;

    busy = true;
    options.say('Saving…');

    try {
      const next = await write();

      entity = next;
      history.push({
        label,
        undo: async () => {
          entity = await revert();
        },
      });
      flash = flashed;
      adjusting = null;
      options.announce(label);
      showUndoBar(label);
      options.say('Saved.');
      options.onChanged(next);
    } catch (error) {
      options.say(errorMessage(error), true);
      if (error instanceof StatChangedError) await reread();
    } finally {
      busy = false;
    }
  }

  async function undo() {
    if (busy) return;

    const last = history.pop();

    if (!last) return;

    busy = true;
    options.say('Saving…');

    try {
      await last.undo();
      flash = null;
      options.announce(`Undone: ${last.label}`);

      if (history.size > 0) showUndoBar(`Undone: ${last.label}`);
      else undoBar.hidden = true;

      options.say('Saved.');
      if (entity) options.onChanged(entity);
    } catch (error) {
      options.say(errorMessage(error), true);
    } finally {
      busy = false;
    }
  }

  undoButton.addEventListener('click', () => void undo());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && adjusting) {
      const name = adjusting;

      adjusting = null;
      redraw();
      page.querySelector<HTMLElement>(`[data-stat="${quoted(name)}"] .stat-value-btn`)?.focus();
    }

    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName ?? '');

    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z' && !typing) {
      event.preventDefault();
      void undo();
    }
  });
  document.addEventListener('click', (event) => {
    const target = event.target as Element;

    if (adjusting && !target.closest('.adjust') && !target.closest('[data-adjust-open]')) {
      adjusting = null;
      redraw();
    }
  });

  // ---- numbers --------------------------------------------------------------------------------

  const definitionOf = (tile: Tile) =>
    vocabulary.find((entry) => entry.definition.id === tile.id)?.definition;

  /** Sets a number, saying what it was and is ("Hit points 31 → 24"), and how to go back. */
  function setNumber(tile: Tile, next: number) {
    const definition = definitionOf(tile);
    const old = tile.value;

    if (!definition || typeof old !== 'number' || next === old) {
      adjusting = null;
      redraw();
      return;
    }

    const id = entity?.id ?? '';
    const seen = { value: old, own: tile.own };
    const after = { value: next, own: true };
    const delta = next - old;

    void change(
      `${tile.label} ${old} → ${next}`,
      { name: tile.name, delta: `${delta > 0 ? '+' : '−'}${Math.abs(delta)}` },
      () => setStat(tenantId, id, definition, next, seen),
      () =>
        tile.own
          ? setStat(tenantId, id, definition, old, after)
          : clearStat(tenantId, id, definition, after),
    );
  }

  const canAdjust = (tile: Tile) =>
    mode === 'play' &&
    canEdit &&
    tile.adjustable &&
    tile.numeric &&
    !tile.computed &&
    typeof tile.value === 'number' &&
    Boolean(tile.id);

  function adjusterFor(tile: Tile): HTMLElement {
    const panel = el('div', 'adjust');
    const label = el('label', 'field-label', 'Amount');
    const amount = el('input', 'text-input');
    const actions = el('div', 'adjust-actions');

    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', `Change ${tile.label}`);
    amount.id = 'adjust-amount';
    label.htmlFor = amount.id;
    amount.type = 'number';
    amount.inputMode = 'numeric';
    amount.min = '0';
    amount.value = '1';

    const apply = (operation: 'sub' | 'add' | 'set') => () => {
      const wanted = parseAmount(amount.value);

      if (wanted === null || typeof tile.value !== 'number') {
        options.announce('Enter an amount, zero or more.');
        amount.focus();
        return;
      }

      setNumber(tile, nextValue(tile.value, operation, wanted, tile.floor));
    };

    for (const [text, operation] of [
      ['Take away', 'sub'],
      ['Add', 'add'],
      ['Set to', 'set'],
    ] as const) {
      const button = el('button', 'btn btn-secondary', text);

      button.type = 'button';
      button.addEventListener('click', apply(operation));
      actions.append(button);
    }

    const close = el('button', 'btn btn-quiet', 'Close');

    close.type = 'button';
    close.addEventListener('click', () => {
      adjusting = null;
      redraw();
      page
        .querySelector<HTMLElement>(`[data-stat="${quoted(tile.name)}"] .stat-value-btn`)
        ?.focus();
    });
    panel.append(label, amount, actions, close);

    return panel;
  }

  async function fillExplanation(tile: Tile, panel: HTMLElement) {
    panel.replaceChildren(el('p', 'status-text', 'Working it out…'));

    try {
      const explanation = await getExplanation(tenantId, entity?.id ?? '', tile.id);
      const { text, parts } = explain(explanation, names());
      const list = el('dl');

      for (const part of parts) {
        list.append(el('dt', '', part.label), el('dd', '', part.value));
      }

      list.append(el('dt', '', 'Total'), el('dd', '', String(explanation.value)));
      panel.replaceChildren(el('p', '', text), list);
    } catch (error) {
      panel.replaceChildren(el('p', 'error-text', errorMessage(error)));
    }
  }

  function provenanceElement(tile: Tile): HTMLElement | null {
    const words = provenance(tile);

    if (!words) return null;

    if (tile.computed && tile.id) {
      const details = el('details', 'why');
      const panel = el('div', 'why-panel');

      details.append(el('summary', '', words), panel);
      details.addEventListener('toggle', () => {
        if (details.open) void fillExplanation(tile, panel);
      });

      return details;
    }

    return el('span', 'stat-prov', words);
  }

  // ---- fields (Edit) ----------------------------------------------------------------------------

  /** A value written in Edit: it saves as you go, and is not one of Play's undoable steps. */
  async function editStat(tile: Tile, value: number | string, clear = false) {
    const definition = definitionOf(tile);

    if (!definition || !entity || busy) return;

    busy = true;
    options.say('Saving…');

    const seen = { value: tile.value as number | string, own: tile.own };

    try {
      entity = clear
        ? await clearStat(tenantId, entity.id, definition, seen)
        : await setStat(tenantId, entity.id, definition, value, seen);
      options.say('Saved.');
      options.onChanged(entity);
    } catch (error) {
      options.say(errorMessage(error), true);
      if (error instanceof StatChangedError) await reread();
    } finally {
      busy = false;
    }
  }

  function fieldFor(tile: Tile): HTMLElement {
    const definition = definitionOf(tile);

    if (!definition) return el('span', 'stat-value', valueText(tile));

    const current = tile.value === null ? '' : String(tile.value);
    const commit = (text: string, restore: () => void) => {
      if (text === current) return;

      const parsed = parseStat(definition, text);

      if ('problem' in parsed) {
        options.say(`${tile.label}: ${parsed.problem}`, true);
        restore();
        return;
      }

      void editStat(tile, parsed.value);
    };

    if (definition.value_type === 'enum') {
      const select = el('select', 'text-input');

      select.setAttribute('aria-label', tile.label);

      if (tile.value === null) select.append(new Option('Choose a value', ''));

      for (const value of definition.enum_values) select.append(new Option(value, value));

      select.value = current;
      select.addEventListener('change', () => {
        if (select.value) commit(select.value, () => {});
      });

      return select;
    }

    const input = el('input', 'text-input');

    input.type = 'text';
    input.value = current;
    input.setAttribute('aria-label', tile.label);
    if (tile.numeric) input.inputMode = definition.value_type === 'int' ? 'numeric' : 'decimal';
    input.addEventListener('change', () => {
      commit(input.value, () => {
        input.value = current;
      });
    });

    return input;
  }

  function inheritButton(tile: Tile): HTMLButtonElement {
    const button = el('button', 'btn btn-quiet', 'Use inherited');

    button.type = 'button';
    button.setAttribute('aria-label', `Use inherited ${tile.label}`);
    button.addEventListener('click', () => void editStat(tile, '', true));

    return button;
  }

  const editable = (tile: Tile) => mode === 'edit' && canEdit && !tile.computed && Boolean(tile.id);

  // ---- tiles and rows ---------------------------------------------------------------------------

  /** A tile on the sheet, or a cell of a datasheet line: the same stat, drawn denser. */
  function tileElement(tile: Tile, cell = false): HTMLElement {
    const base = cell ? 'ds-cell' : 'stat-tile';
    const box = el('div', tile.own && !tile.computed ? base : `${base} is-derived`);
    const foot = el('div', 'stat-foot');
    let value: HTMLElement;

    if (editable(tile)) {
      value = fieldFor(tile);
    } else if (canAdjust(tile)) {
      const button = el('button', 'stat-value stat-value-btn', String(tile.value));
      const open = adjusting === tile.name;

      button.type = 'button';
      button.dataset.adjustOpen = '';
      button.setAttribute('aria-haspopup', 'dialog');
      button.setAttribute('aria-expanded', String(open));
      button.setAttribute('aria-label', `Change ${tile.label}, now ${tile.value}`);
      button.addEventListener('click', () => {
        adjusting = open ? null : tile.name;
        redraw();
      });
      if (tile.unit) button.append(el('span', 'unit', tile.unit));
      value = button;
    } else {
      value = el('span', 'stat-value', valueText({ ...tile, unit: null }));
      if (tile.unit && tile.value !== null) value.append(el('span', 'unit', tile.unit));
    }

    const source = provenanceElement(tile);

    if (source) foot.append(source);
    if (editable(tile) && tile.own) foot.append(inheritButton(tile));

    if (canAdjust(tile)) {
      const stepper = el('span', 'stat-stepper');
      const step = (direction: 'step-down' | 'step-up') => () => {
        if (typeof tile.value === 'number') {
          setNumber(tile, nextValue(tile.value, direction, 1, tile.floor));
        }
      };

      stepper.append(
        iconButton(`Lower ${tile.label} by 1`, '−', step('step-down')),
        iconButton(`Raise ${tile.label} by 1`, '+', step('step-up')),
      );
      foot.append(stepper);

      if (adjusting === tile.name) foot.append(adjusterFor(tile));
    }

    box.dataset.stat = tile.name;
    // Always four children, so the label, value, caption and foot of a row of tiles line up.
    box.append(
      el('span', 'stat-label', tile.label),
      value,
      el('span', 'stat-sub', captionOf(tile)),
      foot,
    );

    return box;
  }

  function rowElements(row: Tile): HTMLElement[] {
    const term = el('dt', '', row.label);
    const detail = el('dd');

    if (editable(row)) {
      detail.append(fieldFor(row));
      if (row.own) detail.append(inheritButton(row));
    } else {
      detail.textContent = valueText(row);
    }

    if (!row.own || row.computed) detail.classList.add('is-derived');

    return [term, detail];
  }

  /** A group of the datasheet: one line of labelled cells. */
  function lineElement(group: BandGroup): HTMLElement {
    const box = el('div', 'ds-line');
    const cells = el('div', 'ds-cells');

    if (group.name) box.append(el('h3', '', group.name));

    cells.replaceChildren(
      ...[...group.tiles, ...group.rows].map((tile) => tileElement(tile, true)),
    );
    box.append(cells);

    return box;
  }

  function groupElement(group: BandGroup): HTMLElement {
    const box = el('div', 'stat-group');

    if (group.name) {
      const heading = el('h3', '', `${group.name} `);
      const total = group.tiles.length + group.rows.length;

      heading.append(el('span', 'caption', `${total} ${total === 1 ? 'stat' : 'stats'}`));
      box.append(heading);
    }

    if (group.tiles.length > 0) {
      const grid = el('div', 'stat-grid');

      grid.replaceChildren(...group.tiles.map((tile) => tileElement(tile)));
      box.append(grid);
    }

    if (group.rows.length > 0) {
      const list = el('dl', 'stat-rows');

      list.replaceChildren(...group.rows.flatMap(rowElements));
      box.append(list);
    }

    return box;
  }

  // ---- tags -------------------------------------------------------------------------------------

  /** A tag in Play: pressed when it is in force, and one tap flips it. */
  function toggleTag(tag: Tag, isOn: boolean) {
    const id = entity?.id ?? '';
    const next = isOn ? 'off' : 'on';

    void change(
      `${tag.label} ${next}`,
      null,
      () => setTag(tenantId, id, tag.id, next),
      () => setTag(tenantId, id, tag.id, tag.state),
    );
  }

  function drawTags(current: EntityDetail) {
    const tags = tagsOf(vocabulary, current);
    const isOn = (tag: Tag) =>
      current.stats.some((stat) => stat.name === tag.name && stat.value === true);
    const items: HTMLElement[] = [];

    if (tags.length === 0) {
      // A viewer who cannot list the library's tags still sees the ones that are on.
      for (const stat of current.stats.filter((candidate) => candidate.value === true)) {
        const item = el('li');
        const chip = el('span', 'tag-toggle', statLabel(stat.name));

        chip.dataset.state = stat.own ? 'on' : 'inherited';
        item.append(chip);
        items.push(item);
      }
    }

    for (const tag of tags) {
      const on = isOn(tag);
      const playable = mode === 'play' && canEdit && tag.adjustable;

      if (!on && !playable) continue;

      const item = el('li');

      if (playable) {
        const button = el('button', 'tag-toggle', tag.label);

        button.type = 'button';
        button.dataset.state = on ? (tag.state === 'inherited' ? 'inherited' : 'on') : 'off';
        button.setAttribute('aria-pressed', String(on));
        button.addEventListener('click', () => toggleTag(tag, on));
        item.append(button);
      } else {
        const chip = el('span', 'tag-toggle', tag.label);

        chip.dataset.state = tag.state === 'inherited' ? 'inherited' : 'on';
        if (tag.state === 'inherited' && tag.from) chip.title = `From ${tag.from}`;
        item.append(chip);
      }

      items.push(item);
    }

    chips.hidden = items.length === 0;
    chips.replaceChildren(...items);
  }

  // ---- drawing ----------------------------------------------------------------------------------

  /** The changed tile gets a short highlight and the amount; both go away by themselves. */
  function applyFlash() {
    const shown = flash;

    flash = null;

    if (!shown) return;

    const tile = (layout === 'datasheet' ? lines : groups).querySelector<HTMLElement>(
      `[data-stat="${quoted(shown.name)}"]`,
    );

    if (!tile) return;

    const chip = el('span', 'stat-delta', shown.delta);

    chip.setAttribute('aria-hidden', 'true');
    tile.classList.add('is-changed');
    tile.append(chip);
    window.setTimeout(() => {
      tile.classList.remove('is-changed');
      chip.remove();
    }, 2600);
  }

  function redraw() {
    if (!entity) return;

    const editing = mode === 'edit' && canEdit;
    const focused = document.activeElement?.closest<HTMLElement>('[data-stat]')?.dataset.stat;

    drawn = bandOf(vocabulary, entity, { includeUnset: editing && vocabulary.length > 0 });

    // Only the layout in view is drawn; the other is drawn when it is asked for.
    const [into, draw] =
      layout === 'datasheet' ? ([lines, lineElement] as const) : ([groups, groupElement] as const);

    into.replaceChildren(...drawn.map(draw));
    drawTags(entity);
    applyFlash();
    message.hidden = !(editing && vocabulary.length === 0);
    message.textContent =
      'Only library members can see the list of stats, so only the ones this being has can change.';

    // The adjuster takes the focus when it opens; otherwise the tile keeps it.
    const amount = into.querySelector<HTMLInputElement>('#adjust-amount');

    if (amount) {
      amount.focus({ preventScroll: true });
      amount.closest('.adjust')?.scrollIntoView({ block: 'nearest' });
    } else if (focused) {
      const tile = `[data-stat="${quoted(focused)}"]`;

      into.querySelector<HTMLElement>(`${tile} button, ${tile} input`)?.focus({
        preventScroll: true,
      });
    }
  }

  return {
    async load() {
      // Listing definitions needs library membership; without it the stats are drawn ungrouped.
      vocabulary = await statVocabulary(tenantId).catch(() => []);
    },
    vocabulary: () => vocabulary,
    show(next, nextMode, nextCanEdit, nextLayout) {
      entity = next;
      mode = nextMode;
      canEdit = nextCanEdit;
      layout = nextLayout;
      if (mode !== 'play') adjusting = null;
      redraw();

      return drawn;
    },
    undo,
  };
}
