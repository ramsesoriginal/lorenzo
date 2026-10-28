import { client, unwrap } from './api';

// Textareas normalize CRLF and their caret counts UTF-16 units. API offsets count Unicode
// code points in the untouched saved source. Translate only the chosen boundary, in one pass.
export function sourceOffset(source: string, caret: number): number {
  let displayed = 0;
  let offset = 0;
  for (const char of source) {
    if (displayed >= caret) break;
    if (char !== '\r') displayed += char.length;
    offset++;
  }
  return offset;
}

export function splitControls(
  tenant: string,
  entry: string,
  payload: string,
  done: () => Promise<void>,
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Split text';
  details.append(summary);
  let loaded = false;
  details.addEventListener('toggle', () => {
    if (!details.open || loaded) return;
    loaded = true;
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    details.append(status);
    void (async () => {
      const available = await unwrap(
        await client.GET(
          '/tenants/{tenant_id}/writing/entries/{id}/payloads/{payload_id}/split-points',
          {
            params: { path: { tenant_id: tenant, id: entry, payload_id: payload } },
          },
        ),
      );
      if (!available.points.length) {
        status.textContent = available.explanation ?? 'No safe section boundary here.';
        return;
      }
      const help = document.createElement('p');
      help.textContent =
        'Place the cursor at the start of the section that should begin the second text block, after a blank line, then choose it. Your saved text stays unchanged until you confirm.';
      const text = document.createElement('textarea');
      text.className = 'text-input';
      text.readOnly = true;
      text.rows = 8;
      text.value = available.source;
      text.setAttribute('aria-label', 'Text to split');
      const choose = document.createElement('button');
      choose.type = 'button';
      choose.className = 'btn btn-secondary';
      choose.textContent = 'Choose section';
      const confirm = document.createElement('button');
      confirm.type = 'button';
      confirm.className = 'btn btn-secondary';
      confirm.textContent = 'Split here';
      confirm.hidden = true;
      let selected: { offset: number; operation: string; second: string } | undefined;
      choose.addEventListener('click', () => {
        let boundary = 0;
        for (const gap of text.value.matchAll(/\n[ \t]*\n(?:[ \t]*\n)*/g)) {
          const end = gap.index + gap[0].length;
          if (end > text.selectionStart) break;
          boundary = end;
        }
        const offset = sourceOffset(available.source, boundary);
        const point = available.points.find((item) => item.offset === offset);
        if (!point) {
          selected = undefined;
          confirm.hidden = true;
          status.textContent =
            'Choose a blank-line boundary before a complete section. Keep lists, quotations, shared footnotes and repeated headings together.';
          return;
        }
        if (selected?.offset !== offset)
          selected = { offset, operation: crypto.randomUUID(), second: crypto.randomUUID() };
        status.textContent = `The second text block will begin: ${point.following}`;
        confirm.hidden = false;
      });
      confirm.addEventListener('click', () => {
        if (!selected) return;
        const attempt = selected;
        confirm.disabled = choose.disabled = true;
        void (async () => {
          await unwrap(
            await client.POST('/tenants/{tenant_id}/writing/entries/{id}/splits/{operation_id}', {
              params: {
                path: { tenant_id: tenant, id: entry, operation_id: attempt.operation },
                header: { 'if-match': available.version },
              },
              body: {
                payload_id: payload,
                second_payload_id: attempt.second,
                offset: attempt.offset,
              },
            }),
          );
          await done();
        })()
          .catch((error: unknown) => {
            status.textContent =
              error instanceof Error ? error.message : 'This split could not be completed.';
          })
          .finally(() => {
            confirm.disabled = choose.disabled = false;
          });
      });
      details.append(help, text, choose, confirm);
    })().catch((error: unknown) => {
      status.textContent =
        error instanceof Error ? error.message : 'The saved text could not be read.';
      loaded = false;
    });
  });
  return details;
}
