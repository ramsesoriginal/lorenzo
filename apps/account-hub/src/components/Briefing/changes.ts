import { describeChange } from '../../lib/changeText';
import { relativeTime } from '../../lib/relativeTime';
import { fromTemplate, requiredIn } from '../../lib/template';
import type { EntityChange } from '../../lib/types';

const required = requiredIn('Briefing');

export type ChangeContext = {
  characterName(entityId: string): string;
  libraryName(tenantId: string): string | null;
};

// The latest changes to what your characters hold (ADR 0099), one line each. The section is
// there only when there are some.
export function showChanges(
  root: HTMLElement,
  changes: EntityChange[],
  context: ChangeContext,
): void {
  const section = required<HTMLElement>(root, '[data-changes]');

  section.hidden = changes.length === 0;
  required<HTMLElement>(section, '[data-changes-list]').replaceChildren(
    ...changes.map((change) => {
      const fragment = fromTemplate(root, '[data-change-template]');
      const where = required<HTMLElement>(fragment, '[data-where]');

      required<HTMLElement>(fragment, '[data-text]').textContent = describeChange(
        change,
        context.characterName(change.character_entity_id),
      );
      where.textContent = [context.libraryName(change.tenant_id), relativeTime(change.occurred_at)]
        .filter(Boolean)
        .join(' · ');
      where.title = new Date(change.occurred_at).toLocaleString();

      return required<HTMLLIElement>(fragment, 'li');
    }),
  );
}
