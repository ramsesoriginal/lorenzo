import { type AppRegistry, appsByJob } from '@lorenzo/app-shell';
import { BRANDING_CSS_URL } from '../../lib/config';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Briefing');

// What the person may open next: every deployed app, by job, as a card with its icon and what it is
// for (D16). The block is there only when the registry names some.
export function showApps(root: HTMLElement, registry: AppRegistry): void {
  const section = required<HTMLElement>(root, '[data-apps]');
  const apps = appsByJob(registry).flatMap((job) => job.apps);

  section.hidden = apps.length === 0;
  required<HTMLElement>(section, '[data-apps-list]').replaceChildren(
    ...apps.map((app) => {
      const fragment = fromTemplate(root, '[data-tile-template]');
      const icon = required<HTMLElement>(fragment, '[data-tile-icon]');

      required<HTMLAnchorElement>(fragment, '[data-link]').href = app.url;
      required<HTMLElement>(fragment, '[data-title]').textContent = app.name;
      required<HTMLElement>(fragment, '[data-meta]').textContent = app.description;
      required<Element>(icon, '[data-icon]').setAttribute(
        'href',
        `${BRANDING_CSS_URL}/icons.svg#icon-${app.icon}`,
      );
      icon.hidden = false;

      return rootElement(fragment);
    }),
  );
}
