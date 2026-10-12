// A being page's stat values (ADR 0263, 0272): each stat that is not a tag, what the item
// resolves to and where that comes from, a field for its own value, and a way back to inherited.

import { LorenzoApiError } from '../../lib/api';
import { getEntityDetail } from '../../lib/entities';
import { errorMessage } from '../../lib/errorMessage';
import { statLabel } from '../../lib/statLabel';
import { say } from '../../lib/statusLine';
import {
  clearStat,
  parseStat,
  StatChangedError,
  type StatRow,
  type StatValue,
  setStat,
  sourceIn,
  statDefinitions,
  statRows,
} from '../../lib/statValues';
import { cloneTemplate, requiredIn } from '../../lib/template';
import type { EntityDetail } from '../../lib/types';

export type StatEditorOptions = {
  // Whatever contains <StatEditor />.
  root: HTMLElement;
  tenantId: string;
  // After every change, so the page can show the values readers now see.
  onChanged: () => void;
};

export type RenderedStatEditor = {
  load(entityId: string): Promise<void>;
};

const required = requiredIn('Stat editor');

/** The text a field starts with for a value. */
const textOf = (value: StatValue | null) => (value === null ? '' : String(value));

export function renderStatEditor(options: StatEditorOptions): RenderedStatEditor {
  const { root, tenantId } = options;
  const message = required<HTMLElement>(root, '[data-message]');
  const stats = required<HTMLElement>(root, '[data-stats]');
  const status = required<HTMLElement>(root, '[data-status]');
  const template = required<HTMLTemplateElement>(root, '[data-stat-template]');

  return {
    async load(entityId) {
      stats.replaceChildren();
      say(status, '');
      say(message, 'Loading stats…');

      let definitions: Awaited<ReturnType<typeof statDefinitions>>;
      let entity: EntityDetail;

      try {
        [definitions, entity] = await Promise.all([
          statDefinitions(tenantId),
          getEntityDetail(tenantId, entityId),
        ]);
      } catch (error) {
        // Listing definitions needs library membership, unlike writing a stat.
        const member = !(
          error instanceof LorenzoApiError &&
          (error.status === 403 || error.status === 404)
        );

        say(
          message,
          member
            ? `Couldn't load stats: ${errorMessage(error)}`
            : 'Only library members can see the list of stats.',
        );
        return;
      }

      if (definitions.length === 0) {
        say(message, 'This library has no stats yet.');
        return;
      }

      say(message, '');

      const draw = () => {
        stats.replaceChildren(...statRows(definitions, entity).map(drawRow));
      };

      // A write is one at a time: the fields wait while one is on its way.
      const busy = (on: boolean) => {
        for (const control of stats.querySelectorAll<HTMLInputElement | HTMLButtonElement>(
          'input, select, button',
        )) {
          control.disabled = on;
        }
      };

      const change = async (write: () => Promise<EntityDetail>) => {
        busy(true);
        say(status, 'Saving…');

        try {
          entity = await write();
          say(status, 'Saved.');
          options.onChanged();
        } catch (error) {
          say(status, errorMessage(error), true);

          // Show what is there now, whatever was in the way.
          if (error instanceof StatChangedError) {
            entity = await getEntityDetail(tenantId, entityId).catch(() => entity);
          }
        }

        draw();
      };

      function drawRow(row: StatRow): HTMLElement {
        const { definition } = row;
        const form = cloneTemplate<HTMLFormElement>(template, '[data-stat]');
        const label = required<HTMLElement>(form, '[data-label]');
        const control = required<HTMLElement>(form, '[data-control]');
        const clear = required<HTMLButtonElement>(form, '[data-clear]');

        // Our own messages say what is wanted, in place of the browser's.
        form.noValidate = true;
        label.textContent = statLabel(definition.name);
        form.setAttribute('aria-label', `${statLabel(definition.name)} stat`);
        required<HTMLElement>(form, '[data-source]').textContent = sourceIn('being', row);
        clear.hidden = !row.own;

        let field: HTMLInputElement | HTMLSelectElement;

        if (definition.value_type === 'enum') {
          const select = document.createElement('select');
          const none = new Option('Choose a value', '');

          select.append(none);
          // A value the library no longer lists is kept, so the field doesn't misreport it.
          const values = definition.enum_values.includes(textOf(row.value))
            ? definition.enum_values
            : [textOf(row.value), ...definition.enum_values].filter(Boolean);

          for (const value of values) select.append(new Option(value, value));

          select.value = textOf(row.value);
          none.hidden = row.value !== null;
          field = select;
        } else {
          const input = document.createElement('input');

          input.className = 'text-input';
          input.type = definition.value_type === 'int' ? 'number' : 'text';
          if (definition.value_type === 'int') input.step = '1';
          if (definition.value_type === 'float') input.inputMode = 'decimal';
          input.value = textOf(row.value);
          field = input;
        }

        // Named outright: a choice's name would otherwise take in the text of its options.
        field.setAttribute('aria-label', statLabel(definition.name));
        control.append(field);
        required<HTMLButtonElement>(form, '[data-save]').setAttribute(
          'aria-label',
          `Save ${statLabel(definition.name)}`,
        );
        clear.setAttribute('aria-label', `Use inherited ${statLabel(definition.name)}`);

        const seen = { value: row.value, own: row.own };

        form.addEventListener('submit', (event) => {
          event.preventDefault();

          const parsed = parseStat(definition, field.value);

          if ('problem' in parsed) {
            say(status, `${statLabel(definition.name)}: ${parsed.problem}`, true);
            return;
          }

          void change(() => setStat(tenantId, entityId, definition, parsed.value, seen));
        });
        clear.addEventListener('click', () => {
          void change(() => clearStat(tenantId, entityId, definition, seen));
        });

        return form;
      }

      draw();
    },
  };
}
