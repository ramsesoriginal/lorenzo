// What every page's script does around its own rendering: the "Loading…" line goes once there is
// something to show or to say, and a person who is not logged in, or a load that fails, is told in
// the page's `#load-error` line.
import { isAuthenticated } from './auth';
import { showError } from './errorUi';

export const NOT_LOGGED_IN = 'Not logged in. Go back and log in first.';

function elementById(id: string): HTMLElement {
  const element = document.getElementById(id);

  if (!element) {
    throw new Error(`The page is missing #${id}.`);
  }

  return element;
}

// Runs `render` for a page with a `#loading` and a `#load-error` line. A page that is open to
// someone who has not logged in (a link they were sent) passes `needsLogin: false`.
export async function runPage(
  render: () => Promise<void>,
  { needsLogin = true }: { needsLogin?: boolean } = {},
): Promise<void> {
  const loading = elementById('loading');
  const loadError = elementById('load-error');

  try {
    if (needsLogin && !(await isAuthenticated())) {
      loadError.hidden = false;
      loadError.textContent = NOT_LOGGED_IN;

      return;
    }

    await render();
  } catch (cause) {
    loadError.hidden = false;
    showError(loadError, cause);
  } finally {
    loading.hidden = true;
  }
}
