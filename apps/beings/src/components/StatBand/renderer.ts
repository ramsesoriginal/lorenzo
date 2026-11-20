// The stat area of a being's sheet (RFC 0043): a surface of its own with a group at a time, numbers as
// tiles and the rest as rows, and the being's tags as chips in its header. The grammar of the brand's
// information visualisation: solid is set on the being, dashed is inherited or calculated, and the
// words say so too.
//
// What a mode does here: Read draws and nothing more. Play lets the person change what the library
// calls adjustable, one change at a time and each one undoable: a number with a stepper and an
// adjuster ("take away 7"), a tag with a toggle. In Read, a number a person may set has an Edit
// button that turns it into a field, which saves on its own. Every control is a convenience; the API refuses what the viewer may not do, and the page says so.

import { applyChange, nextValue, parseChange, UndoStack } from '../../lib/adjust';
import { getEntityDetail } from '../../lib/entities';
import { errorMessage } from '../../lib/errorMessage';
import { explain } from '../../lib/explain';
import type { Layout, Mode } from '../../lib/sheetMode';
import { currentShell } from '../../lib/shell';
import { type BandGroup, bandOf, type Tag, type Tile, tagsOf, valueText } from '../../lib/statBand';
import { statLabel } from '../../lib/statLabel';
import {
  clearStat,
  getExplanation,
  parseStat,
  type Seen,
  StatChangedError,
  setStat,
  statVocabulary,
} from '../../lib/statValues';
import { setTag } from '../../lib/tagEditor';
import { requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';
import { icon } from '../BeingList/views';

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
  // After the steps that can be undone changed in number, with the last one's words, so the band
  // can say what its Undo would take back.
  onSteps?: (count: number, last: string | null) => void;
  // A line that says Saving, Saved or what went wrong.
  say: (message: string, failed?: boolean) => void;
};

export type RenderedStatBand = {
  /** Loads the library's stat vocabulary; without it (not a member) stats are drawn ungrouped. */
  load(beingStatGroupId?: string | null): Promise<void>;
  /** Draws the being as `mode` shows it, for someone who `canEdit` or not; returns the groups drawn. */
  show(entity: EntityDetail, mode: Mode, canEdit: boolean, layout: Layout): BandGroup[];
  /** The library's stat vocabulary, as loaded. */
  vocabulary(): Vocabulary;
  /** Takes the last change back, if there is one. */
  undo(): Promise<void>;
  /**
   * Sends these stats (by definition id) back to these values, in one go: a step of History's
   * "undo back to before". A null value takes the being's own value away.
   */
  restore(values: ReadonlyMap<string, boolean | number | string | null>): Promise<void>;
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
  const chips = required<HTMLElement>(page, '[data-tag-chips]');
  const bandConditions = required<HTMLElement>(page, '[data-band-conditions]');
  const pins = required<HTMLElement>(page, '[data-pins]');
  const conditions = required<HTMLElement>(root, '[data-conditions]');

  let vocabulary: Vocabulary = [];
  let beingStatGroupId: string | null = null;
  let entity: EntityDetail | null = null;
  let mode: Mode = 'read';
  let canEdit = false;
  let layout: Layout = 'sheet';
  let busy = false;
  // The name of the tile whose adjuster is open.
  let adjusting: string | null = null;
  // The names of the numbers being edited in place, in Read.
  const editingNames = new Set<string>();
  // The name of the calculated number whose explanation is open.
  let whyOpen: string | null = null;
  let lastLabel: string | null = null;
  // The tile just changed and by how much, drawn for a moment.
  let flash: { name: string; delta: string } | null = null;
  const history = new UndoStack(30);
  let toast: { dismiss(): void } | null = null;
  let drawn: BandGroup[] = [];

  const names = () =>
    new Map(vocabulary.map((entry) => [entry.definition.id, entry.definition.name]));

  /** The shell's Undo toast for the step just made: "Hit points 9 → 8", by you. */
  function showUndoBar(label: string) {
    toast?.dismiss();
    toast =
      currentShell()?.undoable({
        title: label,
        text: 'by you',
        undo: () => void undo(),
      }) ?? null;
    lastLabel = label;
    options.onSteps?.(history.size, label);
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

      toast?.dismiss();
      toast = null;
      lastLabel = null;
      options.onSteps?.(history.size, lastLabel);

      options.say('Saved.');
      if (entity) options.onChanged(entity);
    } catch (error) {
      options.say(errorMessage(error), true);
    } finally {
      busy = false;
    }
  }

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
    const label = el('label', 'field-label', 'Change by');
    const amount = el('input', 'text-input');
    const actions = el('div', 'adjust-actions');

    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', `Change ${tile.label}`);
    amount.id = 'adjust-amount';
    label.htmlFor = amount.id;
    amount.type = 'text';
    amount.inputMode = 'numeric';
    amount.placeholder = '-5, +3 or 12';
    amount.setAttribute('aria-describedby', 'adjust-help');

    const help = el('span', 'caption', 'Type 12 to set it, or +3 or -5 to change it.');

    help.id = 'adjust-help';

    const apply = () => {
      const wanted = parseChange(amount.value);

      if (wanted === null || typeof tile.value !== 'number') {
        options.announce('That is not a number. Type 12 to set it, or +3 or -5 to change it.');
        options.say('That is not a number. Type 12 to set it, or +3 or -5 to change it.', true);
        amount.focus();
        return;
      }

      setNumber(tile, applyChange(tile.value, wanted, tile.floor));
    };
    const go = el('button', 'btn btn-secondary', 'Apply');

    go.type = 'button';
    go.addEventListener('click', apply);
    amount.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        apply();
      }
    });
    actions.append(go);

    const close = el('button', 'btn btn-quiet', 'Close');

    close.type = 'button';
    close.addEventListener('click', () => {
      adjusting = null;
      redraw();
      page
        .querySelector<HTMLElement>(`[data-stat="${quoted(tile.name)}"] .stat-value-btn`)
        ?.focus();
    });
    panel.append(label, amount, help, actions, close);

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

  /** Where an inherited number comes from; a calculated one has its fx button instead. */
  function provenanceElement(tile: Tile): HTMLElement | null {
    if (tile.computed && tile.id) return null;

    const words = provenance(tile);

    return words ? el('span', 'stat-prov', words) : null;
  }

  /** The fx button of a calculated number: it opens how the number came to be (BN6). */
  function whyButton(tile: Tile): HTMLButtonElement | null {
    if (!(tile.computed && tile.id)) return null;

    const open = whyOpen === tile.name;
    const button = el('button', 'icon-btn stat-why');

    button.type = 'button';
    button.setAttribute('aria-label', `Why is ${tile.label} ${valueText(tile)}?`);
    button.setAttribute('aria-expanded', String(open));
    button.append(icon('formula'));
    button.addEventListener('click', () => {
      whyOpen = open ? null : tile.name;
      redraw();
    });

    return button;
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

  // A number a person may set in Read: not a calculated one, and one the library lets them name.
  const settable = (tile: Tile) => mode === 'read' && canEdit && !tile.computed && Boolean(tile.id);
  const editable = (tile: Tile) => settable(tile) && editingNames.has(tile.name);

  /** The button that turns a number into a field and back (BN2: edit where it is). */
  function editToggle(tile: Tile): HTMLButtonElement | null {
    if (!settable(tile)) return null;

    const open = editingNames.has(tile.name);
    const button = el('button', 'icon-btn stat-edit');

    button.type = 'button';
    button.append(icon(open ? 'select-item' : 'edit'));
    button.dataset.editStat = '';
    button.setAttribute('aria-label', `${open ? 'Done editing' : 'Edit'} ${tile.label}`);
    button.setAttribute('aria-pressed', String(open));
    button.addEventListener('click', () => {
      if (open) editingNames.delete(tile.name);
      else editingNames.add(tile.name);
      redraw();
      page
        .querySelector<HTMLElement>(
          `[data-stat="${quoted(tile.name)}"] ${open ? '[data-edit-stat]' : 'input, select'}`,
        )
        ?.focus({ preventScroll: true });
    });

    return button;
  }

  // ---- tiles and rows ---------------------------------------------------------------------------

  /** A tile on the sheet, in the band or in a cell of a datasheet line: the same stat, drawn denser. */
  function tileElement(tile: Tile, cell = false, big = false): HTMLElement {
    const base = cell ? 'ds-cell' : 'stat-tile';
    const classes = [base, tile.own && !tile.computed ? '' : 'is-derived', big ? 'is-big' : ''];
    const box = el('div', classes.filter(Boolean).join(' '));
    const head = el('div', 'stat-head');
    const foot = el('div', 'stat-foot');
    const max = tile.numeric && tile.of !== null ? el('span', 'stat-max', `/ ${tile.of}`) : null;
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

    head.append(el('span', 'stat-label', tile.label));

    const why = whyButton(tile);
    const toggle = editToggle(tile);

    if (why) head.append(why);
    else if (toggle) head.append(toggle);

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

    const row = el('div', 'stat-valuerow');

    row.append(value);
    if (max) row.append(max);

    box.dataset.stat = tile.name;
    box.append(head, row);

    // A bar for a number with a limit: how much of it is left.
    if (typeof tile.value === 'number' && typeof tile.of === 'number' && tile.of > 0) {
      const bar = el('div', 'stat-bar');
      const fill = el('i');

      bar.setAttribute('aria-hidden', 'true');
      fill.style.width = `${Math.max(0, Math.min(100, Math.round((tile.value / tile.of) * 100)))}%`;
      bar.append(fill);
      box.append(bar);
    }

    const sub = tile.resolved ? el('span', 'stat-sub', tile.resolved) : null;

    if (sub) box.append(sub);
    box.append(foot);

    if (whyOpen === tile.name && whyButton(tile)) {
      const panel = el('div', 'why-panel');

      box.append(panel);
      void fillExplanation(tile, panel);
    }

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

    const toggle = editToggle(row);

    if (toggle) {
      // The row is a <dd>: the button sits inside it, after the value, and names the stat it is for.
      detail.dataset.stat = row.name;
      detail.append(toggle);
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

  function chip(label: string, state: string, from: string | null = null): HTMLElement {
    const node = el('span', 'tag-toggle tag-chip', label);

    node.dataset.state = state;
    if (state === 'inherited' && from) node.title = `From ${from}`;

    return node;
  }

  /**
   * The conditions that are on, in the band (BN10), and the Conditions row of the Stats: chips in
   * Read, and in Play a toggle for each condition the library lets a table change (BN3).
   */
  function drawTags(current: EntityDetail) {
    const tags = tagsOf(vocabulary, current);
    const isOn = (tag: Tag) =>
      current.stats.some((stat) => stat.name === tag.name && stat.value === true);
    const onChips: HTMLElement[] = [];
    const rowItems: HTMLElement[] = [];
    const toggles: HTMLElement[] = [];

    if (tags.length === 0) {
      // A viewer who cannot list the library's tags still sees the ones that are on.
      for (const stat of current.stats.filter((candidate) => candidate.value === true)) {
        const state = stat.own ? 'on' : 'inherited';

        onChips.push(chip(statLabel(stat.name), state));
        rowItems.push(chip(statLabel(stat.name), state));
      }
    }

    for (const tag of tags) {
      const on = isOn(tag);
      const state = tag.state === 'inherited' ? 'inherited' : 'on';

      if (on) {
        onChips.push(chip(tag.label, state, tag.from));
        rowItems.push(chip(tag.label, state, tag.from));
      }

      if (mode === 'play' && canEdit && tag.adjustable) {
        const button = el('button', 'tag-toggle');

        button.type = 'button';
        button.dataset.state = on ? state : 'off';
        button.setAttribute('aria-pressed', String(on));
        button.append(icon(on ? 'select-item' : 'add'), el('span', '', tag.label));
        button.addEventListener('click', () => toggleTag(tag, on));
        toggles.push(button);
      }
    }

    chips.replaceChildren(...onChips);
    bandConditions.hidden = onChips.length === 0;

    const items = toggles.length > 0 ? toggles : rowItems;

    conditions.hidden = items.length === 0 && tags.length === 0;
    conditions.replaceChildren(
      el('span', 'stat-label', 'Conditions'),
      ...(items.length > 0
        ? [wrapGroup(items, toggles.length > 0)]
        : [el('span', 'is-muted', 'None')]),
    );
  }

  function wrapGroup(items: HTMLElement[], playing: boolean): HTMLElement {
    const group = el('span', 'conditions-group');

    if (playing) group.setAttribute('role', 'group');
    if (playing) group.setAttribute('aria-label', 'Conditions');
    group.append(...items);

    return group;
  }

  // ---- drawing ----------------------------------------------------------------------------------

  /** The changed tile gets a short highlight and the amount; both go away by themselves. */
  function applyFlash() {
    const shown = flash;

    flash = null;

    if (!shown) return;

    const tile = [pins, layout === 'datasheet' ? lines : groups]
      .map((host) => host.querySelector<HTMLElement>(`[data-stat="${quoted(shown.name)}"]`))
      .find(Boolean);

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

    const editing = mode === 'read' && canEdit;
    const focused = document.activeElement?.closest<HTMLElement>('[data-stat]')?.dataset.stat;

    drawn = bandOf(vocabulary, entity, { beingStatGroupId });

    // The pinned numbers are the band's: big tiles above, and not again among the stats (BN6).
    // Only what the library pins, and has a value: a number is in the band or among the stats, not both.
    const vitals = drawn
      .flatMap((group) => group.tiles)
      .filter((tile) => tile.pinned && tile.numeric && tile.value !== null);
    const pinned = new Set(vitals.map((tile) => tile.name));

    pins.replaceChildren(...vitals.map((tile) => tileElement(tile, false, true)));

    // Only the layout in view is drawn; the other is drawn when it is asked for.
    if (layout === 'datasheet') {
      lines.replaceChildren(...drawn.map(lineElement));
    } else {
      groups.replaceChildren(
        ...drawn
          .map((group) => ({
            ...group,
            tiles: group.tiles.filter((tile) => !pinned.has(tile.name)),
          }))
          .filter((group) => group.tiles.length + group.rows.length > 0)
          .map(groupElement),
      );
    }

    drawTags(entity);
    applyFlash();
    message.hidden = !(editing && vocabulary.length === 0);
    message.textContent =
      'Only library members can see the list of stats, so only the ones this being has can change.';

    // The adjuster takes the focus when it opens; otherwise the tile keeps it.
    const into = page;
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
    async load(selectedGroupId = null) {
      beingStatGroupId = selectedGroupId;
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
      if (mode !== 'read') editingNames.clear();
      redraw();

      return drawn;
    },
    undo,
    async restore(values) {
      if (busy || !entity) return;

      busy = true;
      options.say('Saving…');

      try {
        let current = await getEntityDetail(tenantId, entity.id);

        for (const [definitionId, value] of values) {
          const definition = vocabulary.find(
            (entry) => entry.definition.id === definitionId,
          )?.definition;

          if (!definition) continue;

          const now = current.stats.find((stat) => stat.name === definition.name);
          const seen = { value: now?.value ?? '', own: now?.own ?? false } as Seen;

          if (value === null) {
            if (now?.own) current = await clearStat(tenantId, current.id, definition, seen);
          } else if (typeof value === 'boolean') {
            current = await setTag(tenantId, current.id, definitionId, value ? 'on' : 'off');
          } else {
            current = await setStat(tenantId, current.id, definition, value, seen);
          }
        }

        entity = current;
        // What was undone before cannot be undone again after this: the steps are the new truth.
        history.clear();
        toast?.dismiss();
        toast = null;
        lastLabel = null;
        options.onSteps?.(0, null);
        options.announce('Went back.');
        options.say('Saved.');
        options.onChanged(current);
      } catch (error) {
        options.say(errorMessage(error), true);
        if (error instanceof StatChangedError) await reread();
      } finally {
        busy = false;
      }
    },
  };
}
