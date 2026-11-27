import { el, field, select } from './dom';
import { parseInput } from './matrix';
import { limitsOf, listStats } from './matrix-api';
import { endPicker, typePicker } from './pickers';
import { createRelationship } from './social-api';
import { setStatValue } from './types-api';
import { defaultName } from './words';

/**
 * The fields that make a relationship: two ends, how it goes, what it is, who may see it, and
 * optionally a standing. `submit` makes it and says in words what it refused; the ends are told
 * apart before anything is written.
 */
export function relationshipForm(
  tenant: string,
  manage: boolean,
  start: { first?: { id: string; name: string } } = {},
) {
  const first = endPicker(tenant, 'First end', () => second.value());
  const second = endPicker(tenant, 'Second end', () => first.value());
  if (start.first) first.set?.(start.first);
  const kind = typePicker(tenant, 'Type of relationship (optional)');
  const direction = select('How it goes', [
    ['both', 'Both ways'],
    ['one', 'From the first end to the second'],
  ]);
  const named = field('Name (optional)');
  const visible = field('Everyone in the library may see it', '', 'checkbox');
  const standing = select('Standing (optional)', [['', 'None']]);
  const value = field('Value of the standing');
  const stats = new Map<string, ReturnType<typeof limitsOf>>();
  // The standings the library has are offered once they are read; without any, the field is absent.
  const standingBox = el('div', '', 'stack-tight');
  standingBox.hidden = true;
  standingBox.append(standing.label, value.label);
  void listStats(tenant)
    .then((all) => {
      for (const stat of all.filter((s) => s.value_type === 'int')) {
        stats.set(stat.id, limitsOf(stat));
        const option = el('option', stat.name);
        option.value = stat.id;
        standing.input.append(option);
      }
      standingBox.hidden = stats.size === 0;
    })
    .catch(() => {});

  const fields: HTMLElement[] = [
    first.label,
    second.label,
    direction.label,
    kind.label,
    named.label,
    standingBox,
    ...(manage
      ? [visible.label]
      : [
          el(
            'p',
            'A relationship you make is for a being of yours and the GMs: it starts restricted and you cannot open it.',
            'status-text',
          ),
        ]),
  ];

  async function submit() {
    const a = first.value();
    const b = second.value();
    if (!a || !b) throw new Error('Choose both ends first.');
    if (a === b) throw new Error('A relationship ties two different entries.');
    const stat = standing.input.value;
    let number: number | null = null;
    if (stat) {
      const parsed = parseInput(value.input.value, stats.get(stat) as ReturnType<typeof limitsOf>);
      if (!parsed.ok) throw new Error(parsed.reason);
      number = parsed.value;
    }
    const type = kind.value();
    const made = await createRelationship(tenant, {
      name: named.input.value.trim() || defaultName(first.name(), second.name(), kind.name()),
      end_a: a,
      end_b: b,
      one_way: direction.input.value === 'one',
      prototypes: type ? [type] : [],
      is_public: manage && visible.input.checked,
    });
    if (stat && number !== null) await setStatValue(tenant, made.id, stat, number);
    return {
      id: made.id,
      ends: [
        { id: a, name: first.name() },
        { id: b, name: second.name() },
      ],
    };
  }

  return { fields, submit };
}
