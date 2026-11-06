import { DELETED, renderReview } from '@lorenzo/repo-ui';
import '@lorenzo/repo-ui/repo-ui.css';
import { client, unwrap } from './api';

function manuscript(value: { [key: string]: unknown } | null | undefined) {
  if (!value) return DELETED;
  const pieces = [String(value.title ?? 'Manuscript')];
  for (const item of Array.isArray(value.payloads) ? value.payloads : []) {
    const fields = item.fields ?? {};
    if (item.kind === 'description') {
      pieces.push(String(fields.content ?? ''));
    } else if (item.kind === 'picture') {
      pieces.push(`Picture (${String(fields.file_type ?? 'image')})`);
    } else if (item.kind === 'document') {
      pieces.push(`Document: ${String(fields.filename ?? 'attachment')}`);
    } else {
      pieces.push(String(fields.value ?? ''));
    }
  }
  return pieces.join('\n\n');
}

export type ApplyRepositoryUpdate = (action: () => Promise<void>) => Promise<void>;

export function repositoryComparison(tenant: string, id: string, apply?: ApplyRepositoryUpdate) {
  const panel = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Repository comparison';
  const hint = document.createElement('p');
  hint.textContent =
    'Compare saved direct writing. Unsaved edits and chapter structure are not included. Pictures and attachments are compared by content; their previews are not shown here.';
  const check = document.createElement('button');
  check.type = 'button';
  check.className = 'btn btn-secondary';
  check.textContent = 'Compare saved writing';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const result = document.createElement('div');
  panel.append(summary, hint, check, status, result);
  check.addEventListener('click', async () => {
    check.disabled = true;
    result.replaceChildren();
    status.textContent = 'Comparing saved writing…';
    try {
      const comparison = await unwrap(
        await client.GET('/tenants/{tenant_id}/writing/entries/{id}/repository-comparison', {
          params: { path: { tenant_id: tenant, id } },
        }),
      );
      if (!panel.isConnected || !panel.open) return;
      const words = {
        not_copied: 'This entry was not copied from a repository.',
        no_baseline:
          'This copy has no saved manuscript baseline. Its changes cannot be compared safely yet.',
        local_unavailable: 'The copied manuscript bundle is no longer available here.',
        unchanged: 'The saved writing still matches the original copy.',
        local: 'Only your saved writing has changed.',
        upstream:
          'The repository writing changed. Your saved writing still matches the original copy.',
        matching: 'Your saved writing and the repository match after changes.',
        conflict: 'Both versions changed differently.',
      };
      status.textContent = words[comparison.state];
      if (!comparison.base) return;
      const name = document.createElement('p');
      name.textContent = comparison.repository_name ?? 'Repository';
      const accept = async (side: 'mine' | 'theirs') => {
        if (!apply || check.disabled || !comparison.version) return;
        check.disabled = true;
        try {
          await apply(async () => {
            await unwrap(
              await client.POST('/tenants/{tenant_id}/writing/entries/{id}/repository-comparison', {
                params: {
                  path: { tenant_id: tenant, id },
                  header: { 'if-match': comparison.version as string },
                },
                body: { choice: side === 'mine' ? 'local' : 'upstream' },
              }),
            );
          });
          if (panel.isConnected) {
            result.replaceChildren();
            status.textContent =
              side === 'mine' ? 'Kept your writing.' : 'Repository writing saved.';
          }
        } catch (error) {
          status.textContent =
            error instanceof Error ? error.message : 'The update could not be accepted.';
        } finally {
          check.disabled = false;
        }
      };
      result.append(
        name,
        renderReview(
          [
            {
              id: 'manuscript',
              label: 'Saved direct manuscript',
              ...(comparison.update_allowed && apply ? { choice: { chosen: null } } : {}),
              change: {
                kind: 'value',
                was: manuscript(comparison.base),
                theirs: manuscript(comparison.upstream),
                mine: manuscript(comparison.local),
              },
            },
          ],
          {
            mode: 'act',
            onChoose: (_id, side) => void accept(side),
            words: { was: 'Original copy', theirs: 'Repository', mine: 'Your saved writing' },
          },
        ),
      );
      const note = document.createElement('p');
      note.textContent =
        comparison.update_reason ??
        (apply
          ? 'Accepting keeps all existing audiences and saves the previous text in revisions.'
          : 'Open Write to accept an update.');
      result.append(note);
    } catch (error) {
      result.replaceChildren();
      status.textContent =
        error instanceof Error ? error.message : 'The manuscript could not be compared.';
    } finally {
      check.disabled = false;
    }
  });
  panel.addEventListener('toggle', () => {
    if (!panel.open) {
      result.replaceChildren();
      status.textContent = '';
    }
  });
  return panel;
}
