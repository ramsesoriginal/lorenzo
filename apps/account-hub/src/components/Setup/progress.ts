// The chain of /setup as it runs (ADR 0180): each step says what it is doing, and a failure stops
// here, says where and why, and offers to go on from that step.

import {
  emptySetupState,
  runSetup,
  type SetupApi,
  SetupFailure,
  type SetupInput,
  type SetupState,
  type StepId,
  stepDoneLabel,
  stepLabel,
  stepsFor,
} from '../../lib/setup';
import { sayError } from '../../lib/statusLine';
import { fromTemplate, requiredIn, rootElement } from '../../lib/template';

const required = requiredIn('Setup');

// Makes what `input` asks for, one step at a time, in `root`'s progress list. Resolves with what
// was made once every step has worked, which may take "Try again" after a step that did not.
export function runProgress(
  root: HTMLElement,
  input: SetupInput,
  api: SetupApi,
): Promise<SetupState> {
  const steps = required<HTMLElement>(root, '[data-steps]');
  const problem = required<HTMLElement>(root, '[data-problem]');
  const why = required<HTMLElement>(root, '[data-why]');
  const retry = required<HTMLButtonElement>(root, '[data-retry]');

  const state = emptySetupState();
  const rows = new Map<StepId, HTMLElement>();

  for (const step of stepsFor(input.gm)) {
    const row = rootElement(fromTemplate(root, '[data-step-template]'));

    row.textContent = stepLabel(step);
    row.dataset.state = 'waiting';
    rows.set(step, row);
  }

  steps.replaceChildren(...rows.values());

  function mark(step: StepId, status: 'start' | 'done'): void {
    const row = rows.get(step);

    if (!row) return;

    row.dataset.state = status === 'start' ? 'working' : 'done';
    row.textContent = status === 'start' ? `${stepLabel(step)}…` : `✓ ${stepDoneLabel(step)}`;
  }

  return new Promise((resolve) => {
    async function attempt(): Promise<void> {
      problem.hidden = true;

      try {
        await runSetup(input, state, api, mark);
      } catch (error) {
        if (!(error instanceof SetupFailure)) throw error;

        const row = rows.get(error.step);

        if (row) {
          row.dataset.state = 'failed';
          row.textContent = `✗ ${stepLabel(error.step)}`;
        }

        sayError(why, error.original);
        problem.hidden = false;

        return;
      }

      resolve(state);
    }

    retry.addEventListener('click', () => void attempt());
    void attempt();
  });
}
