// "Create a library" and "Create a repository" (ADR 0178): one form for both, since they ask the same
// three things and differ in the word and in the `kind` they send. The API's 403 is still shown if
// it comes, like any other refusal (ADR 0175).

import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { kindNoun, kindNounCapitalized, type TenantKind } from '../../lib/tenantKind';
import { createTenant } from '../../lib/tenants';
import type { TenantOut } from '../../lib/types';

const required = requiredIn('Create tenant');

// What each one is, in a sentence, so nobody has to know the difference first.
const BLURB: Record<TenantKind, string> = {
  play: 'A library holds the campaigns and characters of a group of people.',
  repository: 'A repository holds content that libraries copy from. Nobody plays in one.',
};

// `root` is the <CreateTenant /> form. `onCreated` gets the new library or repository, so the page
// can open it.
export function renderCreateTenant(
  root: HTMLFormElement,
  kind: TenantKind,
  onCreated: (tenant: TenantOut) => void,
): void {
  const noun = kindNoun(kind);
  const name = required<HTMLInputElement>(root, '[data-name]');
  const slug = required<HTMLInputElement>(root, '[data-slug]');
  const description = required<HTMLTextAreaElement>(root, '[data-description]');
  const status = required<HTMLElement>(root, '[data-status]');

  required<HTMLElement>(root, '[data-heading]').textContent = `Create a ${noun}`;
  required<HTMLElement>(root, '[data-blurb]').textContent = BLURB[kind];
  required<HTMLElement>(root, '[data-name-label]').textContent =
    `${kindNounCapitalized(kind)} name`;
  required<HTMLElement>(root, '[data-submit]').textContent = `Create ${noun}`;

  root.addEventListener('submit', async (event) => {
    event.preventDefault();
    say(status, 'Creating…');

    try {
      const created = await createTenant({
        name: name.value.trim(),
        slug: slug.value.trim() || null,
        description: description.value.trim() || null,
        // A library is what the API makes when the kind is left out; saying so would be noise.
        ...(kind === 'repository' ? { kind } : {}),
      });

      root.reset();
      say(status, '');
      onCreated(created);
    } catch (cause) {
      sayError(status, cause);
    }
  });
}
