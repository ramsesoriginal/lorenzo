// What a distance answer says, in words (ADR 0368). Pure, so the page and the tests share it. A number
// is written as the API gave it with the author's unit; it is never converted or rounded to look more
// sure, and a distance that is not known is never written as zero.
export type Answer = {
  mode: 'route' | 'straight';
  state: 'known' | 'partial' | 'unknown' | 'limit_reached';
  value?: number | null;
  at_least?: number | null;
  unit?: string | null;
  unmeasured_legs?: number | null;
  route: readonly Leg[];
  reason?: string | null;
};

export type Leg = {
  connection: { name: string };
  start: { name: string };
  end: { name: string };
  length?: number | null;
};

/** A number with its unit, as the author wrote the unit: *40 miles*. */
export function amount(value: number, unit?: string | null): string {
  const text = value.toLocaleString('en', { maximumFractionDigits: 6 });

  return unit ? `${text} ${unit}` : text;
}

const sentence = (text: string) => (/[.!?]$/.test(text) ? text : `${text}.`);

/** *Straight line: 40 miles*, with how diagonals were counted on a grid, or why it is not known. */
export function straightWords(answer: Answer, metric?: string | null): string {
  if (answer.state === 'known' && typeof answer.value === 'number') {
    const how = metric ? `, counting diagonals by the ${metric} rule` : '';

    return `Straight line: ${amount(answer.value, answer.unit)}${how}.`;
  }

  return `Straight line: ${sentence(answer.reason ?? 'not known')}`;
}

const legs = (n: number) => `${n} ${n === 1 ? 'leg' : 'legs'}`;

/** *By the connections: 52 miles, over 3 legs*, *at least 12 miles; 2 of 4 legs have no length*, or why not. */
export function routeWords(answer: Answer): string {
  if (answer.state === 'known' && typeof answer.value === 'number') {
    const over = answer.route.length ? `, over ${legs(answer.route.length)}` : '';

    return `By the connections: ${amount(answer.value, answer.unit)}${over}.`;
  }
  if (answer.state === 'partial' && typeof answer.at_least === 'number') {
    const missing = answer.unmeasured_legs ?? 0;

    return `By the connections: at least ${amount(answer.at_least, answer.unit)}; ${missing} of ${answer.route.length} legs have no length.`;
  }

  return `By the connections: ${sentence(answer.reason ?? 'not known')}`;
}

/** One leg of a route: *King's Road, Hollowmere to Dunmere: 10 miles*, or *no length*. */
export function legWords(leg: Leg, unit?: string | null): string {
  const length = typeof leg.length === 'number' ? amount(leg.length, unit) : 'no length';

  return `${leg.connection.name}, ${leg.start.name} to ${leg.end.name}: ${length}`;
}
