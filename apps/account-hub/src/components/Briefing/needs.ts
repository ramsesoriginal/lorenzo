import { regionState } from '@lorenzo/app-shell';
import { BRANDING_CSS_URL } from '../../lib/config';
import type { Task } from '../../lib/home';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Briefing');

const ICON: Record<Task['kind'], string> = {
  update: 'update-available',
  link: 'waiting',
  player: 'kind-beings',
  draft: 'stale',
};

// What needs the person: tasks, never news (AH6), each with where to go. With none, a quiet day says so.
export function showNeeds(root: HTMLElement, tasks: Task[]): void {
  const section = required<HTMLElement>(root, '[data-needs]');
  const empty = required<HTMLElement>(section, '[data-needs-empty]');

  section.hidden = false;

  required<HTMLElement>(section, '[data-needs-list]').replaceChildren(
    ...tasks.map((task) => {
      const fragment = fromTemplate(root, '[data-task-template]');
      const action = required<HTMLAnchorElement>(fragment, '[data-action]');
      const meta = required<HTMLElement>(fragment, '[data-meta]');

      required<HTMLElement>(fragment, '[data-text]').textContent = task.text;
      meta.textContent = task.meta ?? '';
      meta.hidden = !task.meta;
      required<Element>(fragment, '[data-icon]').setAttribute(
        'href',
        `${BRANDING_CSS_URL}/icons.svg#icon-${ICON[task.kind]}`,
      );
      action.textContent = task.action;
      action.href = task.href;

      return rootElement(fragment);
    }),
  );
  empty.hidden = tasks.length > 0;
  empty.replaceChildren(
    ...(tasks.length === 0
      ? [
          regionState(`${BRANDING_CSS_URL}/icons.svg`, {
            kind: 'empty',
            title: 'You’re all caught up',
            text: 'Nothing is waiting for you. Notifications are in the bell.',
          }),
        ]
      : []),
  );
}
