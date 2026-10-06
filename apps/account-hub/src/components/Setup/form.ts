// The form of /setup (ADR 0180): the names, who runs the campaign, and how long the links last.

import { EXPIRY_PRESETS, GM_EXPIRY_PRESETS } from '../../lib/inviteLink';
import type { GmChoice, SetupInput } from '../../lib/setup';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { UserRefOut } from '../../lib/types';
import { renderUserPicker } from '../UserPicker/renderer';

const required = requiredIn('Setup');

// What was asked for, and the two expiries, which are read when a link is made (so a retry an hour
// later is not already short of what the person chose).
export type Submission = {
  input: SetupInput;
  // Who the person found, for the result to name.
  gmLabel: string | null;
  playerExpiry(): string;
  gmExpiry(): string;
};

// Setup forms on a page each get an id for their submit button.
let forms = 0;

function fillPresets(
  select: HTMLSelectElement,
  presets: readonly { id: string; label: string }[],
  selected: string,
): void {
  select.replaceChildren(
    ...presets.map((preset) => new Option(preset.label, preset.id, false, preset.id === selected)),
  );
}

// `root` is the <Setup /> block; `onSubmit` hears a form that is complete.
export function bindSetupForm(
  root: HTMLElement,
  meId: string,
  onSubmit: (submission: Submission) => void,
): void {
  const form = required<HTMLFormElement>(root, '[data-form]');
  const libraryName = required<HTMLInputElement>(root, '[data-library-name]');
  const campaignName = required<HTMLInputElement>(root, '[data-campaign-name]');
  const gameSystem = required<HTMLInputElement>(root, '[data-game-system]');
  const playerExpiry = required<HTMLSelectElement>(root, '[data-player-expiry]');
  const gmExpiry = required<HTMLSelectElement>(root, '[data-gm-expiry]');
  const gmExpiryField = required<HTMLElement>(root, '[data-gm-expiry-field]');
  const pickerBox = required<HTMLElement>(root, '[data-picker-box]');
  const submit = required<HTMLButtonElement>(root, '[data-submit]');
  const status = required<HTMLElement>(root, '[data-form-status]');

  forms += 1;
  form.id = `setup-form-${forms}`;
  submit.setAttribute('form', form.id);

  fillPresets(playerExpiry, EXPIRY_PRESETS, '1w');
  fillPresets(gmExpiry, GM_EXPIRY_PRESETS, '3d');

  const choice = (): 'me' | 'user' | 'link' => {
    const picked = form.querySelector<HTMLInputElement>('input[name="gm-choice"]:checked');

    return picked?.value === 'user' || picked?.value === 'link' ? picked.value : 'me';
  };

  // The person the lookup found, for the choice "someone I can find".
  let found: UserRefOut | null = null;

  renderUserPicker(required<HTMLFormElement>(pickerBox, '[data-user-picker]'), (user) => {
    found = user;
  });

  form.addEventListener('change', () => {
    pickerBox.hidden = choice() !== 'user';
    gmExpiryField.hidden = choice() !== 'link';
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();

    let gm: GmChoice;

    if (choice() === 'me') {
      gm = { kind: 'me' };
    } else if (choice() === 'link') {
      gm = { kind: 'link' };
    } else if (found === null) {
      say(status, 'Look the person up first, or choose another way.');

      return;
    } else {
      gm = { kind: 'user', userId: found.id };
    }

    say(status, '');
    onSubmit({
      input: {
        libraryName: libraryName.value.trim(),
        campaignName: campaignName.value.trim(),
        gameSystem: gameSystem.value.trim(),
        gm,
        meId,
      },
      gmLabel:
        gm.kind === 'user' && found ? (found.display_name ?? found.nickname ?? found.id) : null,
      playerExpiry: () => playerExpiry.value,
      gmExpiry: () => gmExpiry.value,
    });
  });
}
