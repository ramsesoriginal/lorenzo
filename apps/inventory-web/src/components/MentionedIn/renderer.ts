import { getBacklinks } from '../../lib/descriptions';
import { entityHref } from '../../lib/entityLinks';
import { cloneTemplate, requiredIn } from '../../lib/template';

export type MentionedInOptions = {
  // The <MentionedIn /> section: hidden unless something links to the entity.
  root: HTMLElement;
  tenantId: string;
};

export type RenderedMentionedIn = {
  // Lists the information whose descriptions link to `entityId`, as far as the viewer may see
  // (ADR 0110).
  load(entityId: string): Promise<void>;
};

const required = requiredIn('Mentioned in');

export function renderMentionedIn(options: MentionedInOptions): RenderedMentionedIn {
  const { root, tenantId } = options;
  const list = required<HTMLUListElement>(root, '[data-list]');
  const template = required<HTMLTemplateElement>(root, '[data-chip-template]');

  return {
    async load(entityId) {
      try {
        const backlinks = await getBacklinks(tenantId, entityId);

        list.replaceChildren(
          ...backlinks.map((backlink) => {
            const chip = cloneTemplate<HTMLLIElement>(template, 'li');
            const link = required<HTMLAnchorElement>(chip, '[data-link]');
            const name = required<HTMLElement>(chip, '[data-name]');
            const href = entityHref(tenantId, backlink);
            // A link when there's a page to go to, plain text when there isn't.
            const label = href ? link : name;

            if (href) link.href = href;

            label.hidden = false;
            label.textContent = backlink.name;
            label.title = backlink.title;
            (href ? name : link).remove();

            return chip;
          }),
        );
        root.hidden = backlinks.length === 0;
      } catch {
        root.hidden = true;
      }
    },
  };
}
