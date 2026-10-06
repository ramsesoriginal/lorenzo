// The header on every page: where to go, who's signed in, and the theme. Each part has its own
// module; this only starts them.

import { bindPrefetch } from '../../lib/prefetch';
import { renderAccount } from './account';
import { renderNav, showAllowedLinks } from './nav';
import { renderThemeToggle } from './theme';
import { renderUnreadCount } from './unread';

export async function renderSiteHeader(root: HTMLElement): Promise<void> {
  renderThemeToggle(root);
  renderNav(root);

  await renderAccount(root, {
    onSignedIn: async () => {
      renderUnreadCount(root);
      bindPrefetch();
      await showAllowedLinks(root);
    },
  });
}
