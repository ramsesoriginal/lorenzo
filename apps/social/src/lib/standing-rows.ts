import type { bindShell } from '@lorenzo/app-shell';
import { el, empty, message } from './dom';
import { parseInput } from './matrix';
import { limitsOf, type StatDef } from './matrix-api';
import type { readEntry } from './social-api';
import { standingMark } from './standing';
import { clearStatValue, setStatValue } from './types-api';

type Shell = NonNullable<ReturnType<typeof bindShell>>;
type Entry = Awaited<ReturnType<typeof readEntry>>;

/** How a standing's scale is said, and where its value comes from (SO3). */
function scaleWords(def: StatDef, own: boolean | null, from: string | null, has: boolean) {
  const scale =
    def.min_value != null && def.max_value != null
      ? `Scale ${def.min_value} to ${def.max_value}.`
      : 'No scale set; shaded across the visible range.';
  const where = !has ? 'No value.' : own ? '' : from ? `Inherited from ${from}.` : 'Inherited.';
  return [scale, where].filter(Boolean).join(' ');
}

/**
 * Every standing the library has, for one relationship (SO2, SO3): its value as a number, a bar and a
 * word, with its scale and where the value comes from, and for those who may write, a field to set it
 * where it is read, even when it has no value yet. A value outside the scale is refused in words; a
 * change says what it did and has Undo.
 */
export function standingRows(options: {
  tenant: string;
  relationship: { id: string; name: string };
  entry: Entry | null;
  stats: readonly StatDef[];
  canEdit: boolean;
  shell: Shell | null;
}): HTMLElement {
  const { tenant, relationship, entry, stats, canEdit, shell } = options;
  const numbers = stats.filter((s) => s.value_type === 'int');
  const list = el('ul', '', 'list');
  list.setAttribute('aria-label', 'Standings of this relationship');
  if (numbers.length === 0) {
    const none = el('div');
    none.append(empty('The library has no standings yet.'));
    return none;
  }
  for (const def of numbers) {
    const held = entry?.stats.find((s) => s.stat_definition_id === def.id);
    const value = typeof held?.value === 'number' ? held.value : null;
    const row = el('li');
    const text = el('div', '', 'stack-tight grow');
    text.append(
      el('span', def.name),
      el(
        'span',
        scaleWords(def, held?.own ?? null, held?.from_entity?.name ?? null, value !== null),
        'status-text',
      ),
    );
    row.append(text);
    if (value !== null && !canEdit) {
      row.append(
        standingMark(
          value,
          { min: def.min_value ?? null, max: def.max_value ?? null },
          held?.own ? 'direct' : 'inherited',
        ),
      );
    }
    if (canEdit) {
      const limits = limitsOf(def);
      const input = el('input', '', 'text-input matrix-input');
      input.inputMode = 'numeric';
      input.setAttribute('aria-label', `${def.name} of ${relationship.name}`);
      input.value = value === null ? '' : String(value);
      let current = value;
      const problem = el('p', '', 'error-text');
      problem.setAttribute('role', 'alert');
      input.addEventListener('change', () => {
        const parsed = parseInput(input.value, limits);
        if (!parsed.ok) {
          problem.textContent = parsed.reason;
          return;
        }
        if (parsed.value === null) {
          problem.textContent =
            'A standing is changed here, not cleared: use the matrix to clear it.';
          input.value = current === null ? '' : String(current);
          return;
        }
        problem.textContent = '';
        const before = current;
        const after = parsed.value;
        void setStatValue(tenant, relationship.id, def.id, after)
          .then(() => {
            current = after;
            shell?.undoable({
              title: `${def.name} of ${relationship.name} is ${after}`,
              undo: () => {
                const back =
                  before === null
                    ? clearStatValue(tenant, relationship.id, def.id)
                    : setStatValue(tenant, relationship.id, def.id, before);
                void back
                  .then(() => {
                    current = before;
                    input.value = before === null ? '' : String(before);
                  })
                  .catch((error) => {
                    problem.textContent = message(error);
                  });
              },
            });
          })
          .catch((error) => {
            problem.textContent = message(error);
          });
      });
      row.append(input, problem);
    }
    list.append(row);
  }
  return list;
}
