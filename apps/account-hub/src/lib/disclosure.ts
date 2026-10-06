// A <details> whose summary has a chevron and whose body may be empty: one without a body has
// nothing to open to, so it shows no chevron and does not toggle.

export function bindOpensToBody(summary: HTMLElement, chevron: HTMLElement, body: string): void {
  if (body.trim() !== '') return;

  chevron.hidden = true;
  summary.addEventListener('click', (event) => event.preventDefault());
}
