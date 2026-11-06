import type { RecentPage } from '../../lib/home';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Briefing');

// Where the person was last (this browser's own memory, never sent anywhere): the block is there
// only when there is something to continue.
export function showRecent(root: HTMLElement, pages: RecentPage[]): void {
  const section = required<HTMLElement>(root, '[data-continue]');

  section.hidden = pages.length === 0;
  required<HTMLElement>(section, '[data-continue-list]').replaceChildren(
    ...pages.map((page) => {
      const fragment = fromTemplate(root, '[data-recent-template]');
      const link = required<HTMLAnchorElement>(fragment, '[data-link]');

      link.textContent = page.title;
      link.href = page.href;

      return rootElement(fragment);
    }),
  );
}
