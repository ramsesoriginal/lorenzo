import { clearContainer, setContainer } from '../../lib/items';
import { moveAnywayOptions, moveOrAsk } from '../../lib/moveAnyway';
import { collectMoveTargets } from '../../lib/moveTargets';
import { splitQuestion } from '../../lib/settingDown';
import type { ItemInstance } from '../../lib/types';
import { type ActionContext, actionPanel, note, reason, showStatus, statusLine } from './panels';

// Move to…: the way to move a single item without dragging it. The candidates are the
// containers on the board (lib/moveTargets.ts), as Merge into… finds its own.
export function movePanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const panel = actionPanel();
  const previousContainerId = item.container_entity_id;

  // Equipping is moving into the being: Equipped is among the targets.
  const targets = collectMoveTargets(item, ctx.board.containers.values(), ctx.board.items.values());

  // Anything in a container can be set down, what's equipped too (ADR 0132).
  const inContainer = item.container_entity_id !== null;

  if (targets.length === 0 && !inContainer) {
    panel.append(note('No other container is visible on the current board.'));

    return panel;
  }

  const status = statusLine();
  const list = document.createElement('div');

  list.className = 'merge-candidates';

  const setDisabled = (disabled: boolean) => {
    for (const button of list.querySelectorAll('button')) button.disabled = disabled;
  };

  async function performMove(targetId: string | null) {
    // Set down, a stack becomes single items: asked first, and then there's no Undo.
    const question = targetId === null ? splitQuestion([item]) : null;

    if (question !== null && !window.confirm(question)) return;

    setDisabled(true);

    try {
      const anyway = moveAnywayOptions(ctx.viewerIsGm);

      // Into a container, it stacks with something identical already there (ADR 0133).
      let merged = false;

      if (targetId) {
        const endedUp = await moveOrAsk(
          (flags) =>
            setContainer(ctx.tenantId, item.entity_id, targetId, {
              ...flags,
              mergeIdentical: true,
            }),
          anyway,
        );

        merged = endedUp.entity_id !== item.entity_id;
      } else {
        await moveOrAsk(
          (flags) =>
            clearContainer(ctx.tenantId, item.entity_id, { ...flags, split: question !== null }),
          anyway,
        );
      }

      // What's split or merged away can't simply be put back.
      if (question === null && !merged) {
        ctx.undo.record(
          { kind: 'restore-container', entityId: item.entity_id, previousContainerId },
          `${targetId === null ? 'Set down' : 'Moved'} ${item.title}.`,
        );
      } else {
        ctx.undo.forget();
      }

      ctx.finish();
    } catch (error) {
      showStatus(status, reason(error), true);
      setDisabled(false);
    }
  }

  const addChoice = (text: string, targetId: string | null) => {
    const button = document.createElement('button');

    button.type = 'button';
    button.textContent = text;
    button.addEventListener('click', () => void performMove(targetId));
    list.append(button);
  };

  if (inContainer) addChoice('Set down', null);

  for (const target of targets) addChoice(target.name, target.id);

  panel.append(list, status);

  return panel;
}
