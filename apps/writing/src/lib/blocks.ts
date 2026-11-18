// What a part of a page can do from its menu and from the selection bar (ADR 0494, W3): split
// here, make a Chapter or a Scene, copy a link. The checks and the operations are the API's; this
// only asks, and says in words why a thing cannot be done.
import { closeDialog, fadeOnDismiss, openDialog } from '@lorenzo/app-shell';
import { client, unwrap } from './api';
import { boundaryBefore } from './blocks-pure';
import { sourceOffset } from './manuscript-split';

/** A plain question for a title. Resolves the trimmed words, or null when dismissed. */
export function askTitle(question: string, confirm: string, initial = ''): Promise<string | null> {
  return new Promise((resolve) => {
    const dialog = document.createElement('dialog');
    const form = document.createElement('form');
    form.className = 'stack-tight';
    const heading = document.createElement('h2');
    heading.textContent = question;
    const input = document.createElement('input');
    input.className = 'text-input';
    input.maxLength = 300;
    input.required = true;
    input.value = initial;
    input.setAttribute('aria-label', 'Title');
    const row = document.createElement('div');
    row.className = 'row';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'btn btn-secondary';
    cancel.textContent = 'Cancel';
    const ok = document.createElement('button');
    ok.type = 'submit';
    ok.className = 'btn btn-primary';
    ok.textContent = confirm;
    row.append(cancel, ok);
    form.append(heading, input, row);
    dialog.append(form);
    document.body.append(dialog);
    fadeOnDismiss(dialog);
    let answer: string | null = null;
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      answer = input.value.trim() || null;
      closeDialog(dialog);
    });
    cancel.addEventListener('click', () => closeDialog(dialog));
    dialog.addEventListener('close', () => {
      dialog.remove();
      resolve(answer);
    });
    openDialog(dialog);
    input.focus();
  });
}

export type Outline = { version: string; elements: { id: string }[] };

/** Make the chosen parts, which must follow one another, into a new Chapter or Scene. */
export async function extractParts(
  tenant: string,
  entry: string,
  outline: Outline,
  ids: string[],
  kind: 'Chapter' | 'Scene',
  title: string,
): Promise<void> {
  const at = ids.map((id) => outline.elements.findIndex((e) => e.id === id));
  if (at.some((i) => i < 0))
    throw new Error('Save this page first: a part that is not saved yet cannot be moved.');
  const sorted = [...at].sort((a, b) => a - b);
  const first = sorted[0] as number;
  const last = sorted[sorted.length - 1] as number;
  if (last - first + 1 !== sorted.length)
    throw new Error(
      `Choose parts that follow one another: ${kind === 'Chapter' ? 'a Chapter' : 'a Scene'} is made from a run of the page.`,
    );
  const elements = outline.elements.slice(first, last + 1).map((e) => e.id);
  const params = {
    path: { tenant_id: tenant, id: entry, operation_id: crypto.randomUUID() },
    header: { 'if-match': outline.version },
  };
  if (kind === 'Scene')
    await unwrap(
      await client.POST(
        '/tenants/{tenant_id}/writing/entries/{id}/scene-extractions/{operation_id}',
        {
          params,
          body: {
            scene_id: crypto.randomUUID(),
            telling_id: crypto.randomUUID(),
            name: title,
            elements,
          },
        },
      ),
    );
  else
    await unwrap(
      await client.POST('/tenants/{tenant_id}/writing/entries/{id}/extractions/{operation_id}', {
        params,
        body: { chapter_id: crypto.randomUUID(), name: title, elements },
      }),
    );
}

/** Split a saved text block at the start of the section the caret is in. */
export async function splitAtCaret(
  tenant: string,
  entry: string,
  payload: string,
  caret: number,
): Promise<string> {
  const available = await unwrap(
    await client.GET(
      '/tenants/{tenant_id}/writing/entries/{id}/payloads/{payload_id}/split-points',
      {
        params: { path: { tenant_id: tenant, id: entry, payload_id: payload } },
      },
    ),
  );
  if (!available.points.length)
    throw new Error(available.explanation ?? 'There is no safe place to split this text.');
  const boundary = boundaryBefore(available.source, caret);
  const offset = boundary === null ? -1 : sourceOffset(available.source, boundary);
  const point = available.points.find((item) => item.offset === offset);
  if (!point)
    throw new Error(
      'Put the cursor in the section that should start the second block. A split falls between whole sections, after a blank line, never inside a list, a quotation or a footnote.',
    );
  const operation = crypto.randomUUID();
  await unwrap(
    await client.POST('/tenants/{tenant_id}/writing/entries/{id}/splits/{operation_id}', {
      params: {
        path: { tenant_id: tenant, id: entry, operation_id: operation },
        header: { 'if-match': available.version },
      },
      body: { payload_id: payload, second_payload_id: crypto.randomUUID(), offset },
    }),
  );
  return operation;
}

const SPLIT = 'lorenzo:writing:split';

/** Keep the receipt of a split for this tab, so the page it reloads to can offer Undo. */
export function rememberSplit(entry: string, operation: string) {
  try {
    sessionStorage.setItem(SPLIT, JSON.stringify({ entry, operation }));
  } catch {
    // Undo is a convenience.
  }
}

/** The split this tab made on `entry`, once: reading it forgets it. */
export function takeSplit(entry: string): string | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(SPLIT) ?? 'null');
    sessionStorage.removeItem(SPLIT);
    return value?.entry === entry && typeof value.operation === 'string' ? value.operation : null;
  } catch {
    return null;
  }
}

/** Join the two texts a split made, while the entry is as `version` says. */
export async function undoSplit(
  tenant: string,
  entry: string,
  operation: string,
  version: string,
): Promise<void> {
  await unwrap(
    await client.DELETE('/tenants/{tenant_id}/writing/entries/{id}/splits/{operation_id}', {
      params: {
        path: { tenant_id: tenant, id: entry, operation_id: operation },
        header: { 'if-match': version },
      },
    }),
  );
}
