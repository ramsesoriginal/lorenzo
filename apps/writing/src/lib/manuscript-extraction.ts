import { client, unwrap } from './api';

export function extractionControls(
  tenant: string,
  source: string,
  version: string,
  elements: { id: string; label: string }[],
  done: () => Promise<void>,
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Extract a Chapter';
  details.append(summary);
  const form = document.createElement('form');
  form.className = 'stack-tight';
  const explanation = document.createElement('p');
  explanation.textContent =
    'Move complete text blocks, pictures and entries into a new Chapter here.';
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
  const first = select('First element');
  const last = select('Last element');
  last.value = String(elements.length - 1);
  const label = document.createElement('label');
  label.textContent = 'Extracted chapter title';
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
  submit.textContent = 'Extract Chapter';
  submit.disabled = !elements.length;
  form.append(label, status, submit);
  details.append(form);
  let attempt: { key: string; operation: string; chapter: string } | undefined;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const start = Number(first.value);
    const end = Number(last.value);
    const title = name.value.trim();
    if (!title || end < start) {
      status.textContent = 'Give the Chapter a title and choose the range in reading order.';
      return;
    }
    const selected = elements.slice(start, end + 1).map((item) => item.id);
    const key = JSON.stringify([title, selected]);
    if (!attempt || attempt.key !== key)
      attempt = { key, operation: crypto.randomUUID(), chapter: crypto.randomUUID() };
    submit.disabled = true;
    status.textContent = 'Extracting';
    void (async () => {
      await unwrap(
        await client.POST('/tenants/{tenant_id}/writing/entries/{id}/extractions/{operation_id}', {
          params: {
            path: { tenant_id: tenant, id: source, operation_id: attempt.operation },
            header: { 'if-match': version },
          },
          body: { chapter_id: attempt.chapter, name: title, elements: selected },
        }),
      );
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
