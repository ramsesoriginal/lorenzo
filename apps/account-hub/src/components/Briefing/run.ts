import { BRANDING_CSS_URL } from '../../lib/config';
import type { RunItem } from '../../lib/home';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Briefing');

// What the person looks after: a line for each library and repository, with their part in it and where
// it stands, and the ways to make another. The block is there when there is a line, or a way to make one.
export function showRun(
  root: HTMLElement,
  items: RunItem[],
  may: { createLibrary: boolean; createRepository: boolean },
): void {
  const section = required<HTMLElement>(root, '[data-run]');

  required<HTMLElement>(section, '[data-run-list]').replaceChildren(
    ...items.map((item) => {
      const fragment = fromTemplate(root, '[data-run-template]');
      const chip = required<HTMLElement>(fragment, '[data-chip]');
      const role = required<HTMLElement>(fragment, '[data-role]');

      required<HTMLElement>(fragment, '[data-name]').textContent = item.name;
      required<HTMLElement>(fragment, '[data-meta]').textContent = item.meta;
      required<HTMLAnchorElement>(fragment, '[data-link]').href = item.href;

      chip.hidden = item.chip === undefined;
      if (item.chip) {
        chip.dataset.state = item.chip.state;
        required<HTMLElement>(chip, '[data-chip-text]').textContent = item.chip.text;
        required<Element>(chip, '[data-chip-icon]').setAttribute(
          'href',
          `${BRANDING_CSS_URL}/icons.svg#icon-${item.chip.icon}`,
        );
      }

      role.hidden = item.role === undefined;
      role.textContent = item.role ?? '';

      return rootElement(fragment);
    }),
  );
  required<HTMLElement>(section, '[data-setup]').hidden = !may.createLibrary;
  required<HTMLElement>(section, '[data-new-repository]').hidden = !may.createRepository;
  section.hidden = items.length === 0 && !may.createLibrary && !may.createRepository;
}
