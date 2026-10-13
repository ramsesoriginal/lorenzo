// A line of status text that shows only while it has something to say, and reads as an error
// when `failed`.
export function say(line: HTMLElement, text: string, failed = false) {
  line.textContent = text;
  line.classList.toggle('error-text', failed);
  line.hidden = !text;
}
