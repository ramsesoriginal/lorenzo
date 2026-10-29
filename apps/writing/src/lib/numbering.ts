import { client, unwrap } from './api';

export const numberingOf = async (tenant: string, id: string) =>
  unwrap(
    await client.GET('/tenants/{tenant_id}/writing/entries/{id}/numbering', {
      params: { path: { tenant_id: tenant, id } },
    }),
  );
export const numberedTitle = (name: string, number?: string | null) =>
  number ? `${number} ${name}` : name;

export function numberingControls(
  tenant: string,
  id: string,
  chapter: boolean,
  current: Awaited<ReturnType<typeof numberingOf>>,
  refresh: () => Promise<void>,
) {
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.textContent = 'Numbering';
  details.append(summary);
  const form = document.createElement('form');
  form.className = 'stack';
  const settings = {
    ...structuredClone(current.settings),
    levels: structuredClone(
      current.settings.levels ?? [
        { style: 'decimal' as const, start: 1, restart_per_parent: true, include_parents: true },
      ],
    ),
  };
  const field = (label: string, input: HTMLElement, host: HTMLElement = form) => {
    const wrapper = document.createElement('label');
    wrapper.className = 'stack-tight';
    wrapper.append(document.createTextNode(label), input);
    host.append(wrapper);
  };
  const check = (
    label: string,
    value: boolean,
    update: (value: boolean) => void,
    host: HTMLElement = form,
  ) => {
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = value;
    input.addEventListener('change', () => update(input.checked));
    field(label, input, host);
  };
  const number = (
    label: string,
    value: number | null | undefined,
    update: (value: number | null) => void,
    host: HTMLElement = form,
  ) => {
    const input = document.createElement('input');
    input.type = 'number';
    input.min = '1';
    input.max = '999999';
    input.className = 'text-input';
    input.value = value == null ? '' : String(value);
    input.addEventListener('input', () => update(input.value ? Number(input.value) : null));
    field(label, input, host);
    return input;
  };
  if (current.root_id === id) {
    check('Number Chapters', settings.enabled, (v) => {
      settings.enabled = v;
    });
    const levels = document.createElement('div');
    levels.className = 'stack';
    const draw = () => {
      levels.replaceChildren();
      settings.levels.forEach((rule, i) => {
        const group = document.createElement('fieldset');
        group.className = 'stack-tight';
        const legend = document.createElement('legend');
        legend.textContent = `Level ${i + 1}`;
        group.append(legend);
        const style = document.createElement('select');
        style.className = 'text-input';
        for (const [value, label] of [
          ['decimal', '1, 2, 3'],
          ['roman', 'I, II, III'],
          ['roman_lower', 'i, ii, iii'],
          ['alphabetic', 'A, B, C'],
          ['alphabetic_lower', 'a, b, c'],
        ] as const) {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = label;
          style.append(option);
        }
        style.value = rule.style;
        style.addEventListener('change', () => {
          rule.style = style.value as typeof rule.style;
        });
        field('Number style', style, group);
        number(
          'Start at',
          rule.start,
          (v) => {
            rule.start = v ?? 1;
          },
          group,
        ).required = true;
        check(
          'Restart under each parent',
          rule.restart_per_parent,
          (v) => {
            rule.restart_per_parent = v;
          },
          group,
        );
        check(
          'Include parent numbers',
          rule.include_parents,
          (v) => {
            rule.include_parents = v;
          },
          group,
        );
        levels.append(group);
      });
    };
    draw();
    form.append(levels);
    const actions = document.createElement('div');
    actions.className = 'row';
    for (const [label, action] of [
      [
        'Add level',
        () => {
          const last = settings.levels.at(-1);
          if (last && settings.levels.length < 100) settings.levels.push(structuredClone(last));
        },
      ],
      [
        'Remove last level',
        () => {
          if (settings.levels.length > 1) settings.levels.pop();
        },
      ],
    ] as const) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-secondary';
      button.textContent = label;
      button.addEventListener('click', () => {
        action();
        draw();
      });
      actions.append(button);
    }
    form.append(actions);
  } else {
    const note = document.createElement('p');
    note.textContent = 'Level rules come from the containing manuscript.';
    form.append(note);
  }
  if (chapter) {
    check('Leave this Chapter unnumbered', settings.unnumbered, (v) => {
      settings.unnumbered = v;
    });
    number('Use this number (optional)', settings.override, (v) => {
      settings.override = v;
    });
    check('Restart the sequence here', settings.restart, (v) => {
      settings.restart = v;
    });
    check('End the sequence after this Chapter', settings.end, (v) => {
      settings.end = v;
    });
  }
  const save = document.createElement('button');
  save.type = 'submit';
  save.className = 'btn btn-primary';
  save.textContent = 'Save numbering';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  form.append(save, status);
  details.append(form);
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    save.disabled = true;
    void (async () => {
      try {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/writing/entries/{id}/numbering', {
            params: { path: { tenant_id: tenant, id }, header: { 'if-match': current.version } },
            body: settings,
          }),
        );
        await refresh();
      } catch (error) {
        status.textContent =
          error instanceof Error ? error.message : 'Numbering could not be saved.';
      } finally {
        save.disabled = false;
      }
    })();
  });
  return details;
}
