import type { Renderer } from '../../lib/descriptions';
import { errorMessage } from '../../lib/errorMessage';
import { descriptionDraft, type Information, type InformationDraft } from '../../lib/information';
import { listCatalogItems } from '../../lib/items';
import { slugProblem, suggestSlug } from '../../lib/slugs';
import { say } from '../../lib/statusLine';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { CatalogItem } from '../../lib/types';
import { renderCombobox } from '../Combobox/renderer';
import { renderDescriptionEditor } from '../DescriptionEditor/renderer';

export type ItemFormValues = {
  name: string;
  parentIds: string[];
  description: InformationDraft;
  slug: string;
  inPublicCatalog: boolean;
};

export type ItemFormInitial = {
  name: string;
  parents: Map<string, string>;
  // Null when creating.
  description: Information | null;
  slug: string;
  inPublicCatalog: boolean;
  // Edit forms only.
  usedBy?: CatalogItem[];
};

export type ItemFormOptions = {
  tenantId: string;
  renderer: Renderer;
  initial: ItemFormInitial;
  submitLabel: string;
  // The create form keeps the display name and slug following the name until they're edited.
  followName?: boolean;
  followSlug?: boolean;
  hideCurrentName?: boolean;
  onSubmit(values: ItemFormValues): Promise<void>;
};

export type RenderedItemForm = {
  element: HTMLFormElement;
  destroy(): void;
};

let nextFormId = 0;

const required = requiredIn('Item form');

function outerTemplate(): HTMLTemplateElement {
  const template = document.querySelector<HTMLTemplateElement>('#item-form-template');

  if (!template) {
    throw new Error('Item form template not found. Did you render <ItemForm /> on this page?');
  }

  return template;
}

function checkSlug(value: string): void {
  const slug = value.trim();

  if (!slug) return;

  const problem = slugProblem(slug);

  if (problem) {
    throw new Error(problem);
  }
}

export function renderItemForm(options: ItemFormOptions): RenderedItemForm {
  const form = cloneTemplate<HTMLFormElement>(outerTemplate(), 'form');
  const controller = new AbortController();
  const { signal } = controller;

  // The create and an edit form can be on the page together.
  const formNumber = ++nextFormId;
  const id = (name: string) => `item-form-${formNumber}-${name}`;

  const currentName = required<HTMLElement>(form, '[data-current-name]');
  const nameLabel = required<HTMLLabelElement>(form, '[data-name-label]');
  const nameInput = required<HTMLInputElement>(form, '[data-name]');
  const displayNameLabel = required<HTMLLabelElement>(form, '[data-display-name-label]');
  const displayNameInput = required<HTMLInputElement>(form, '[data-display-name]');
  const parentsLabel = required<HTMLLabelElement>(form, '[data-parents-label]');
  const parentChips = required<HTMLUListElement>(form, '[data-parent-chips]');
  const publicCatalogInput = required<HTMLInputElement>(form, '[data-public-catalog]');
  const descriptionVisibility = required<HTMLElement>(form, '[data-description-visibility]');
  const descriptionPublicInput = required<HTMLInputElement>(form, '[data-description-public]');
  const slugLabel = required<HTMLLabelElement>(form, '[data-slug-label]');
  const slugInput = required<HTMLInputElement>(form, '[data-slug]');
  const usedByField = required<HTMLElement>(form, '[data-used-by]');
  const usedByEmpty = required<HTMLElement>(form, '[data-used-by-empty]');
  const usedByList = required<HTMLUListElement>(form, '[data-used-by-list]');
  const errorElement = required<HTMLElement>(form, '[data-error]');
  const submitButton = required<HTMLButtonElement>(form, '[data-submit]');

  nameInput.id = id('name');
  nameLabel.htmlFor = nameInput.id;
  displayNameInput.id = id('display-name');
  displayNameLabel.htmlFor = displayNameInput.id;
  slugInput.id = id('slug');
  slugLabel.htmlFor = slugInput.id;

  const initialDescription = descriptionDraft(options.initial.description, options.initial.name);

  nameInput.value = options.initial.name;
  displayNameInput.value = initialDescription.title;
  descriptionPublicInput.checked = initialDescription.isPublic;
  slugInput.value = options.initial.slug;
  publicCatalogInput.checked = options.initial.inPublicCatalog;
  currentName.textContent = options.initial.name || 'New item';
  currentName.hidden = options.hideCurrentName ?? false;
  submitButton.textContent = options.submitLabel;

  // Only a new description chooses its visibility; an existing one keeps it.
  descriptionVisibility.hidden = options.initial.description !== null;

  if (options.followName) {
    let displayNameEdited = false;

    displayNameInput.addEventListener(
      'input',
      () => {
        displayNameEdited = true;
      },
      { signal },
    );

    nameInput.addEventListener(
      'input',
      () => {
        currentName.textContent = nameInput.value.trim() || 'New item';

        if (!displayNameEdited) {
          displayNameInput.value = nameInput.value.trim();
        }
      },
      { signal },
    );
  } else {
    nameInput.addEventListener(
      'input',
      () => {
        currentName.textContent = nameInput.value.trim() || options.initial.name;
      },
      { signal },
    );
  }

  const selectedParents = new Map(options.initial.parents);

  function renderParentChips(): void {
    parentChips.replaceChildren(
      ...[...selectedParents].map(([entityId, title]) => {
        const chip = cloneTemplate<HTMLLIElement>(
          required<HTMLTemplateElement>(form, '[data-parent-chip-template]'),
        );
        const remove = required<HTMLButtonElement>(chip, '[data-remove]');

        required<HTMLElement>(chip, '[data-title]').textContent = title;
        remove.setAttribute('aria-label', `Remove ${title}`);

        remove.addEventListener(
          'click',
          () => {
            selectedParents.delete(entityId);
            renderParentChips();
          },
          { signal },
        );

        return chip;
      }),
    );
  }

  renderParentChips();

  const parents = renderCombobox<CatalogItem>(form, {
    delayMs: 250,

    async search(query) {
      const items = await listCatalogItems(options.tenantId, query);

      return items
        .filter((item) => !selectedParents.has(item.entity_id))
        .map((item) => ({ label: item.title, value: item }));
    },

    onPick(item) {
      selectedParents.set(item.entity_id, item.title);
      renderParentChips();
      parents.input.value = '';
      parents.input.focus();
    },

    signal,
  });

  parents.input.id = id('parents');
  parentsLabel.htmlFor = parents.input.id;

  if (options.followSlug) {
    let slugEdited = false;
    let suggestionRequest = 0;

    slugInput.addEventListener(
      'input',
      () => {
        slugEdited = true;
      },
      { signal },
    );

    let slugDebounce: ReturnType<typeof setTimeout> | undefined;

    const updateSlugSuggestion = () => {
      clearTimeout(slugDebounce);

      slugDebounce = setTimeout(async () => {
        const request = ++suggestionRequest;
        const title = displayNameInput.value.trim() || nameInput.value.trim();
        const suggestion = await suggestSlug(options.tenantId, title, 'item').catch(() => '');

        if (!slugEdited && request === suggestionRequest) {
          slugInput.value = suggestion;
        }
      }, 250);
    };

    nameInput.addEventListener('input', updateSlugSuggestion, { signal });
    displayNameInput.addEventListener('input', updateSlugSuggestion, { signal });
  }

  const editor = renderDescriptionEditor(form, {
    renderer: options.renderer,
    label: 'Description',
    content: initialDescription.content,
  });

  if (options.initial.usedBy !== undefined) {
    usedByField.hidden = false;

    if (options.initial.usedBy.length > 0) {
      usedByEmpty.hidden = true;
      usedByList.hidden = false;
      usedByList.replaceChildren(
        ...options.initial.usedBy.map((item) => {
          const chip = cloneTemplate<HTMLLIElement>(
            required<HTMLTemplateElement>(form, '[data-used-by-chip-template]'),
          );

          required<HTMLElement>(chip, '[data-title]').textContent = item.title;

          return chip;
        }),
      );
    }
  }

  form.addEventListener(
    'submit',
    async (event) => {
      event.preventDefault();

      say(errorElement, '');
      submitButton.disabled = true;

      try {
        const name = nameInput.value.trim();

        if (!name) {
          throw new Error('Name is required.');
        }

        checkSlug(slugInput.value);

        const description: InformationDraft = {
          title: displayNameInput.value.trim(),
          type: 'description',
          isPublic:
            options.initial.description !== null
              ? initialDescription.isPublic
              : descriptionPublicInput.checked,
          content: editor.value(),
        };

        await options.onSubmit({
          name,
          parentIds: [...selectedParents.keys()],
          description,
          slug: slugInput.value,
          inPublicCatalog: publicCatalogInput.checked,
        });
      } catch (error) {
        say(errorElement, errorMessage(error), true);
      } finally {
        submitButton.disabled = false;
      }
    },
    { signal },
  );

  return {
    element: form,

    destroy() {
      controller.abort();
      editor.destroy();
    },
  };
}
