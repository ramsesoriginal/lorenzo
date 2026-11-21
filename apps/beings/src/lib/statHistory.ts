// The history of a being's stat changes (BN9, ADR 0525): the steps the API keeps, newest first, who
// made each and when, and what going back to before one of them means.

import type { components } from './api';
import { statLabel } from './statLabel';

export type StatStep = components['schemas']['EntityStatChangeOut'];

/** Who made a step: "you" for the viewer's own, else the name, else "someone". */
export function whoLabel(step: Pick<StatStep, 'actor_id' | 'actor_name'>, me: string): string {
  if (step.actor_id !== null && step.actor_id === me) return 'you';

  return step.actor_name ?? 'someone';
}

const show = (value: StatStep['old']): string =>
  value === null ? 'unset' : typeof value === 'boolean' ? (value ? 'on' : 'off') : String(value);

/** "Hit points 16 → 14". */
export const stepText = (step: Pick<StatStep, 'stat_name' | 'old' | 'new'>): string =>
  `${statLabel(step.stat_name)} ${show(step.old)} → ${show(step.new)}`;

/**
 * What going back to before `steps[index]` asks for: every step from the newest down to it is
 * undone, so each stat they touched goes back to what it was before the oldest of those steps.
 * `steps` is newest first.
 */
export function backTo(steps: readonly StatStep[], index: number): Map<string, StatStep['old']> {
  const wanted = new Map<string, StatStep['old']>();

  for (const step of steps.slice(0, index + 1)) wanted.set(step.stat_definition_id, step.old);

  return wanted;
}
