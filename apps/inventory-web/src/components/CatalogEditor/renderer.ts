// A catalog item edited in place, for a game master (IN5): the description saves as you type, the
// stats (its own and what it inherits) and the tags save as you change them, and what could break a link (the link
// name, what it is made from, whether it is in the public catalog) is kept until the shell's save bar
// says Save changes.

import { errorMessage } from '../../lib/errorMessage';
import {
  descriptionDraft,
  getDescription,
  type Information,
  saveDescription,
} from '../../lib/information';
import {
  findCatalogItems,
  getEntityDetail,
  setItemPrototypes,
  updateCatalogItem,
} from '../../lib/items';
import { currentShell } from '../../lib/shell';
import { saveSlug } from '../../lib/slugs';
import { statLabel } from '../../lib/statLabel';
import {
  clearStat,
  parseStat,
  type Seen,
  type StatValue,
  setStat,
  statDefinitions,
  statRows,
} from '../../lib/statValues';
import { setTag, tagDefinitions } from '../../lib/tagEditor';
import type { CatalogItem, EntityDetail } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type CatalogEditorOptions = {
  host: HTMLElement;
  tenantId: string;
  item: Pick<CatalogItem, 'entity_id' | 'title' | 'in_public_catalog'>;
  // The structure was saved: what the list's rows say (public, made from) is drawn again.
  onChanged(): void;
};

export type RenderedCatalogEditor = {
  // Whether there is something not saved yet, which leaving would lose.
  dirty(): boolean;
  destroy(): void;
};

const AUTOSAVE_MS = 800;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;

  return node;
}

export function renderCatalogEditor(options: CatalogEditorOptions): RenderedCatalogEditor {
  const { host, tenantId } = options;
  const entityId = options.item.entity_id;
  const controller = new AbortController();
  const { signal } = controller;
  let destroyed = false;
  let unsaved = () => 0;

  const note = el('p', 'caption', 'Loading…');

  host.replaceChildren(note);

  const toast = (title: string, text?: string) =>
    currentShell()?.toast({ kind: 'error', title, ...(text ? { text } : {}) });

  async function load() {
    const [definitions, entity, info, tags] = await Promise.all([
      statDefinitions(tenantId),
      getEntityDetail(tenantId, entityId),
      getDescription(tenantId, entityId),
      tagDefinitions(tenantId).catch(() => []),
    ]);

    if (destroyed) return;

    draw(definitions, entity, info, tags);
  }

  function draw(
    definitions: Awaited<ReturnType<typeof statDefinitions>>,
    firstEntity: EntityDetail,
    firstInfo: Information | null,
    tagDefs: Awaited<ReturnType<typeof tagDefinitions>>,
  ) {
    let entity = firstEntity;
    let info = firstInfo;

    // --- The description, saved as it is typed.
    const descriptionLabel = el('label', 'field');
    const descriptionNote = el('span', 'field-label', 'Description saves as you type');
    const description = el('textarea', 'text-input');
    const saved = el('span', 'caption');

    description.rows = 4;
    description.value = descriptionDraft(info, entity.name).content;
    descriptionLabel.append(descriptionNote, description, saved);

    let timer: ReturnType<typeof setTimeout> | undefined;
    let writing = Promise.resolve();

    const saveText = () => {
      saved.textContent = 'Saving…';
      writing = writing.then(async () => {
        try {
          const draft = { ...descriptionDraft(info, entity.name), content: description.value };

          await saveDescription(tenantId, entityId, info, draft, entity.name);
          info = await getDescription(tenantId, entityId);
          saved.textContent = 'Saved';
        } catch (error) {
          saved.textContent = '';
          toast('Couldn’t save the description', errorMessage(error));
        }
      });
    };

    description.addEventListener(
      'input',
      () => {
        clearTimeout(timer);
        saved.textContent = '';
        timer = setTimeout(saveText, AUTOSAVE_MS);
      },
      { signal },
    );
    signal.addEventListener('abort', () => {
      clearTimeout(timer);
    });

    // --- Stats: every one the item has, its own or inherited, written where it is. A value typed
    // over an inherited one is the item's own, and the ancestor keeps its.
    const statsBox = el('div', 'stack-tight');
    const statList = el('div', 'item-editor-fields');
    const addStat = el('select', 'text-input item-editor-add');
    // A stat chosen to add: a field with no value yet, which saves when it has one.
    const drafts = new Set<string>();

    addStat.setAttribute('aria-label', 'Add a stat');
    statsBox.append(el('p', 'field-label', 'Stats'), statList, addStat);

    const sourceText = (stat: EntityDetail['stats'][number] | undefined, own: boolean) => {
      if (stat?.computed) return 'Worked out from its other stats';
      if (own) return 'Set on this item';
      if (stat?.from_entity) return `Inherited from ${stat.from_entity.name}`;
      if (stat?.from_hidden) return 'Inherited from a hidden entry';

      return stat ? 'Inherited' : 'Not set yet';
    };

    function drawStats() {
      const rows = statRows(definitions, entity);
      const byName = new Map(entity.stats.map((stat) => [stat.name, stat]));
      const shown = rows.filter(
        (row) => row.value !== null || row.own || drafts.has(row.definition.name),
      );
      const rest = rows.filter((row) => !shown.includes(row));

      statList.replaceChildren(
        ...shown.map((row) => {
          const stat = byName.get(row.definition.name);
          const box = el('div', 'item-editor-stat');
          const label = el('label', 'item-editor-field');
          const unit = row.definition.unit ? `, ${row.definition.unit}` : '';
          const name = `${statLabel(row.definition.name)}${unit}`;
          const caption = el('span', 'caption', sourceText(stat, row.own));
          const seen: Seen = { value: row.value, own: row.own };
          let field: HTMLInputElement | HTMLSelectElement;

          if (row.definition.value_type === 'enum') {
            const choice = el('select', 'text-input');

            choice.append(new Option('Choose a value', ''));

            for (const value of row.definition.enum_values) choice.append(new Option(value, value));

            choice.value = row.value === null ? '' : String(row.value);
            field = choice;
          } else {
            const input = el('input', 'text-input');

            input.inputMode = row.definition.value_type === 'text' ? 'text' : 'decimal';
            input.value = row.value === null ? '' : String(row.value);
            field = input;
          }

          field.setAttribute('aria-label', name);
          field.disabled = stat?.computed === true;
          label.append(el('span', undefined, name), field);
          box.append(label, caption);

          field.addEventListener(
            'change',
            async () => {
              try {
                if (field.value.trim() === '') {
                  if (!row.own) {
                    drawStats();

                    return;
                  }

                  entity = await clearStat(tenantId, entityId, row.definition, seen);
                } else {
                  const parsed = parseStat(row.definition, field.value);

                  if ('problem' in parsed) throw new Error(parsed.problem);

                  entity = await setStat(
                    tenantId,
                    entityId,
                    row.definition,
                    parsed.value as StatValue,
                    seen,
                  );
                }

                drafts.delete(row.definition.name);
                drawStats();
              } catch (error) {
                toast(`Couldn’t save ${statLabel(row.definition.name)}`, errorMessage(error));
                drawStats();
              }
            },
            { signal },
          );

          if (row.own) {
            const clear = el('button', 'btn btn-secondary item-editor-clear', 'Clear');

            clear.type = 'button';
            clear.setAttribute('aria-label', `Clear ${statLabel(row.definition.name)}`);
            clear.addEventListener(
              'click',
              async () => {
                try {
                  entity = await clearStat(tenantId, entityId, row.definition, seen);
                  drawStats();
                } catch (error) {
                  toast(`Couldn’t clear ${statLabel(row.definition.name)}`, errorMessage(error));
                }
              },
              { signal },
            );
            box.append(clear);
          }

          return box;
        }),
      );

      addStat.replaceChildren(
        new Option('Add a stat…', ''),
        ...rest.map((row) => new Option(statLabel(row.definition.name), row.definition.name)),
      );
      addStat.hidden = rest.length === 0;
    }

    addStat.addEventListener(
      'change',
      () => {
        if (addStat.value) drafts.add(addStat.value);

        const name = addStat.value;

        drawStats();
        statList
          .querySelector<HTMLElement>(`[aria-label^="${CSS.escape(statLabel(name))}"]`)
          ?.focus();
      },
      { signal },
    );
    drawStats();

    // --- Tags: the ones the item has, its own or inherited; the rest are added.
    const tagsBox = el('div', 'stack-tight');
    const tagList = el('ul', 'row item-editor-tags');
    const addTag = el('select', 'text-input item-editor-add');

    addTag.setAttribute('aria-label', 'Add a tag');
    tagsBox.append(el('p', 'field-label', 'Tags'), tagList, addTag);

    async function changeTag(definition: (typeof tagDefs)[number], to: 'on' | 'off' | 'inherited') {
      try {
        entity = await setTag(tenantId, entityId, definition.id, to);
        drawTags();
      } catch (error) {
        toast(`Couldn’t change ${statLabel(definition.name)}`, errorMessage(error));
      }
    }

    function drawTags() {
      const byName = new Map(entity.stats.map((stat) => [stat.name, stat]));
      const has = (definition: (typeof tagDefs)[number]) =>
        byName.get(definition.name)?.value === true;
      const shown = tagDefs.filter(has);

      tagList.replaceChildren(
        ...shown.map((definition) => {
          const stat = byName.get(definition.name);
          const own = stat?.own === true;
          const chip = el('li', own ? 'chip' : 'chip chip--inherited');
          const from = stat?.from_entity?.name;
          const remove = el('button', 'chip-remove', '×');

          chip.append(statLabel(definition.name));

          if (!own) chip.append(el('span', 'caption', from ? ` from ${from}` : ' inherited'));

          remove.type = 'button';
          remove.setAttribute('aria-label', `Remove ${statLabel(definition.name)}`);
          // Its own goes back to what it inherits; what it inherits is turned off here.
          remove.addEventListener(
            'click',
            () => void changeTag(definition, own ? 'inherited' : 'off'),
            { signal },
          );
          chip.append(remove);

          return chip;
        }),
      );

      const rest = tagDefs.filter((definition) => !has(definition));

      addTag.replaceChildren(
        new Option('Add a tag…', ''),
        ...rest.map((definition) => new Option(statLabel(definition.name), definition.id)),
      );
      addTag.hidden = rest.length === 0;
      tagsBox.hidden = tagDefs.length === 0;
    }

    addTag.addEventListener(
      'change',
      () => {
        const definition = tagDefs.find((d) => d.id === addTag.value);

        if (definition) void changeTag(definition, 'on');
      },
      { signal },
    );
    drawTags();

    // --- The structure, kept with the save bar.
    const structure = el('fieldset', 'item-editor-structure');
    const slugLabel = el('label', 'item-editor-field');
    const slugInput = el('input', 'text-input');
    let baseSlug = entity.slug ?? '';
    let basePublic = options.item.in_public_catalog;
    let baseParents = entity.prototypes.map((p) => ({ id: p.id, name: p.name }));
    let parents = [...baseParents];
    let isPublic = basePublic;

    slugInput.value = baseSlug;
    slugInput.spellcheck = false;
    slugLabel.append(el('span', undefined, 'Link name'), slugInput);

    const publicLabel = el('label', 'row-tight');
    const publicInput = el('input');

    publicInput.type = 'checkbox';
    publicInput.checked = isPublic;
    publicLabel.append(publicInput, document.createTextNode('In the public catalog'));

    const madeBox = el('div', 'stack-tight');
    const madeList = el('ul', 'row');
    const finder = el('div', 'field');

    finder.innerHTML = `<div class="combobox" data-combobox>
      <input type="text" class="text-input" role="combobox" autocomplete="off" aria-expanded="false" aria-label="Add an item it is made from" placeholder="Add an item it is made from…" data-input />
      <ul class="combobox-suggestions" role="listbox" hidden data-suggestions></ul>
      <template data-suggestion-template>
        <li class="combobox-suggestion" role="option"><button type="button" data-select></button></li>
      </template>
    </div>`;
    madeBox.append(el('span', 'field-label', 'Made from'), madeList, finder);
    structure.append(
      el('legend', 'caption', 'Structure kept with Save changes'),
      slugLabel,
      madeBox,
      publicLabel,
    );

    const count = () =>
      (slugInput.value.trim() !== baseSlug ? 1 : 0) +
      (isPublic !== basePublic ? 1 : 0) +
      (parents.map((p) => p.id).join() !== baseParents.map((p) => p.id).join() ? 1 : 0);
    unsaved = count;
    const bar = currentShell()?.saveBar({
      async save() {
        try {
          await Promise.all([
            updateCatalogItem(tenantId, entityId, entity.name, isPublic),
            setItemPrototypes(
              tenantId,
              entityId,
              parents.map((p) => p.id),
            ),
          ]);
          await saveSlug(tenantId, entityId, baseSlug, slugInput.value);
          // What was saved is what the bar compares against now.
          baseSlug = slugInput.value.trim();
          basePublic = isPublic;
          baseParents = [...parents];
          options.onChanged();
          refresh();
        } catch (error) {
          // The draft stays where it is, so a link name that is taken can be changed.
          toast('Couldn’t save', errorMessage(error));
        }
      },
      discard() {
        slugInput.value = baseSlug;
        parents = [...baseParents];
        isPublic = basePublic;
        publicInput.checked = isPublic;
        drawParents();
        refresh();
      },
    });
    const refresh = () => bar?.set(count());

    function drawParents() {
      madeList.replaceChildren(
        ...parents.map((parent) => {
          const chip = el('li', 'chip');
          const remove = el('button', 'chip-remove', '×');

          remove.type = 'button';
          remove.setAttribute('aria-label', `Remove ${parent.name}`);
          remove.addEventListener('click', () => {
            parents = parents.filter((p) => p.id !== parent.id);
            drawParents();
            refresh();
          });
          chip.append(parent.name, remove);

          return chip;
        }),
      );
    }

    drawParents();
    slugInput.addEventListener('input', refresh, { signal });
    publicInput.addEventListener(
      'change',
      () => {
        isPublic = publicInput.checked;
        refresh();
      },
      { signal },
    );
    renderCombobox<CatalogItem>(finder, {
      search: async (query) =>
        (await findCatalogItems(tenantId, query, 10))
          .filter(
            (found) =>
              found.entity_id !== entityId && !parents.some((p) => p.id === found.entity_id),
          )
          .map((found) => ({ label: found.title, value: found })),
      browseOnFocus: true,
      onPick(found) {
        parents = [...parents, { id: found.entity_id, name: found.title }];
        const input = finder.querySelector<HTMLInputElement>('[data-input]');

        if (input) input.value = '';

        drawParents();
        refresh();
      },
      signal,
    });
    signal.addEventListener('abort', () => bar?.set(0));

    host.replaceChildren(descriptionLabel, statsBox, tagsBox, structure);
  }

  load().catch((error) => {
    note.textContent = errorMessage(error);
    note.classList.add('error-text');
  });

  return {
    dirty: () => unsaved() > 0,

    destroy() {
      destroyed = true;
      controller.abort();
      host.replaceChildren();
    },
  };
}
