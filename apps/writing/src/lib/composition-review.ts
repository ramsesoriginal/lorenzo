import { renderReview } from '@lorenzo/repo-ui';
import '@lorenzo/repo-ui/repo-ui.css';
import { client, unwrap } from './api';
import { API_BASE_URL } from './config';
import { draftKey, readDrafts } from './drafts';
import type { ApplyRepositoryUpdate } from './repository-comparison';

const node = <K extends keyof HTMLElementTagNameMap>(tag: K, text = '') => {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
};

type Value = Record<string, unknown>;
const record = (value: unknown): Value =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Value) : {};
const list = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

function describeComposition(value: unknown, names: Record<string, string>): string {
  if (value === null || value === undefined) return 'Not present';
  const row = record(value);
  const name = (id: unknown) => names[String(id)] ?? 'Writing element';
  if ('bundle' in row) {
    return [
      String(row.name),
      describeComposition(row.bundle, names),
      describeComposition(row.structure, names),
    ].join('\n\n');
  }
  if ('payloads' in row) {
    return [
      String(row.title ?? 'Writing'),
      ...list(row.payloads).map((item) => {
        const payload = record(item);
        const fields = record(payload.fields);
        if (payload.kind === 'description') return String(fields.content ?? '');
        if (payload.kind === 'picture') return `Picture · ${fields.file_type ?? 'image'}`;
        if (payload.kind === 'document') return `Attachment · ${fields.filename ?? 'document'}`;
        return String(fields.value ?? 'Number');
      }),
    ].join('\n\n');
  }
  const lines: string[] = [];
  if (row.book) lines.push(`Edition of ${name(row.book)}`);
  const placement = record(row.placement);
  if (placement.parent) {
    lines.push(`Inside ${name(placement.parent)} · position ${Number(placement.position) + 1}`);
    if (placement.before) lines.push(`Before ${name(placement.before)}`);
  } else if (list(row.kinds).some((kind) => kind === 'chapter' || kind === 'scene_telling')) {
    lines.push('Unassigned draft');
  }
  const telling = record(row.telling);
  if (telling.scene) {
    lines.push(
      `${telling.shared ? 'Uses the shared writing of' : 'Independent telling of'} ${name(telling.scene)}`,
    );
    if (telling.viewpoint) lines.push(`Viewpoint: ${name(telling.viewpoint)}`);
  }
  if (list(row.kinds).includes('carrier')) {
    const coverage = list(row.coverage);
    lines.push(coverage.length ? 'Covers, in order:' : 'No covered writing');
    for (const item of coverage) {
      const covered = record(item);
      lines.push(
        `• ${name(covered.entry ?? covered.payload)}${covered.before ? `, before ${name(covered.before)}` : ''}`,
      );
    }
  }
  const redirect = record(row.redirect);
  if (redirect.destination) lines.push(`Joined into ${name(redirect.destination)}`);
  const numbering = record(row.numbering);
  if (Object.keys(numbering).length) {
    lines.push(numbering.enabled ? 'Chapter numbering enabled' : 'Chapter numbering disabled');
    if (numbering.unnumbered) lines.push('This Chapter is unnumbered');
    if (numbering.override !== null && numbering.override !== undefined)
      lines.push(`Chapter number: ${numbering.override}`);
    if (numbering.restart) lines.push('Starts a numbering sequence');
    if (numbering.end) lines.push('Ends a numbering sequence');
    for (const [index, item] of list(numbering.levels).entries()) {
      const level = record(item);
      const styles: Record<string, string> = {
        decimal: '1, 2, 3',
        roman: 'I, II, III',
        roman_lower: 'i, ii, iii',
        alphabetic: 'A, B, C',
        alphabetic_lower: 'a, b, c',
      };
      lines.push(
        `Level ${index + 1}: ${styles[String(level.style)] ?? 'Numbers'}, starting at ${level.start}`,
      );
      lines.push(
        level.restart_per_parent ? 'Restarts within each parent' : 'Continues across parents',
      );
      lines.push(level.include_parents ? 'Includes parent numbers' : 'Omits parent numbers');
    }
  }
  const contents = record(row.contents);
  if (Object.keys(contents).length) {
    lines.push(contents.included ? 'Included in contents' : 'Excluded from contents');
    if (contents.role !== 'chapter') lines.push(`Special Chapter: ${contents.role}`);
    if (contents.enabled)
      lines.push(`Contents through ${contents.depth} levels · ${contents.template}`);
    else lines.push('Generated contents disabled');
  }
  return lines.join('\n') || 'No additional structure';
}

export function compositionReview(tenant: string, id: string, apply?: ApplyRepositoryUpdate) {
  const panel = node('details');
  const check = node('button', 'Review composition updates');
  check.type = 'button';
  check.className = 'btn btn-secondary';
  const status = node('p');
  status.setAttribute('role', 'status');
  const result = node('div');
  panel.append(
    node('summary', 'Composition updates'),
    node(
      'p',
      'Review connected writing and structure together. Choose the changes to accept; other writing stays as it is. Attachments are compared by content; previews are not shown.',
    ),
    check,
    status,
    result,
  );
  check.addEventListener('click', async () => {
    check.disabled = true;
    result.replaceChildren();
    status.textContent = 'Comparing the composition…';
    try {
      const comparison = await unwrap(
        await client.GET('/tenants/{tenant_id}/writing/entries/{id}/repository-updates', {
          params: { path: { tenant_id: tenant, id } },
        }),
      );
      if (!panel.isConnected || !panel.open) return;
      const choices: Record<string, 'local' | 'upstream'> = {};
      const accept = node('button', 'Apply selected updates');
      accept.type = 'button';
      accept.className = 'btn btn-primary';
      accept.disabled = true;
      result.append(
        renderReview(
          comparison.rows.map((row) => ({
            id: row.id,
            label: `${row.name} — ${row.field === 'bundle' ? 'Writing' : row.field === 'entry' ? 'Entry' : 'Composition'}`,
            note:
              row.state === 'removed'
                ? 'Removed from the repository. Your writing is retained.'
                : !row.selectable
                  ? 'Removed locally. Copy it explicitly through the repository review to restore it.'
                  : !row.baseline_known
                    ? 'The original composition was not recorded. Taking the repository version explicitly replaces the version shown here.'
                    : row.state === 'conflict'
                      ? 'Both versions changed differently.'
                      : undefined,
            ...(row.selectable ? { choice: { chosen: null } } : {}),
            change: {
              kind: 'value' as const,
              was: row.baseline_known
                ? row.base === null
                  ? 'Not present'
                  : describeComposition(row.base, comparison.names)
                : 'Original not recorded',
              mine: describeComposition(row.local, comparison.names),
              theirs: describeComposition(row.upstream, comparison.names),
            },
          })),
          {
            mode: 'choose',
            onChoose: (key, side) => {
              choices[key] = side === 'mine' ? 'local' : 'upstream';
              accept.disabled = false;
            },
            words: { was: 'Original copy', mine: 'Your saved writing', theirs: 'Repository' },
          },
        ),
      );
      status.textContent = comparison.rows.length
        ? 'Choose what to keep and what to take.'
        : 'No composition updates to review.';
      if (comparison.rows.some((row) => row.selectable)) result.append(accept);
      accept.addEventListener('click', async () => {
        accept.disabled = true;
        check.disabled = true;
        try {
          const action = async () => {
            const me = await unwrap(await client.GET('/me'));
            for (const entry of comparison.affected_entries) {
              if ((await readDrafts(draftKey(API_BASE_URL, me.id, tenant, entry))).length) {
                throw new Error(
                  'There is unsaved writing in this composition. Save or recover it before accepting updates.',
                );
              }
            }
            await unwrap(
              await client.POST('/tenants/{tenant_id}/writing/entries/{id}/repository-updates', {
                params: {
                  path: { tenant_id: tenant, id },
                  header: { 'if-match': comparison.version },
                },
                body: { choices },
              }),
            );
          };
          if (apply) await apply(action, { composition: true });
          else {
            await action();
            location.reload();
          }
        } catch (error) {
          status.textContent =
            error instanceof Error ? error.message : 'The updates could not be applied.';
          accept.disabled = false;
          check.disabled = false;
        }
      });
    } catch (error) {
      status.textContent =
        error instanceof Error ? error.message : 'The composition could not be compared.';
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
