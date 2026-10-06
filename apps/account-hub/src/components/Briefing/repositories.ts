import { fromTemplate, requiredIn, rootElement } from '../../lib/template';
import { tenantHref } from '../../lib/tenantKind';

const required = requiredIn('Briefing');

export type RepositoryCard = {
  name: string;
  // What /tenants names it by.
  slug: string;
  role: string;
  // Draft or when it was published; unknown when the detail couldn't be read.
  status: string | null;
};

// One card for each repository you belong to. A repository is not a library (identity §14.3),
// so it has its own section, which is there only when you have one.
export function showRepositories(root: HTMLElement, repositories: RepositoryCard[]): void {
  const section = required<HTMLElement>(root, '[data-repositories]');

  section.hidden = repositories.length === 0;
  required<HTMLElement>(section, '[data-repositories-list]').replaceChildren(
    ...repositories.map((repository) => {
      const fragment = fromTemplate(root, '[data-repository-template]');
      const status = required<HTMLElement>(fragment, '[data-status]');

      const link = required<HTMLAnchorElement>(fragment, '[data-link]');

      link.textContent = repository.name;
      link.href = tenantHref(repository.slug);
      required<HTMLElement>(fragment, '[data-role]').textContent = repository.role;
      status.textContent = repository.status ?? '';
      status.hidden = repository.status === null;

      return rootElement(fragment);
    }),
  );
}
