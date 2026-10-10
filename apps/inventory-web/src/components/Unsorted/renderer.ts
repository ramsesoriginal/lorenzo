// The Unsorted view (ADR 0240): the library's placeholders by the name the player wrote, each
// group given to a catalog item, made into a new one, or kept.
import { errorMessage } from '../../lib/errorMessage';
import { suggest } from '../../lib/fuzzy';
import { findCatalogItems, listCatalogItems } from '../../lib/items';
import {
  assignAll,
  createFromGroup,
  descriptionFrom,
  groupUnsorted,
  holderNames,
  listUnsortedInstances,
  type PlayerNote,
  playerNotes,
  type UnsortedGroup,
} from '../../lib/sorting';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { CatalogItem, ItemInstance } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';

export type UnsortedOptions = {
  root: HTMLElement;
  tenantId: string;
  unsortedId: string;
};

const required = requiredIn('Unsorted');

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

export async function renderUnsorted({ root, tenantId, unsortedId }: UnsortedOptions) {
  const empty = required<HTMLElement>(root, '[data-empty]');
  const result = required<HTMLElement>(root, '[data-result]');
  const list = required<HTMLElement>(root, '[data-groups]');
  const groupTemplate = required<HTMLTemplateElement>(root, '[data-group-template]');
  const instanceTemplate = required<HTMLTemplateElement>(root, '[data-instance-template]');
  const holders = new Map<string, string>();
  let catalog: Promise<CatalogItem[]> | null = null;

  // The whole catalog is read once, when a first group is opened.
  const catalogItems = () =>
    (catalog ??= listCatalogItems(tenantId).then((items) =>
      items.filter((item) => item.entity_id !== unsortedId),
    ));

  function renderGroup(group: UnsortedGroup): HTMLLIElement {
    let instances: readonly ItemInstance[] = group.instances;
    let chosen: CatalogItem | null = null;
    let opened = false;

    const item = cloneTemplate<HTMLLIElement>(groupTemplate, 'li');
    const name = required<HTMLElement>(item, '[data-name]');
    const count = required<HTMLElement>(item, '[data-count]');
    const toggle = required<HTMLButtonElement>(item, '[data-toggle]');
    const body = required<HTMLElement>(item, '[data-body]');
    const rows = required<HTMLElement>(item, '[data-instances]');
    const suggestions = required<HTMLElement>(item, '[data-suggestions]');
    const chosenRow = required<HTMLElement>(item, '[data-chosen]');
    const chosenText = required<HTMLElement>(item, '[data-chosen-text]');
    const assign = required<HTMLButtonElement>(item, '[data-assign]');
    const createForm = required<HTMLFormElement>(item, '[data-create]');
    const createName = required<HTMLInputElement>(item, '[data-create-name]');
    const createPublic = required<HTMLInputElement>(item, '[data-create-public]');
    const keep = required<HTMLButtonElement>(item, '[data-keep]');
    const progress = required<HTMLElement>(item, '[data-progress]');
    const notes = new Map<string, PlayerNote[]>();

    name.textContent = group.name;
    createName.value = group.name;

    // Ticked instances are the ones a button acts on; all of them to start with.
    const ticked = () =>
      [...rows.querySelectorAll<HTMLInputElement>('[data-pick]')]
        .map((box, at) => (box.checked ? instances[at] : undefined))
        .filter((instance): instance is ItemInstance => instance !== undefined);

    function summarize() {
      count.textContent = plural(instances.length, 'item', 'items');
      const picked = ticked().length;

      assign.textContent = chosen ? `Assign ${picked} to ${chosen.title}` : 'Assign';
      assign.disabled = picked === 0;
    }

    function renderRows() {
      rows.replaceChildren(
        ...instances.map((instance) => {
          const row = cloneTemplate<HTMLLIElement>(instanceTemplate, 'li');
          const holder = instance.owner_entity_id
            ? (holders.get(instance.owner_entity_id) ?? 'Someone')
            : 'Nobody';

          required<HTMLElement>(row, '[data-holder]').textContent =
            instance.title === group.name ? holder : `${holder}, as “${instance.title}”`;
          required<HTMLInputElement>(row, '[data-pick]').addEventListener('change', summarize);

          const noteList = required<HTMLElement>(row, '[data-notes]');

          for (const note of notes.get(instance.entity_id) ?? []) {
            const line = document.createElement('li');

            line.className = 'field-note';
            line.textContent = `${note.title}: ${note.text}`;
            noteList.append(line);
          }

          return row;
        }),
      );
      summarize();
    }

    function choose(picked: CatalogItem) {
      chosen = picked;
      chosenRow.hidden = false;
      chosenText.textContent = `${group.name} is a ${picked.title}.`;
      summarize();
    }

    async function open() {
      opened = true;
      body.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      toggle.textContent = 'Close';

      // Names, notes and the catalog, read when a group is opened and not before.
      try {
        const [, all] = await Promise.all([
          holderNames(tenantId, instances, holders),
          catalogItems(),
          ...instances.map(async (instance) => {
            notes.set(instance.entity_id, await playerNotes(tenantId, instance.entity_id));
          }),
        ]);

        renderRows();

        for (const near of suggest(group.name, all, (c) => c.title, 3)) {
          const button = document.createElement('button');

          button.type = 'button';
          button.className = 'btn-secondary';
          button.textContent = near.title;
          button.addEventListener('click', () => choose(near));
          suggestions.append(button);
        }

        if (!suggestions.children.length) suggestions.textContent = 'Nothing close in the catalog.';
      } catch (error) {
        say(progress, errorMessage(error), true);
      }
    }

    function close() {
      opened = false;
      body.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.textContent = 'Sort';
    }

    toggle.addEventListener('click', () => (opened ? close() : void open()));
    keep.addEventListener('click', () => item.remove());

    renderCombobox(item, {
      async search(query) {
        const found = await findCatalogItems(tenantId, query, 8);

        return found
          .filter((c) => c.entity_id !== unsortedId)
          .map((c) => ({ label: c.title, value: c }));
      },
      onPick: choose,
    });

    // What a button did, said once, with whatever it could not do kept in the group to try again.
    function finish(sorted: Awaited<ReturnType<typeof assignAll>>, title: string, extra = '') {
      const done = new Set(sorted.done.map((d) => d.entity_id));

      instances = instances.filter((instance) => !done.has(instance.entity_id));

      const failed = sorted.failed.map((f) => `${f.instance.title} (${f.problem})`);
      const text = `${plural(sorted.done.length, 'item', 'items')} sorted as ${title}.${extra}`;

      if (!instances.length) {
        item.remove();
        say(result, text, false);
        refreshEmpty();

        return;
      }

      renderRows();
      say(
        progress,
        failed.length ? `${text} Not sorted: ${failed.join('; ')}.` : text,
        failed.length > 0,
      );
    }

    assign.addEventListener('click', async () => {
      if (!chosen) return;

      const target = chosen;
      const picked = ticked();

      assign.disabled = true;
      say(result, '');
      const sorted = await assignAll(tenantId, picked, target.entity_id, (done, total) =>
        say(progress, `Sorting ${done} of ${total}…`),
      );

      finish(sorted, target.title);
    });

    createForm.addEventListener('submit', async (event) => {
      event.preventDefault();

      const title = createName.value.trim();

      if (!title) return say(progress, 'Give the new item a name.', true);

      const picked = ticked();

      say(progress, 'Creating…');

      try {
        const description = descriptionFrom(
          picked.flatMap((instance) => notes.get(instance.entity_id) ?? []),
        );
        const made = await createFromGroup(tenantId, title, createPublic.checked, description);
        const sorted = await assignAll(tenantId, picked, made.entityId, (done, total) =>
          say(progress, `Sorting ${done} of ${total}…`),
        );

        finish(
          sorted,
          title,
          made.descriptionProblem
            ? ` Its description was not saved (${made.descriptionProblem}).`
            : '',
        );
      } catch (error) {
        say(progress, errorMessage(error), true);
      }
    });

    count.textContent = plural(instances.length, 'item', 'items');

    return item;
  }

  function refreshEmpty() {
    empty.hidden = list.children.length > 0;
    empty.textContent = 'Nothing is unsorted.';
  }

  const instances = await listUnsortedInstances(tenantId, unsortedId);

  list.replaceChildren(...groupUnsorted(instances).map(renderGroup));
  refreshEmpty();
}
