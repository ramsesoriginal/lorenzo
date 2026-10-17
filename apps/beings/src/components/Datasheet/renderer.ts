import { renderInformationPayloads } from '@lorenzo/information-editor';
import { blobUrl } from '../../lib/api';
// A being as a datasheet (RFC 0043): the stat lines are drawn by the stat band, which owns what
// changing a number means; this draws what the datasheet adds to them from the API's sheet read
// (ADR 0281): the equipped weapons as a table, and the abilities with the notes. A library that has
// not said which stat group holds a weapon's stats gets what the being carries instead.

import { getOwned } from '../../lib/being';
import { type Renderer, showDescriptions } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import { type Information, listInformation } from '../../lib/information';
import { getSheet } from '../../lib/sheet';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { weaponTable } from '../../lib/weapons';
import type { StatBandVocabulary } from '../StatBand/renderer';

export type DatasheetOptions = {
  // The <Datasheet />.
  root: HTMLElement;
  tenantId: string;
  renderer: Renderer;
  vocabulary: () => StatBandVocabulary;
};

export type RenderedDatasheet = {
  /** Draws the parts that are about the being itself: its name and description. */
  show(entity: { id: string; name: string; information: Information[] }): void;
  /** Reads the sheet and the notes and draws them; asked for when the datasheet is wanted. */
  load(entityId: string): Promise<void>;
  /** Whether the stat lines had anything to show. */
  setHasStats(has: boolean): void;
};

const required = requiredIn('Datasheet');

const cell = (tag: 'th' | 'td', text: string): HTMLTableCellElement => {
  const element = document.createElement(tag);

  element.textContent = text;
  if (tag === 'th') element.scope = 'col';

  return element;
};

export function renderDatasheet(options: DatasheetOptions): RenderedDatasheet {
  const { root, tenantId, renderer } = options;
  const empty = required<HTMLElement>(root, '[data-ds-empty]');
  const weapons = required<HTMLElement>(root, '[data-ds-weapons]');
  const weaponsTitle = required<HTMLElement>(root, '[data-ds-weapons-title]');
  const head = required<HTMLTableRowElement>(root, '[data-ds-head]');
  const body = required<HTMLElement>(root, '[data-ds-body]');
  const notes = required<HTMLElement>(root, '[data-ds-notes]');
  const noteList = required<HTMLElement>(root, '[data-ds-note-list]');
  const status = required<HTMLElement>(root, '[data-ds-status]');
  const aboutTitle = required<HTMLElement>(root, '[data-ds-about-title]');
  const description = required<HTMLElement>(root, '[data-ds-description]');

  // Each load retires one still in flight.
  let turn = 0;

  function drawWeapons(
    table: ReturnType<typeof weaponTable>,
    title: string,
    quantityColumn: boolean,
  ) {
    weaponsTitle.textContent = title;
    head.replaceChildren(
      cell('th', title === 'Weapons' ? 'Weapon' : 'Item'),
      ...table.columns.map((column) => cell('th', column.label)),
      ...(quantityColumn ? [cell('th', 'Qty')] : []),
    );
    body.replaceChildren(
      ...table.rows.map((row) => {
        const tr = document.createElement('tr');

        tr.append(
          cell('td', row.name),
          ...row.cells.map((text) => cell('td', text)),
          ...(quantityColumn ? [cell('td', String(row.quantity ?? 1))] : []),
        );

        return tr;
      }),
    );
    weapons.hidden = table.rows.length === 0;
  }

  /** An ability or a note: its title and who may read it, its text and who wrote it. */
  function noteElement(info: Information, beingId: string): HTMLElement {
    const box = document.createElement('div');
    const side = document.createElement('div');
    const title = document.createElement('strong');
    const text = document.createElement('div');

    box.className = 'ds-note';
    title.textContent = info.title || 'Note';
    side.append(title);

    // Who may read it is told only where it is not everyone, and then only that: the datasheet does
    // not list who was told (the notes of the sheet do).
    if (!info.is_public) {
      const badge = document.createElement('span');

      badge.className = 'badge-visibility';
      badge.textContent = 'Not for everyone';
      side.append(document.createElement('br'), badge);
    }

    text.className = 'ls-content';
    box.append(side, text);

    renderInformationPayloads(text, {
      information: info,
      loadFile: (payload) => blobUrl(payload.url, payload.updated_at),
      renderText: (host, content) =>
        showDescriptions(host, renderer, [{ text: content, home: beingId }]),
    });

    if (info.created_by_name) {
      const author = document.createElement('p');

      author.className = 'caption';
      author.textContent = info.created_by_name;
      text.after(author);
    }

    return box;
  }

  return {
    show(entity) {
      aboutTitle.textContent = `About ${entity.name.split(' ')[0]}`;
      description.replaceChildren();
      for (const info of entity.information.filter((info) => info.type === 'description')) {
        const mount = document.createElement('div');
        description.append(mount);
        renderInformationPayloads(mount, {
          information: info,
          loadFile: (payload) => blobUrl(payload.url, payload.updated_at),
          renderText: (host, content) =>
            showDescriptions(host, renderer, [{ text: content, home: entity.id }]),
        });
      }
    },
    setHasStats(has) {
      empty.hidden = has;
    },
    async load(entityId) {
      const mine = ++turn;

      say(status, '');

      try {
        const [sheet, notesAbout] = await Promise.all([
          getSheet(tenantId, entityId),
          listInformation(tenantId, entityId, ['note']),
        ]);

        if (mine !== turn) return;

        if (sheet.weapons_configured) {
          drawWeapons(weaponTable(sheet.weapons, options.vocabulary()), 'Weapons', false);
        } else {
          // Nothing says what a weapon is here: show what it carries, as plain names and counts.
          const owned = await getOwned(tenantId, entityId).catch(() => null);

          if (mine !== turn) return;

          const items = owned?.groups.flatMap((group) => group.item_instances) ?? [];

          drawWeapons(
            {
              columns: [],
              rows: items.map((item) => ({
                id: item.entity_id,
                name: item.title,
                quantity: item.quantity ?? 1,
                cells: [],
              })),
            },
            'Carried',
            true,
          );
        }

        const all = [...sheet.abilities, ...notesAbout];

        noteList.replaceChildren(...all.map((info) => noteElement(info, entityId)));
        notes.hidden = all.length === 0;
      } catch (error) {
        if (mine === turn) say(status, `Couldn't load the datasheet: ${errorMessage(error)}`, true);
      }
    },
  };
}
