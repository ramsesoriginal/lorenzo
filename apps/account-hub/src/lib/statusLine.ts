// The line of status text beside a button or form ("Saving…", "Saved.", an error), which shows
// only while it has something to say. Components keep one as a hidden
// `<span class="status-text" role="status" hidden data-status>` in their markup.
import { showError } from './errorUi';

// Sets what the line says: nothing hides it. `failed` makes it read as an error.
export function say(line: HTMLElement, text: string, failed = false): void {
  line.textContent = text;
  line.classList.toggle('error-text', failed);
  line.hidden = text === '';
}

// An error in words (and a "Log in" button where the session has ended), as showError makes it,
// in a line that is shown for it.
export function sayError(line: HTMLElement, cause: unknown): void {
  line.hidden = false;
  line.classList.add('error-text');
  showError(line, cause);
}
