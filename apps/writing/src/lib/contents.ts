import { client, unwrap } from './api';

export const contentsOf = async (tenant: string, id: string) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}/contents', {
      params: { path: { tenant_id: tenant, id } },
    }),
  );
export type Contents = Awaited<ReturnType<typeof contentsOf>>;
type Row = Contents['rows'][number];

export function contentsNavigation(rows: Row[], address: (id: string) => string, heading = true) {
  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'Contents');
  if (heading) {
    const title = document.createElement('h2');
    title.textContent = 'Contents';
    nav.append(title);
  }
  const list = document.createElement('ul');
  nav.append(list);
  const ancestors: { depth: number; item: HTMLLIElement; children?: HTMLUListElement }[] = [];
  for (const row of rows) {
    while (ancestors.length && ancestors[ancestors.length - 1].depth >= row.depth) ancestors.pop();
    const parent = ancestors.at(-1);
    let into = list;
    if (parent) {
      if (!parent.children) {
        parent.children = document.createElement('ul');
        parent.item.append(parent.children);
      }
      into = parent.children;
    }
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.textContent = row.label;
    link.href = address(row.id);
    item.append(link);
    into.append(item);
    ancestors.push({ depth: row.depth, item });
  }
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No Chapters are included at this depth.';
    nav.replaceChildren(empty);
  }
  return nav;
}

export function contentsControls(
  tenant: string,
  id: string,
  chapter: boolean,
  current: Contents,
  refresh: () => Promise<void>,
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Contents';
  details.append(summary);
  const form = document.createElement('form');
  form.className = 'stack';
  details.append(form);
  const settings = structuredClone(current.settings);
  const field = (title: string, input: HTMLElement) => {
    const label = document.createElement('label');
    label.className = 'stack-tight';
    label.append(document.createTextNode(title), input);
    form.append(label);
  };
  const check = (title: string, value: boolean, update: (value: boolean) => void) => {
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = value;
    input.addEventListener('change', () => update(input.checked));
    field(title, input);
  };
  if (id === current.root_id) {
    check('Show contents before the manuscript', settings.enabled, (value) => {
      settings.enabled = value;
    });
    const depth = document.createElement('input');
    depth.type = 'number';
    depth.min = '1';
    depth.max = '100';
    depth.required = true;
    depth.value = String(settings.depth);
    depth.className = 'text-input';
    depth.addEventListener('input', () => {
      settings.depth = Number(depth.value);
    });
    field('Chapter levels to include', depth);
    const template = document.createElement('input');
    template.type = 'text';
    template.required = true;
    template.maxLength = 120;
    template.value = settings.template;
    template.className = 'text-input';
    template.addEventListener('input', () => {
      settings.template = template.value;
    });
    field('Contents label template', template);
    const help = document.createElement('p');
    help.textContent = 'Use {title} once, with {number} if wanted. Other text is shown as written.';
    form.append(help);
  } else {
    const note = document.createElement('p');
    note.textContent = 'Depth and labels come from the containing manuscript.';
    form.append(note);
  }
  if (chapter) {
    const role = document.createElement('select');
    role.className = 'text-input';
    for (const [value, title] of [
      ['chapter', 'Chapter'],
      ['contents', 'Contents'],
      ['index', 'Index'],
      ['glossary', 'Glossary'],
    ] as const) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = title;
      role.append(option);
    }
    role.value = settings.role;
    role.addEventListener('change', () => {
      settings.role = role.value as typeof settings.role;
    });
    field('Chapter type', role);
    check('Include in contents', settings.included, (value) => {
      settings.included = value;
    });
    const help = document.createElement('p');
    help.textContent =
      'Contents adds generated links before your text. Index and Glossary keep the text you write.';
    form.append(help);
  }
  const save = document.createElement('button');
  save.type = 'submit';
  save.className = 'btn btn-primary';
  save.textContent = 'Save contents settings';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  form.append(save, status);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    save.disabled = true;
    void (async () => {
      try {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/writing/entries/{id}/contents', {
            params: { path: { tenant_id: tenant, id }, header: { 'if-match': current.version } },
            body: settings,
          }),
        );
        await refresh();
      } catch (error) {
        status.textContent =
          error instanceof Error ? error.message : 'Contents settings could not be saved.';
      } finally {
        save.disabled = false;
      }
    })();
  });
  return details;
}
