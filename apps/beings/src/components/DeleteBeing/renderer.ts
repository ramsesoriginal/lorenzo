// Permanent deletion (ADR 0302). The API applies the destructive character guard.
import { confirmDialog } from '@lorenzo/app-shell';
import { client, unwrap } from '../../lib/api';
import { errorMessage } from '../../lib/errorMessage';
import { say } from '../../lib/statusLine';
import type { EntityDetail } from '../../lib/types';

export function renderDeleteBeing(options: {
  root: HTMLElement;
  tenantId: string;
  current: () => EntityDetail;
  onDeleted: () => void;
}) {
  const { root, tenantId } = options;
  let busy = false;
  let allowed = false;

  return {
    allow(canDelete: boolean) {
      allowed = canDelete;
    },
    /** Asks, with the name typed (ADR 0302, D26), and deletes. The page's menu calls it. */
    async run() {
      if (busy || !allowed) return;
      const entity = options.current();

      const confirmed = await confirmDialog({
        title: `Delete ${entity.name}?`,
        body: [
          "This can't be undone.",
          'Its stats, notes, pictures and link name will be deleted. Items it both owns and carries ' +
            'will be deleted too. Borrowed items will be set down. Items it owns elsewhere will be ' +
            'set down and have no owner.',
        ],
        confirm: 'Delete being',
        danger: true,
        typeToConfirm: entity.name,
      });

      if (!confirmed) return;

      busy = true;
      say(root, 'Deleting…');

      try {
        await unwrap(
          await client.DELETE('/tenants/{tenant_id}/beings/{entity_id}', {
            params: { path: { tenant_id: tenantId, entity_id: entity.id } },
            headers: { 'if-match': `W/"${entity.updated_at}"` },
          }),
        );
        options.onDeleted();
      } catch (error) {
        say(root, errorMessage(error), true);
      } finally {
        busy = false;
      }
    },
  };
}
