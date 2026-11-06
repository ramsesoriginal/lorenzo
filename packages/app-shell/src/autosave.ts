// The autosave indicator (ADR 0412): a page that saves as the person writes says so, in words and
// an icon, and says honestly when a change is only on this device (ADR 0412, Consequences).

export type AutosaveState = 'saving' | 'saved' | 'device' | 'error';

const TEXT: Record<AutosaveState, string> = {
  saving: 'Saving…',
  saved: 'Saved',
  device: 'Saved on this device. It is sent when you are back online.',
  error: 'Couldn’t save. Your text is still here.',
};

const ICON: Record<AutosaveState, string> = {
  saving: 'waiting',
  saved: 'select-item',
  device: 'offline',
  error: 'warning',
};

export function autosaveText(state: AutosaveState): string {
  return TEXT[state];
}

export type Autosave = { set(state: AutosaveState): void; clear(): void };

const SVG = 'http://www.w3.org/2000/svg';

/** Draws into `host` (a toolbar's end, say) and keeps it announced politely. */
export function createAutosave(host: HTMLElement, sprite: string): Autosave {
  host.setAttribute('role', 'status');
  host.setAttribute('aria-live', 'polite');

  return {
    set(state) {
      const svg = document.createElementNS(SVG, 'svg');
      const use = document.createElementNS(SVG, 'use');
      const text = document.createElement('span');

      svg.setAttribute('class', 'icon');
      svg.setAttribute('aria-hidden', 'true');
      use.setAttribute('href', `${sprite}#icon-${ICON[state]}`);
      svg.append(use);
      text.textContent = TEXT[state];
      host.dataset.state = state;
      host.replaceChildren(svg, text);
    },
    clear() {
      delete host.dataset.state;
      host.replaceChildren();
    },
  };
}
