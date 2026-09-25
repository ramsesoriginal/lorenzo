// Notes on an item instance (ADR 0113): its information of type `note`. Anyone
// who can see one reads it; a GM, or a player whose character owns the item,
// adds, edits and deletes them. A note is private unless "Everyone can read
// this", and then the owning character reads it, as loot-bot's /note makes it.
import type { Renderer } from './descriptions';
import { addKnower } from './information';
import { renderInformationManager } from './informationManager';

/** A character that can be told something: the one that owns the item, if the viewer plays it. */
export type Reader = { entity_id: string; name: string };

/** Who, besides everyone, can read a private note: the reader's players and the GMs. */
export function privateTo(reader: Reader | null): string {
  return reader
    ? `Otherwise only ${reader.name}'s players and the campaign's GMs can.`
    : "Otherwise only the campaign's GMs can.";
}

/** Renders the notes into `container`, with writing if `canWrite`. */
export function renderNotes(
  container: HTMLElement,
  options: {
    tenantId: string;
    entityId: string;
    renderer: Renderer;
    canWrite: boolean;
    reader: Reader | null;
    rowHeading: 'h3' | 'h4';
    onChanged?: () => void;
  },
): Promise<void> {
  const { tenantId, reader } = options;
  return renderInformationManager(container, {
    tenantId,
    entityId: options.entityId,
    renderer: options.renderer,
    onChanged: options.onChanged ?? (() => {}),
    kind: {
      types: ['note'],
      canWrite: options.canWrite,
      initial: { title: 'Note', type: 'note', isPublic: false, content: '' },
      showType: false,
      addLabel: 'Add a note',
      empty: 'No notes yet.',
      visibilityLabel: 'Everyone can read this',
      visibilityNote: privateTo(reader),
      describe: (info) => (info.is_public ? 'Everyone can read this' : 'Private'),
      rowHeading: options.rowHeading,
      // A private note needs its reader; one that was private already has one.
      afterSave: async (saved, before) => {
        if (saved.isPublic || !reader || (before && !before.is_public)) return;
        await addKnower(tenantId, saved.id, reader.entity_id);
      },
    },
  });
}
