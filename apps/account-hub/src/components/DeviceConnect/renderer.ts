// Connecting a device (ADR 0269): the code from the address (or typed), what is asking, a name and
// an optional expiry, then Connect or Deny.

import { pageState } from '@lorenzo/app-shell';
import { isAuthenticated, login } from '../../lib/auth';
import { BRANDING_CSS_URL } from '../../lib/config';
import {
  CODE_NOT_FOUND,
  codeFromSearch,
  isCodeNotFound,
  normalizeUserCode,
  suggestedTokenName,
  TOKEN_EXPIRY_PRESETS,
  tokenExpiryFor,
  tokenNameProblem,
} from '../../lib/personalTokens';
import { approveDeviceCode, denyDeviceCode, previewDeviceCode } from '../../lib/personalTokensApi';
import { relativeTime } from '../../lib/relativeTime';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Connect a device');

// `root` is the <DeviceConnect /> block; `search` is the page's query string.
export async function renderDeviceConnect(root: HTMLElement, search: string): Promise<void> {
  const codeForm = required<HTMLFormElement>(root, '[data-code-form]');
  const codeInput = required<HTMLInputElement>(codeForm, '[data-code]');
  const codeStatus = required<HTMLElement>(codeForm, '[data-code-status]');
  const approveForm = required<HTMLFormElement>(root, '[data-approve-form]');
  const client = required<HTMLElement>(approveForm, '[data-client]');
  const shownCode = required<HTMLElement>(approveForm, '[data-shown-code]');
  const name = required<HTMLInputElement>(approveForm, '[data-name]');
  const expiry = required<HTMLSelectElement>(approveForm, '[data-expiry]');
  const approve = required<HTMLButtonElement>(approveForm, '[data-approve]');
  const deny = required<HTMLButtonElement>(approveForm, '[data-deny]');
  const status = required<HTMLElement>(approveForm, '[data-status]');
  const result = required<HTMLElement>(root, '[data-result]');
  const resultBlock = required<HTMLElement>(root, '[data-result-block]');
  const connected = required<HTMLElement>(root, '[data-connected]');
  const ends = required<HTMLElement>(approveForm, '[data-ends]');
  const nameProblem = required<HTMLElement>(approveForm, '[data-name-problem]');
  const signin = required<HTMLElement>(root, '[data-signin]');

  expiry.replaceChildren(
    ...TOKEN_EXPIRY_PRESETS.map(
      (preset) => new Option(preset.label, preset.id, false, preset.id === 'never'),
    ),
  );

  // Shows the choices for a code that is waiting, or says why it isn't.
  async function open(code: string, failure: HTMLElement): Promise<boolean> {
    try {
      const waiting = await previewDeviceCode(code);

      client.textContent = waiting.client_name ?? 'A device';
      shownCode.textContent = waiting.user_code;
      ends.textContent = `It ends ${relativeTime(waiting.expires_at)}.`;
      name.value = suggestedTokenName(waiting.client_name);
      codeForm.hidden = true;
      approveForm.hidden = false;
      approveForm.dataset.code = waiting.user_code;
      name.focus();

      return true;
    } catch (cause) {
      if (isCodeNotFound(cause)) say(failure, CODE_NOT_FOUND, true);
      else sayError(failure, cause);

      return false;
    }
  }

  function finish(text: string, mascot = false): void {
    approveForm.hidden = true;
    codeForm.hidden = true;
    resultBlock.hidden = false;
    // Connected: the mascot, and the words under it say what happens next.
    if (mascot) {
      connected.replaceChildren(
        pageState(BRANDING_CSS_URL, {
          art: 'device-connected',
          alt: 'Catileo asleep on a closed laptop',
          title: 'Connected',
          level: 2,
          text,
        }),
      );
    } else {
      say(result, text);
    }
  }

  codeForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const code = normalizeUserCode(codeInput.value);

    if (code === null) {
      say(codeStatus, 'A code is eight letters, like ABCD-EFGH.', true);

      return;
    }

    say(codeStatus, 'Checking…');

    if (await open(code, codeStatus)) say(codeStatus, '');
  });

  approveForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const code = approveForm.dataset.code ?? '';
    const problem = tokenNameProblem(name.value);

    // Refused here in words, before anything is sent.
    say(nameProblem, problem ?? '', problem !== null);
    if (problem) {
      name.focus();

      return;
    }

    approve.disabled = true;
    deny.disabled = true;
    say(status, 'Connecting…');

    try {
      const expiresAt = tokenExpiryFor(expiry.value, new Date());

      await approveDeviceCode(code, {
        name: name.value.trim(),
        ...(expiresAt === null ? {} : { expires_at: expiresAt }),
      });
      finish(
        'Connected. You can go back to your device: it will pick the token up in a moment.',
        true,
      );
    } catch (cause) {
      approve.disabled = false;
      deny.disabled = false;

      if (isCodeNotFound(cause)) say(status, CODE_NOT_FOUND, true);
      else sayError(status, cause);
    }
  });

  deny.addEventListener('click', async () => {
    approve.disabled = true;
    deny.disabled = true;
    say(status, 'Denying…');

    try {
      await denyDeviceCode(approveForm.dataset.code ?? '');
      finish('Denied. Nothing was connected.');
    } catch (cause) {
      approve.disabled = false;
      deny.disabled = false;
      sayError(status, cause);
    }
  });

  // Not logged in: say so, and that the code is kept (the way back to this address is remembered).
  if (!(await isAuthenticated())) {
    signin.hidden = false;
    required<HTMLButtonElement>(signin, '[data-signin-button]').addEventListener(
      'click',
      () => void login(),
    );

    return;
  }

  const fromAddress = codeFromSearch(search);

  if (fromAddress !== null) {
    resultBlock.hidden = false;
    if (await open(fromAddress, result)) {
      resultBlock.hidden = true;

      return;
    }
  }

  codeForm.hidden = false;
  codeInput.focus();
}
