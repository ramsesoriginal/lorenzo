import type { BoardState } from '../Board/state';
import type { RenderedUndoBanner } from '../UndoBanner/renderer';

// What the dialog's actions need to know about the page they sit on.
export type ActionContext = {
  tenantId: string;
  viewerIsGm: boolean;
  board: BoardState;
  undo: RenderedUndoBanner;
  // Closes the dialog onto the board as it is now.
  finish(): void;
};

export function actionPanel(): HTMLDivElement {
  const panel = document.createElement('div');

  panel.className = 'character-picker-panel';

  return panel;
}

export function statusLine(): HTMLParagraphElement {
  const status = document.createElement('p');

  status.className = 'picker-status';
  status.hidden = true;

  return status;
}

export function note(text: string): HTMLParagraphElement {
  const paragraph = document.createElement('p');

  paragraph.className = 'field-note';
  paragraph.textContent = text;

  return paragraph;
}
