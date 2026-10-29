import { client, unwrap } from './api';

export function extractionControls(
  tenant: string,
  source: string,
  version: string,
  elements: { id: string; label: string }[],
  done: () => Promise<void>,
  kind: 'Chapter' | 'Scene' = 'Chapter',
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = `Extract a ${kind}`;
  details.append(summary);
  const form = document.createElement('form');
  form.className = 'stack-tight';
  const explanation = document.createElement('p');
  explanation.textContent =
    kind === 'Scene'
      ? 'Move complete text blocks and pictures into a reusable Scene. A shared telling stays here; edits to the Scene appear wherever it is shared.'
      : 'Move complete text blocks, pictures and entries into a new Chapter here.';
  form.append(explanation);
  const select = (title: string) => {
    const label = document.createElement('label');
    label.textContent = title;
    const input = document.createElement('select');
    input.setAttribute('aria-label', title);
    input.className = 'text-input';
    elements.forEach((item, index) => {
      const option = document.createElement('option');
      option.value = String(index);
      option.textContent = item.label;
      input.append(option);
    });
    label.append(input);
    form.append(label);
    return input;
  };
  const first = select(kind === 'Scene' ? 'First Scene element' : 'First element');
  const last = select(kind === 'Scene' ? 'Last Scene element' : 'Last element');
  last.value = String(elements.length - 1);
  const label = document.createElement('label');
  label.textContent = `Extracted ${kind.toLowerCase()} title`;
  const name = document.createElement('input');
  name.className = 'text-input';
  name.maxLength = 300;
  name.required = true;
  label.append(name);
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = 'btn btn-secondary';
  submit.textContent = `Extract ${kind}`;
  submit.disabled = !elements.length;
  form.append(label, status, submit);
  details.append(form);
  let attempt: { key: string; operation: string; chapter: string; telling: string } | undefined;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const start = Number(first.value);
    const end = Number(last.value);
    const title = name.value.trim();
    if (!title || end < start) {
      status.textContent = `Give the ${kind} a title and choose the range in reading order.`;
      return;
    }
    const selected = elements.slice(start, end + 1).map((item) => item.id);
    const key = JSON.stringify([title, selected]);
    if (!attempt || attempt.key !== key)
      attempt = {
        key,
        operation: crypto.randomUUID(),
        chapter: crypto.randomUUID(),
        telling: crypto.randomUUID(),
      };
    submit.disabled = true;
    status.textContent = 'Extracting';
    void (async () => {
      const params = {
        path: { tenant_id: tenant, id: source, operation_id: attempt.operation },
        header: { 'if-match': version },
      };
      if (kind === 'Scene') {
        await unwrap(
          await client.POST(
            '/tenants/{tenant_id}/writing/entries/{id}/scene-extractions/{operation_id}',
            {
              params,
              body: {
                scene_id: attempt.chapter,
                telling_id: attempt.telling,
                name: title,
                elements: selected,
              },
            },
          ),
        );
      } else {
        await unwrap(
          await client.POST(
            '/tenants/{tenant_id}/writing/entries/{id}/extractions/{operation_id}',
            {
              params,
              body: { chapter_id: attempt.chapter, name: title, elements: selected },
            },
          ),
        );
      }
      await done();
    })()
      .catch((error: unknown) => {
        status.textContent =
          error instanceof Error ? error.message : 'This extraction could not be completed.';
      })
      .finally(() => {
        submit.disabled = false;
      });
  });
  return details;
}
