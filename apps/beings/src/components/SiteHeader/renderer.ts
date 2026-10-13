// The header on every page: where to go, which library, who's signed in, and the theme. Each
// part has its own module; this only starts them.

import { renderAccount } from './account';
import { renderNav } from './nav';
import { renderTenantSwitcher } from './tenantSwitcher';
import { renderThemeToggle } from './theme';

export async function renderSiteHeader(root: HTMLElement): Promise<void> {
  renderThemeToggle(root);

  // The nav waits on a library's lookup, so it can finish after the account.
  const nav = renderNav(root);

  void renderAccount(root, { onSignedIn: () => renderTenantSwitcher(root) });

  await nav;
}
