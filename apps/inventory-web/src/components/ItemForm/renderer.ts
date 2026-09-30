import { createEditor } from '@lorenzo/lorenzoscript-editor';

import type { Renderer } from '../../lib/descriptions';
import {
  descriptionDraft,
  type Information,
  type InformationDraft,
} from '../../lib/information';
import { listCatalogItems } from '../../lib/items';
import { slugProblem, suggestSlug } from '../../lib/slugs';
import type { CatalogItem } from '../../lib/types';

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

  /**
   * Existing description when editing; null when creating a new item.
   */
  description: Information | null;

  slug: string;
  inPublicCatalog: boolean;

  /**
   * Present on edit forms. Omit on create forms.
   */
  usedBy?: CatalogItem[];
};

export type ItemFormOptions = {
  tenantId: string;
  renderer: Renderer;

  initial: ItemFormInitial;
  submitLabel: string;

  /**
   * Keep the display name equal to Name until the user edits it manually.
   * Intended for the create form.
   */
  followName?: boolean;

  /**
   * Keep suggesting a slug from the effective display name until the
   * user edits the slug manually.
   * Intended for the create form.
   */
  followSlug?: boolean;

  hideCurrentName?: boolean;

  onSubmit(values: ItemFormValues): Promise<void>;
};

export type RenderedItemForm = {
  element: HTMLFormElement;
  destroy(): void;
};

let nextFormId = 0;

function required<T extends Element>(
  root: ParentNode,
  selector: string,
): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Item form is missing ${selector}.`);
  }

  return element;
}

function outerTemplate(): HTMLTemplateElement {
  const template =
    document.querySelector<HTMLTemplateElement>('#item-form-template');

  if (!template) {
    throw new Error(
      'Item form template not found. Did you render <ItemForm /> on this page?',
    );
  }

  return template;
}

function cloneForm(): HTMLFormElement {
  const first = outerTemplate().content.firstElementChild;

  if (!(first instanceof HTMLFormElement)) {
    throw new Error('Item form template does not contain a form.');
  }

  return first.cloneNode(true) as HTMLFormElement;
}

function cloneNested<T extends Element>(
  form: HTMLFormElement,
  selector: string,
): T {
  const template = required<HTMLTemplateElement>(form, selector);
  const first = template.content.firstElementChild;

  if (!first) {
    throw new Error(`Item form template ${selector} is empty.`);
  }

  return first.cloneNode(true) as T;
}

function errorReason(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function checkSlug(value: string): void {
  const slug = value.trim();

  if (!slug) return;

  const problem = slugProblem(slug);

  if (problem) {
    throw new Error(problem);
  }
}

export function renderItemForm(
  options: ItemFormOptions,
): RenderedItemForm {
  const form = cloneForm();

  /*
   * AbortController gives this particular form ownership of its event
   * listeners. destroy() can therefore clean up even listeners attached
   * to document.
   */
  const controller = new AbortController();
  const { signal } = controller;

  const formNumber = ++nextFormId;
  const id = (name: string) => `item-form-${formNumber}-${name}`;

  /*
   * Static controls
   */

  const currentName =
    required<HTMLElement>(form, '[data-current-name]');

  const nameLabel =
    required<HTMLLabelElement>(form, '[data-name-label]');
  const nameInput =
    required<HTMLInputElement>(form, '[data-name]');

  const displayNameLabel =
    required<HTMLLabelElement>(form, '[data-display-name-label]');
  const displayNameInput =
    required<HTMLInputElement>(form, '[data-display-name]');

  const parentsLabel =
    required<HTMLLabelElement>(form, '[data-parents-label]');
  const parentsCombobox =
    required<HTMLElement>(form, '[data-parents-combobox]');
  const parentsSearch =
    required<HTMLInputElement>(form, '[data-parents-search]');
  const parentSuggestions =
    required<HTMLUListElement>(form, '[data-parent-suggestions]');
  const parentChips =
    required<HTMLUListElement>(form, '[data-parent-chips]');

  const publicCatalogInput =
    required<HTMLInputElement>(form, '[data-public-catalog]');

  const descriptionVisibility =
    required<HTMLElement>(form, '[data-description-visibility]');
  const descriptionPublicInput =
    required<HTMLInputElement>(form, '[data-description-public]');

  const slugLabel =
    required<HTMLLabelElement>(form, '[data-slug-label]');
  const slugInput =
    required<HTMLInputElement>(form, '[data-slug]');

  const descriptionInput =
    required<HTMLTextAreaElement>(form, '[data-description]');
  const descriptionNotes =
    required<HTMLUListElement>(form, '[data-description-notes]');

  const usedByField =
    required<HTMLElement>(form, '[data-used-by]');
  const usedByEmpty =
    required<HTMLElement>(form, '[data-used-by-empty]');
  const usedByList =
    required<HTMLUListElement>(form, '[data-used-by-list]');

  const errorElement =
    required<HTMLElement>(form, '[data-error]');
  const submitButton =
    required<HTMLButtonElement>(form, '[data-submit]');

  /*
   * Unique label/control relationships.
   *
   * The page can contain the create form plus an edit form, so these
   * cannot be hard-coded in ItemForm.astro.
   */

  nameInput.id = id('name');
  nameLabel.htmlFor = nameInput.id;

  displayNameInput.id = id('display-name');
  displayNameLabel.htmlFor = displayNameInput.id;

  parentsSearch.id = id('parents');
  parentsLabel.htmlFor = parentsSearch.id;

  parentSuggestions.id = id('parent-suggestions');
  parentsSearch.setAttribute(
    'aria-controls',
    parentSuggestions.id,
  );

  slugInput.id = id('slug');
  slugLabel.htmlFor = slugInput.id;

  /*
   * Initial values
   */

  const initialDescription = descriptionDraft(
    options.initial.description,
    options.initial.name,
  );

  nameInput.value = options.initial.name;
  displayNameInput.value = initialDescription.title;
  descriptionInput.value = initialDescription.content;
  descriptionPublicInput.checked = initialDescription.isPublic;

  slugInput.value = options.initial.slug;
  publicCatalogInput.checked =
    options.initial.inPublicCatalog;

  currentName.textContent =
    options.initial.name || 'New item';

  currentName.hidden = options.hideCurrentName ?? false;

  submitButton.textContent = options.submitLabel;

  /*
   * Existing descriptions keep their current visibility without
   * exposing that choice here, matching the old descriptionFields()
   * behavior:
   *
   *     showVisibility: info === null
   *
   * A newly created description may choose its visibility.
   */
  descriptionVisibility.hidden =
    options.initial.description !== null;

  /*
   * Name / display-name relationship
   */

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
        currentName.textContent =
          nameInput.value.trim() || 'New item';

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
        currentName.textContent =
          nameInput.value.trim() || options.initial.name;
      },
      { signal },
    );
  }

  /*
   * Parents
   */

  const selectedParents = new Map(options.initial.parents);

  function closeParentSuggestions(): void {
    parentSuggestions.hidden = true;
    parentSuggestions.replaceChildren();
    parentsSearch.setAttribute('aria-expanded', 'false');
  }

  function renderParentChips(): void {
    parentChips.replaceChildren(
      ...[...selectedParents].map(([entityId, title]) => {
        const chip = cloneNested<HTMLLIElement>(
          form,
          '[data-parent-chip-template]',
        );

        const titleElement =
          required<HTMLElement>(chip, '[data-title]');
        const remove =
          required<HTMLButtonElement>(chip, '[data-remove]');

        titleElement.textContent = title;

        remove.setAttribute(
          'aria-label',
          `Remove ${title}`,
        );

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

  let parentSearchDebounce:
    | ReturnType<typeof setTimeout>
    | undefined;

  parentsSearch.addEventListener(
    'input',
    () => {
      clearTimeout(parentSearchDebounce);

      const query = parentsSearch.value.trim();

      if (!query) {
        closeParentSuggestions();
        return;
      }

      parentSearchDebounce = setTimeout(async () => {
        try {
          const items = await listCatalogItems(
            options.tenantId,
            query,
          );

          const candidates = items.filter(
            (item) => !selectedParents.has(item.entity_id),
          );

          if (candidates.length === 0) {
            closeParentSuggestions();
            return;
          }

          parentSuggestions.replaceChildren(
            ...candidates.map((candidate) => {
              const suggestion = cloneNested<HTMLLIElement>(
                form,
                '[data-parent-suggestion-template]',
              );

              const button =
                required<HTMLButtonElement>(
                  suggestion,
                  '[data-select]',
                );

              button.textContent = candidate.title;

              button.addEventListener(
                'click',
                () => {
                  selectedParents.set(
                    candidate.entity_id,
                    candidate.title,
                  );

                  renderParentChips();

                  parentsSearch.value = '';
                  closeParentSuggestions();
                  parentsSearch.focus();
                },
                { signal },
              );

              return suggestion;
            }),
          );

          parentSuggestions.hidden = false;
          parentsSearch.setAttribute(
            'aria-expanded',
            'true',
          );
        } catch {
          closeParentSuggestions();
        }
      }, 250);
    },
    { signal },
  );

  parentsSearch.addEventListener(
    'keydown',
    (event) => {
      if (event.key === 'Escape') {
        closeParentSuggestions();
      }
    },
    { signal },
  );

  document.addEventListener(
    'click',
    (event) => {
      if (
        !parentsCombobox.contains(event.target as Node)
      ) {
        closeParentSuggestions();
      }
    },
    { signal },
  );

  /*
   * Slug suggestion
   */

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

    let slugDebounce:
      | ReturnType<typeof setTimeout>
      | undefined;

    const updateSlugSuggestion = () => {
      clearTimeout(slugDebounce);

      slugDebounce = setTimeout(async () => {
        const request = ++suggestionRequest;

        const title =
          displayNameInput.value.trim() ||
          nameInput.value.trim();

        const suggestion = await suggestSlug(
          options.tenantId,
          title,
          'item',
        ).catch(() => '');

        if (
          !slugEdited &&
          request === suggestionRequest
        ) {
          slugInput.value = suggestion;
        }
      }, 250);
    };

    nameInput.addEventListener(
      'input',
      updateSlugSuggestion,
      { signal },
    );

    displayNameInput.addEventListener(
      'input',
      updateSlugSuggestion,
      { signal },
    );
  }

  /*
   * LorenzoScript description editor
   *
   * This is the useful behavior that infoFields() previously supplied,
   * without letting infoFields() construct this form's HTML.
   */

  const editor = createEditor({
    textarea: descriptionInput,

    render: async (source) => {
      const [rendered] =
        await options.renderer([source]);

      descriptionNotes.replaceChildren(
        ...(rendered?.notes ?? []).map((note) => {
          const li = document.createElement('li');
          li.textContent = note;
          return li;
        }),
      );

      return rendered?.html ?? '';
    },
  });

  /*
   * Used-by
   */

  if (options.initial.usedBy !== undefined) {
    usedByField.hidden = false;

    if (options.initial.usedBy.length > 0) {
      usedByEmpty.hidden = true;
      usedByList.hidden = false;

      usedByList.replaceChildren(
        ...options.initial.usedBy.map((item) => {
          const chip = cloneNested<HTMLLIElement>(
            form,
            '[data-used-by-chip-template]',
          );

          required<HTMLElement>(
            chip,
            '[data-title]',
          ).textContent = item.title;

          return chip;
        }),
      );
    }
  }

  /*
   * Submit
   */

  form.addEventListener(
    'submit',
    async (event) => {
      event.preventDefault();

      errorElement.hidden = true;
      errorElement.textContent = '';
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

          /*
           * Existing descriptions don't expose their visibility control
           * here, so retain the original value.
           */
          isPublic:
            options.initial.description !== null
              ? initialDescription.isPublic
              : descriptionPublicInput.checked,

          content: descriptionInput.value,
        };

        await options.onSubmit({
          name,
          parentIds: [...selectedParents.keys()],
          description,
          slug: slugInput.value,
          inPublicCatalog: publicCatalogInput.checked,
        });
      } catch (error) {
        errorElement.hidden = false;
        errorElement.textContent =
          errorReason(error);
      } finally {
        submitButton.disabled = false;
      }
    },
    { signal },
  );

  return {
    element: form,

    destroy() {
      clearTimeout(parentSearchDebounce);
      controller.abort();
      editor.destroy();
    },
  };
}
