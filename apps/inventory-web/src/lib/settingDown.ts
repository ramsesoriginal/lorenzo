// Setting things down (ADR 0132): out of every container. A stack of n can't keep its count
// there, so it becomes n single items - and the API refuses that unless asked, so the board
// asks first. Pure, so the wording is tested without a page.
import { LorenzoApiError } from './api';

type Setting = Readonly<{ title: string; quantity?: number | null }>;

const count = (item: Setting) => item.quantity ?? 1;

/**
 * What to ask before setting `items` down, or null when none of them is a stack: "Setting
 * down Arrow ×20 leaves 20 separate items. Set it down?"
 */
export function splitQuestion(items: readonly Setting[]): string | null {
  const stacks = items.filter((item) => count(item) > 1);
  const [only] = stacks;
  if (only === undefined) return null;
  if (items.length === 1) {
    return `Setting down ${only.title} ×${count(only)} leaves ${count(only)} separate items. Set it down?`;
  }
  const pieces = stacks.reduce((total, stack) => total + count(stack), 0);
  const which = stacks.length === 1 ? `${only.title} ×${count(only)}` : `${stacks.length} stacks`;
  return `Setting these down leaves ${which} as ${pieces} separate items. Set them down?`;
}

/** The API refused because a stack can't leave every container unless it's split. */
export function isStackRefusal(error: unknown): error is LorenzoApiError {
  return error instanceof LorenzoApiError && error.problemType === 'stack-needs-container';
}

/** What to ask when deleting `name` would set down a stack that was inside it. */
export function deleteSplitQuestion(name: string): string {
  return `Deleting "${name}" sets down what's inside it, and a stack among that becomes single items. Delete it?`;
}
