import { errorMessage } from '../../lib/errorMessage';
import { deleteItemInstance, givePack } from '../../lib/items';
import { say } from '../../lib/statusLine';
import type { ItemInstance } from '../../lib/types';
import { packNotRemoved, unpackQuestion } from '../../lib/unpack';
import { type ActionContext, unpackPanelParts } from './panels';

// Unpack… (ADR 0189): a pack instance becomes what its pack lists, for the same owner. Two calls
// the API already has, contents first so a failure of the second leaves a pack and its contents,
// never neither; a dry run of the first is the question.
export function unpackPanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const { element, question, submit, status } = unpackPanelParts(ctx);
  const packId = item.prototype_ids[0];
  const ownerId = item.owner_entity_id;

  if (!packId || !ownerId) {
    // The action isn't offered without both: this is what a stale panel would see.
    question.hidden = true;
    say(status, 'It has no owner to unpack it for.', true);

    return element;
  }

  givePack(ctx.tenantId, packId, ownerId, { dryRun: true }).then(
    (preview) => {
      question.textContent = unpackQuestion(item.title, preview.created);
      submit.hidden = false;
    },
    (error) => {
      question.hidden = true;
      say(status, errorMessage(error), true);
    },
  );

  submit.addEventListener('click', async () => {
    submit.disabled = true;
    say(status, '');

    try {
      await givePack(ctx.tenantId, packId, ownerId);
    } catch (error) {
      say(status, errorMessage(error), true);
      submit.disabled = false;

      return;
    }

    // The board changes from here on, whichever way the delete goes, and no Undo reverses it.
    ctx.undo.forget();

    try {
      await deleteItemInstance(ctx.tenantId, item.entity_id);
      say(status, `Unpacked ${item.title}.`);
      window.setTimeout(ctx.finish, 1200);
    } catch (error) {
      say(status, packNotRemoved(errorMessage(error)), true);
      submit.hidden = true;
      window.setTimeout(ctx.finish, 5000);
    }
  });

  return element;
}
