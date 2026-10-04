import { LorenzoApiError } from '../../lib/api';
import { planGive } from '../../lib/boardLogic';
import {
  contentsDone,
  contentsQuestion,
  nothingToGive,
  withContentsDone,
  withContentsQuestion,
} from '../../lib/givingContents';
import { bulkAssignItemInstances, giveContents, setOwner } from '../../lib/items';
import { giveOrAsk, moveAnywayOptions } from '../../lib/moveAnyway';
import type { BeingRef, ItemInstance, ProblemOut } from '../../lib/types';
import { renderBeingPicker } from '../BeingPicker/renderer';
import { containerOf } from '../Board/state';
import { renderCheckboxField } from '../CheckboxField/renderer';
import { type ActionContext, quantityField } from './panels';

function problemText(problem: ProblemOut | null | undefined): string {
  return problem?.detail ?? problem?.title ?? 'Could not give that.';
}

// A bulk result's problem as the error a single write would throw, so a GM can be asked to
// give anyway (ADR 0129).
function problemError(problem: ProblemOut | null | undefined): LorenzoApiError {
  return new LorenzoApiError(problemText(problem), problem?.status ?? 500, problem?.type);
}

// A one-entry bulk-assign with what's inside (ADR 0125): its dry run first, so the question
// says what goes along and what stays, then the give itself.
async function giveWithContents(
  ctx: ActionContext,
  item: ItemInstance,
  being: BeingRef,
  moveToOwner: boolean,
) {
  const entry = {
    entityId: item.entity_id,
    ownerCharacterId: being.entity_id,
    moveToOwner,
    withContents: true,
  };
  const [preview] = await bulkAssignItemInstances(ctx.tenantId, [entry], { dryRun: true });

  if (preview.status === 'error') throw new Error(problemText(preview.problem));

  const question = withContentsQuestion(item.title, being.name, preview.contents);

  if (question && !window.confirm(question)) throw new Error('Nothing given.');

  const [result] = await bulkAssignItemInstances(ctx.tenantId, [entry]);

  if (result.status === 'error') throw new Error(problemText(result.problem));

  ctx.undo.forget();

  return withContentsDone(being.name, result.contents);
}

// Give to…: a player action, not GM-gated (ownership takes any entity id; each write is
// checked server-side). An optional quantity gives part of a stack, by bulk-assign's own
// delegation to split-with-owner.
export function givePanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  const hasStack = Boolean(item.quantity && item.quantity > 1);

  const quantity = quantityField(
    ctx,
    `How many? (of ${item.quantity}, blank for all)`,
    item.quantity ?? undefined,
  );

  const previousOwnerId = item.owner_entity_id;
  const previousContainerId = item.container_entity_id;
  const where = containerOf(ctx.board, item);
  const handOver = where
    ? renderCheckboxField('Hand it over', `Otherwise it stays in the ${where.name}, theirs now.`)
    : null;

  // Only for a container whose column lists something (ADR 0131).
  const alsoInside = ctx.board.occupied.has(item.entity_id)
    ? renderCheckboxField(
        "Also give what's inside",
        "Otherwise what's inside stays whose it is. You'll be asked first.",
      )
    : null;

  const anyway = moveAnywayOptions(ctx.viewerIsGm);

  return renderBeingPicker({
    tenantId: ctx.tenantId,

    async perform(being) {
      const rawQuantity = quantity.input.value.trim();
      const requestedQuantity = rawQuantity ? Number.parseInt(rawQuantity, 10) : undefined;
      const plan = planGive(item, requestedQuantity);
      const moveToOwner = handOver?.input.checked ?? false;

      if (alsoInside?.input.checked) {
        if (plan.mode === 'partial') {
          throw new Error("Give all of it to give what's inside too.");
        }

        return giveWithContents(ctx, item, being, moveToOwner);
      }

      if (plan.mode === 'partial') {
        let splitOffEntityId = '';

        await giveOrAsk(async (flags) => {
          const [result] = await bulkAssignItemInstances(ctx.tenantId, [
            {
              entityId: item.entity_id,
              ownerCharacterId: being.entity_id,
              quantity: plan.quantity,
              moveToOwner,
              ...flags,
            },
          ]);

          if (result.status === 'error' || !result.item_instance) {
            throw problemError(result.problem);
          }

          splitOffEntityId = result.item_instance.entity_id;
        }, anyway);

        // The split-off instance is a new entity, with no owner to restore: merging it
        // back is the honest inverse.
        ctx.undo.recordGive(
          being.entity_id,
          { kind: 'undo-split', splitOffEntityId, intoEntityId: item.entity_id },
          `Gave ${plan.quantity} ${item.title} to ${being.name}.`,
        );
      } else {
        await giveOrAsk(
          (flags) => setOwner(ctx.tenantId, item.entity_id, being.entity_id, moveToOwner, flags),
          anyway,
        );
        ctx.undo.recordGive(
          being.entity_id,
          {
            kind: 'restore-owner',
            entityId: item.entity_id,
            previousOwnerId,
            ...(moveToOwner ? { previousContainerId } : {}),
          },
          `Gave ${item.title} to ${being.name}.`,
        );
      }

      return `Given to ${being.name}.`;
    },

    onDone: ctx.finish,

    extraFields: [
      ...(hasStack ? [quantity.element] : []),
      ...(handOver ? [handOver.element] : []),
      ...(alsoInside ? [alsoInside.element] : []),
    ],
  });
}

// Give what's inside… (ADR 0125): everything inside, not the container, after asking with a
// dry run's answer. Anything not the caller's to give stays whose it is.
export function giveContentsPanel(ctx: ActionContext, item: ItemInstance): HTMLElement {
  return renderBeingPicker({
    tenantId: ctx.tenantId,

    async perform(being) {
      const preview = await giveContents(ctx.tenantId, item.entity_id, being.entity_id, {
        dryRun: true,
      });
      const question = contentsQuestion(item.title, being.name, preview);

      if (!question) throw new Error(nothingToGive(item.title, being.name, preview));
      if (!window.confirm(question)) throw new Error('Nothing given.');

      const results = await giveContents(ctx.tenantId, item.entity_id, being.entity_id);

      ctx.undo.forget();

      return contentsDone(item.title, being.name, results);
    },

    onDone: ctx.finish,
  });
}
