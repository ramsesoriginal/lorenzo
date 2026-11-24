// A catalog item edited in place, for a game master (IN5): the description saves as you type, the
// weight and the value and the tags save as you change them, and what could break a link (the link
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
import {
  clearStat,
  parseStat,
  type Seen,
  type StatDefinition,
  type StatValue,
  setStat,
  statDefinitions,
  statRows,
} from '../../lib/statValues';
import { setTag, tagDefinitions, tagState } from '../../lib/tagEditor';
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

    // --- Weight and value, saved when they change.
    const rows = statRows(definitions, entity);
    const find = (match: (definition: StatDefinition) => boolean) =>
      rows.find((row) => match(row.definition));
    const numberRows = [
      find((d) => d.role === 'weight' || d.name === 'weight'),
      find((d) => d.name === 'price' || d.name === 'value'),
    ].filter((row): row is NonNullable<typeof row> => row !== undefined);
    const fields = el('div', 'item-editor-fields');

    for (const row of numberRows) {
      const label = el('label', 'item-editor-field');
      const unit = row.definition.unit ? `, ${row.definition.unit}` : '';
      const input = el('input', 'text-input');
      let seen: Seen = { value: row.value, own: row.own };

      label.append(
        el(
          'span',
          undefined,
          `${row.definition.name.replace(/^./, (c) => c.toUpperCase())}${unit}`,
        ),
        input,
      );
      input.inputMode = 'decimal';
      input.value = row.value === null ? '' : String(row.value);
      input.addEventListener(
        'change',
        async () => {
          try {
            if (input.value.trim() === '') {
              entity = await clearStat(tenantId, entityId, row.definition, seen);
            } else {
              const parsed = parseStat(row.definition, input.value);

              if ('problem' in parsed) throw new Error(parsed.problem);

              entity = await setStat(
                tenantId,
                entityId,
                row.definition,
                parsed.value as StatValue,
                seen,
              );
            }

            const fresh = statRows(definitions, entity).find(
              (r) => r.definition.name === row.definition.name,
            );

            seen = { value: fresh?.value ?? null, own: fresh?.own === true };
          } catch (error) {
            toast(`Couldn’t save ${row.definition.name}`, errorMessage(error));
          }
        },
        { signal },
      );
      fields.append(label);
    }

    // --- Tags, on or not, as you choose.
    const tagsBox = el('div', 'stack-tight');
    const tagList = el('ul', 'row item-editor-tags');

    tagsBox.append(el('p', 'field-label', 'Tags'), tagList);

    for (const definition of tagDefs) {
      const chip = el('li');
      const button = el('button', 'chip chip-choice', definition.name.replace(/_/g, ' '));
      const stateOf = () =>
        tagState(entity.stats.find((stat) => stat.name === definition.name)).state;

      button.type = 'button';
      button.setAttribute('aria-pressed', String(stateOf() === 'on'));
      button.addEventListener(
        'click',
        async () => {
          try {
            entity = await setTag(
              tenantId,
              entityId,
              definition.id,
              stateOf() === 'on' ? 'inherited' : 'on',
            );
            button.setAttribute('aria-pressed', String(stateOf() === 'on'));
          } catch (error) {
            toast(`Couldn’t change ${definition.name}`, errorMessage(error));
          }
        },
        { signal },
      );
      chip.append(button);
      tagList.append(chip);
    }

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

    host.replaceChildren(descriptionLabel, fields, tagsBox, structure);
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
