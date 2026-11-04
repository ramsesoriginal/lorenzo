// A repository's card, as Discover's list draws it (ADR 0292) and as Studio's profile preview draws it
// (ADR 0385): one function fills the <template> that DiscoverCard.astro holds, so the two cannot drift.
// The cover is not painted here: the list asks Discover's covers for it (cover.ts), the preview has
// its own.

import type { CardLines } from '../../lib/discover';
import { cloneRoot, requiredIn } from '../../lib/template';

const required = requiredIn('Discover card');

// `root` holds DiscoverCard's templates. `href` is where the name goes, or null for a name that is
// not a link (a repository that is not public has no page to go to).
export function paintCard(root: HTMLElement, lines: CardLines, href: string | null): HTMLElement {
  const card = cloneRoot(root, '[data-card-template]');
  const name = required<HTMLAnchorElement>(card, '[data-name]');

  name.textContent = lines.name;

  if (href === null) {
    name.removeAttribute('href');
    name.removeAttribute('data-link');
  } else {
    name.href = href;
  }

  required<HTMLElement>(card, '[data-summary]').textContent = lines.summary;

  const tags = required<HTMLElement>(card, '[data-tags]');

  tags.replaceChildren(
    ...lines.tags.map((text) => {
      const tagItem = cloneRoot(root, '[data-tag-template]');

      required<HTMLElement>(tagItem, '[data-text]').textContent = text;

      return tagItem;
    }),
  );
  tags.hidden = lines.tags.length === 0;
  required<HTMLElement>(card, '[data-meta]').textContent = lines.meta.join(' · ');

  const publishedBy = required<HTMLElement>(card, '[data-published-by]');

  publishedBy.textContent = lines.publishedBy ?? '';
  publishedBy.hidden = lines.publishedBy === null;

  return card;
}
