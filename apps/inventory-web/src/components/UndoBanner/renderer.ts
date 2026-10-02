import { createUndoController, type UndoPayload } from '../../lib/boardLogic';
import {
  clearContainer,
  mergeItemInstance,
  setContainer,
  setOwner,
  splitItemInstance,
  unsetOwner,
} from '../../lib/items';

export type UndoBannerOptions = {
  root: HTMLElement;
  tenantId: string;
  // After a give, taking it back is a give too (ADR 0124): only whoever controls the new
  // owner may.
  mayUndoGiveTo(recipientId: string): boolean;
  // The pending action was reversed.
  onApplied(): void;
  onError(message: string): void;
};

export type RenderedUndoBanner = {
  record(payload: UndoPayload, description: string): void;
  // Offers an Undo for a give only if the viewer could take it back, else forgets any.
  recordGive(recipientId: string, payload: UndoPayload, description: string): void;
  forget(): void;
  destroy(): void;
};

function required<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Undo banner is missing ${selector}.`);
  }

  return element;
}

export function renderUndoBanner(options: UndoBannerOptions): RenderedUndoBanner {
  const { root } = options;
  const controller = new AbortController();
  const { signal } = controller;

  const message = required<HTMLElement>(root, '[data-message]');
  const undoButton = required<HTMLButtonElement>(root, '[data-undo]');

  // One slot, as in apps/loot-bot (ADR 0068): each new undoable action replaces whatever was
  // pending. The state machine is in lib/boardLogic.ts.
  const undo = createUndoController(options.tenantId, {
    setOwner,
    unsetOwner,
    setContainer,
    clearContainer,
    splitItemInstance,
    mergeItemInstance,
  });

  function record(payload: UndoPayload, description: string) {
    message.textContent = description;
    root.hidden = false;
    undo.record(payload, () => {
      root.hidden = true;
    });
  }

  function forget() {
    undo.clear();
    root.hidden = true;
  }

  undoButton.addEventListener(
    'click',
    async () => {
      if (!undo.getPending()) return;

      root.hidden = true;

      try {
        await undo.apply();
        options.onApplied();
      } catch (error) {
        options.onError(error instanceof Error ? error.message : String(error));
      }
    },
    { signal },
  );

  return {
    record,

    recordGive(recipientId, payload, description) {
      if (options.mayUndoGiveTo(recipientId)) {
        record(payload, description);
      } else {
        forget();
      }
    },

    forget,

    destroy() {
      controller.abort();
    },
  };
}
