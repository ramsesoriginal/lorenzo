// Notes on an item instance (ADR 0113): its information of type `note`. Anyone who can see one
// reads it; a GM, or a player whose character owns the item, adds, edits and deletes them. A
// note is private unless "Everyone can read this", and then the owning character reads it, as
// loot-bot's /note makes it.
import type { Renderer } from '../../lib/descriptions';
import { addKnower } from '../../lib/information';
import { renderInformation } from '../Information/renderer';

// A character that can be told something: the one that owns the item, if the viewer plays it.
export type Reader = { entity_id: string; name: string };

export type NotesOptions = {
  tenantId: string;
  renderer: Renderer;
  rowHeading: 'h3' | 'h4';
  // After any save or delete.
  onChanged?: () => void;
};

export type RenderedNotes = {
  // Shows the notes of `entityId`, replacing what was shown. `canWrite`: the viewer may add,
  // edit and delete them. `reader`: who a private note is also for.
  load(entityId: string, viewer: { canWrite: boolean; reader: Reader | null }): Promise<void>;
  // Fetches the notes of `entityId` ahead of `load`.
  prefetch(entityId: string): void;
};

// Who, besides everyone, can read a private note: the reader's players and the GMs.
export function privateTo(reader: Reader | null): string {
  return reader
    ? `Otherwise only ${reader.name}'s players and the campaign's GMs can.`
    : "Otherwise only the campaign's GMs can.";
}

// `root` is whatever contains <Notes />.
export function renderNotes(root: HTMLElement, options: NotesOptions): RenderedNotes {
  const { tenantId } = options;
  const information = renderInformation(root, {
    tenantId,
    renderer: options.renderer,
    onChanged: options.onChanged,
  });

  return {
    prefetch: (entityId) => information.prefetch(entityId, ['note']),

    load(entityId, { canWrite, reader }) {
      return information.load(entityId, {
        types: ['note'],
        canWrite,
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
      });
    },
  };
}
