// Permanent deletion (ADR 0302). The API applies the destructive character guard.
import { confirmDialog } from '@lorenzo/app-shell';
import { client, unwrap } from '../../lib/api';
import { errorMessage } from '../../lib/errorMessage';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

const required = requiredIn('Delete being');

export function renderDeleteBeing(options: {
  root: HTMLElement;
  tenantId: string;
  current: () => EntityDetail;
  onDeleted: () => void;
}) {
  const { root, tenantId } = options;
  const button = required<HTMLButtonElement>(root, '[data-delete]');
  const status = required<HTMLElement>(root, '[data-status]');
  let busy = false;

  button.addEventListener('click', async () => {
    if (busy) return;
    const entity = options.current();
    // The biggest thing the page does, so the name is typed (ADR 0302, D26).
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
    button.disabled = true;
    say(status, 'Deleting…');
    try {
      await unwrap(
        await client.DELETE('/tenants/{tenant_id}/beings/{entity_id}', {
          params: { path: { tenant_id: tenantId, entity_id: entity.id } },
          headers: { 'if-match': `W/"${entity.updated_at}"` },
        }),
      );
      options.onDeleted();
    } catch (error) {
      say(status, errorMessage(error), true);
    } finally {
      busy = false;
      button.disabled = false;
    }
  });

  return {
    allow(allowed: boolean) {
      root.hidden = !allowed;
    },
  };
}
