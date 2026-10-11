// Connecting a device (ADR 0269): the code from the address (or typed), what is asking, a name and
// an optional expiry, then Connect or Deny.

import {
  CODE_NOT_FOUND,
  codeFromSearch,
  isCodeNotFound,
  normalizeUserCode,
  suggestedTokenName,
  TOKEN_EXPIRY_PRESETS,
  tokenExpiryFor,
} from '../../lib/personalTokens';
import { approveDeviceCode, denyDeviceCode, previewDeviceCode } from '../../lib/personalTokensApi';
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

  function finish(text: string): void {
    approveForm.hidden = true;
    codeForm.hidden = true;
    say(result, text);
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

    approve.disabled = true;
    deny.disabled = true;
    say(status, 'Connecting…');

    try {
      const expiresAt = tokenExpiryFor(expiry.value, new Date());

      await approveDeviceCode(code, {
        name: name.value.trim(),
        ...(expiresAt === null ? {} : { expires_at: expiresAt }),
      });
      finish('Connected. You can go back to your device: it will pick the token up in a moment.');
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

  const fromAddress = codeFromSearch(search);

  if (fromAddress !== null) {
    if (await open(fromAddress, result)) return;
  }

  codeForm.hidden = false;
  codeInput.focus();
}
