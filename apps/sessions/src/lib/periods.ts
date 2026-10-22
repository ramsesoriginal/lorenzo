import {
  createPeriodPicker,
  loadPeriods,
  type Mode,
  type PeriodPicker,
  periodLabel,
  summarize,
} from '@lorenzo/period-picker';
import { client } from './api';
import { button, el } from './dom';
import { canEditCalendars } from './names';
import '@lorenzo/period-picker/period-picker.css';

export type PeriodControl = {
  root: HTMLElement;
  /**
   * The period ids to save, creating the dates that do not exist yet, or null when the person
   * did not change the choice (so the write can leave the field alone).
   */
  value(): Promise<string[] | null>;
};

/**
 * One calendar period field: what is chosen now, in words, and a button that opens the picker
 * (ADR 0323). The picker only loads when it is opened, so a page with several of them asks for
 * nothing until someone wants one.
 */
export function periodControl(options: {
  tenant: string;
  label: string;
  mode: Mode;
  initial: readonly string[];
}): PeriodControl {
  const root = el('fieldset', '', 'field period-control');
  root.append(el('legend', options.label, 'field-label'));
  const current = el('p', 'Not set', 'status-text');
  const holder = el('div');
  let picker: PeriodPicker | undefined;
  let changed = false;
  let toggle: HTMLButtonElement | undefined;

  if (options.initial.length) {
    current.textContent = 'Loading…';
    void loadPeriods(client, options.tenant, options.initial)
      .then((found) => {
        if (changed) return;
        current.textContent = found.length
          ? found
              .map((p) => `${p.name}${p.calendar_name ? ` (${p.calendar_name})` : ''}`)
              .join('; ')
          : 'Not set';
      })
      .catch(() => {
        current.textContent = 'Could not read the saved choice.';
      });
  }

  async function open() {
    if (picker) {
      holder.hidden = !holder.hidden;

      return;
    }

    const canCreate = await canEditCalendars(options.tenant);

    picker = createPeriodPicker({
      client,
      tenantId: options.tenant,
      mode: options.mode,
      canCreate,
      initial: options.initial,
      label: options.label,
      onChange(selection) {
        changed = true;
        current.textContent = selection.length
          ? options.mode === 'single'
            ? periodLabel(selection[0] as (typeof selection)[number])
            : summarize(selection).join('; ')
          : 'Not set';
      },
    });
    holder.append(picker.element);
    await picker.ready;
  }

  toggle = button('Choose', async () => {
    await open();

    if (toggle) toggle.textContent = holder.hidden ? 'Choose' : 'Hide the choice';
  });
  root.append(current, toggle, holder);

  return {
    root,
    async value() {
      if (!picker || !changed) return null;

      return picker.resolve();
    },
  };
}
