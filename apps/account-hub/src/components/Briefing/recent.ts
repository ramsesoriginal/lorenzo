import type { RecentPage } from '../../lib/home';
import { agoText } from '../../lib/home';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Briefing');

// Where the person was last (this browser's own memory, never sent anywhere): a card for each, with
// the app and when it was opened. The block is there only when there is something to continue.
export function showRecent(root: HTMLElement, pages: RecentPage[], now = Date.now()): void {
  const section = required<HTMLElement>(root, '[data-continue]');

  section.hidden = pages.length === 0;
  required<HTMLElement>(section, '[data-continue-list]').replaceChildren(
    ...pages.map((page) => {
      const fragment = fromTemplate(root, '[data-tile-template]');

      required<HTMLAnchorElement>(fragment, '[data-link]').href = page.href;
      required<HTMLElement>(fragment, '[data-title]').textContent = page.title;
      required<HTMLElement>(fragment, '[data-meta]').textContent =
        page.at === undefined ? 'Account' : `Account · opened ${agoText(now, page.at)}`;

      return rootElement(fragment);
    }),
  );
}
