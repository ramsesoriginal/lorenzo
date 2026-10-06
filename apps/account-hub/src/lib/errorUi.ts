// An error, shown (ADR 0170). The sentence itself is describeError's; what
// lives here is the DOM around it: when a session has expired, a way back to
// login right where the message is. A lib/*.ts module that
// builds DOM.
import { login } from './auth';
import { describeError, isSessionExpired } from './describeError';

// Replaces what's in `target` with the error's message. A message that has to
// be a button's own label uses describeError directly instead.
export function showError(target: HTMLElement, error: unknown): void {
  target.textContent = describeError(error);
  if (!isSessionExpired(error)) return;
  const loginButton = document.createElement('button');
  loginButton.type = 'button';
  loginButton.textContent = 'Log in';
  loginButton.addEventListener('click', () => void login());
  target.append(' ', loginButton);
}

// The same, as a line of its own, for the places that append one.
export function errorLine(error: unknown): HTMLParagraphElement {
  const line = document.createElement('p');
  line.className = 'error-text';
  line.setAttribute('role', 'alert');
  showError(line, error);
  return line;
}
