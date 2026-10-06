// The two create forms of /tenants: "Create a library" and "Create a
// repository" (ADR 0178), one builder for both since they ask the same three
// things and differ in the word and in the `kind` they send. Like
// userPicker.ts (ADR 0074), a lib/*.ts module that builds DOM.
//
// Only shown to an account whose `GET /me` says it may create (ADR 0175); the
// API's 403 is still shown if it comes, like any other refusal.
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import { kindNoun, kindNounCapitalized, type TenantKind } from './tenantKind';
import { createTenant } from './tenants';
import type { TenantOut } from './types';

// What each one is, in a sentence, so nobody has to know the difference first.
const BLURB: Record<TenantKind, string> = {
  play: 'A library holds the campaigns and characters of a group of people.',
  repository: 'A repository holds content that libraries copy from. Nobody plays in one.',
};

function field(
  labelText: string,
  control: HTMLInputElement | HTMLTextAreaElement,
): HTMLLabelElement {
  const label = document.createElement('label');
  label.textContent = labelText;
  label.append(control);
  return label;
}

// `onCreated` gets the new library or repository, so the page can open it.
export function renderCreateTenantForm(
  kind: TenantKind,
  onCreated: (tenant: TenantOut) => void,
): HTMLElement {
  const noun = kindNoun(kind);
  const form = document.createElement('form');
  form.className = 'create-tenant-form';
  const heading = document.createElement('h2');
  heading.textContent = `Create a ${noun}`;
  const blurb = document.createElement('p');
  blurb.textContent = BLURB[kind];

  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.placeholder = 'Name';
  nameInput.required = true;
  const slugInput = document.createElement('input');
  slugInput.type = 'text';
  slugInput.placeholder = 'Slug (optional, derived from name)';
  const descriptionInput = document.createElement('textarea');
  descriptionInput.placeholder = 'Description (optional)';

  const button = document.createElement('button');
  button.type = 'submit';
  button.textContent = `Create ${noun}`;
  const status = createStatusSpan();

  form.append(
    heading,
    blurb,
    field(`${kindNounCapitalized(kind)} name`, nameInput),
    field('Slug', slugInput),
    field('Description', descriptionInput),
    button,
    status,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    status.textContent = 'Creating…';
    try {
      const created = await createTenant({
        name: nameInput.value.trim(),
        slug: slugInput.value.trim() || null,
        description: descriptionInput.value.trim() || null,
        // A library is what the API makes when the kind is left out; saying so
        // would be noise.
        ...(kind === 'repository' ? { kind } : {}),
      });
      form.reset();
      status.textContent = '';
      onCreated(created);
    } catch (e) {
      showError(status, e);
    }
  });
  return form;
}
