import type { TableCard } from '../../lib/campaigns';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { tenantHref } from '../../lib/tenantKind';

const required = requiredIn('Briefing');

// One card for each campaign in a block ("Where you play" or "What you run", named by its selector).
// The block is there only when it has one.
export function showTables(root: HTMLElement, selector: string, cards: TableCard[]): void {
  const section = required<HTMLElement>(root, selector);
  const list = required<HTMLElement>(section, '[data-play-list], [data-run-list]');

  function renderTable(card: TableCard): HTMLElement {
    const fragment = fromTemplate(root, '[data-table-template]');
    const article = rootElement(fragment);
    const characters = required<HTMLElement>(fragment, '[data-characters]');

    required<HTMLElement>(fragment, '[data-name]').textContent = card.name;
    // The library it is in, which opens on /tenants, and the game system.
    const library = required<HTMLAnchorElement>(fragment, '[data-library]');
    const system = required<HTMLElement>(fragment, '[data-system]');

    library.textContent = card.libraryName;
    library.href = tenantHref(card.librarySlug);
    system.textContent = card.gameSystem ? ` · ${card.gameSystem}` : '';
    required<HTMLElement>(fragment, '[data-secret]').hidden = !card.secret;

    required<HTMLElement>(fragment, '[data-roles]').append(
      ...card.roles.map((role) => {
        const badge = rootElement(fromTemplate(root, '[data-role-template]'));

        badge.textContent = role;

        return badge;
      }),
    );

    if (card.characters !== null) {
      characters.hidden = false;
      characters.textContent =
        card.characters.length > 0
          ? `Your characters: ${card.characters.join(', ')}`
          : 'No character yet.';
    }

    return article;
  }

  list.replaceChildren(...cards.map(renderTable));
  section.hidden = cards.length === 0;
}
