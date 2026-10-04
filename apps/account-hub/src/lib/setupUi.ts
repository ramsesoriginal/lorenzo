// /setup (ADR 0180): the form, the progress of the chain, and the result with its
// links, shown once. The logic is setup.ts's; this builds the DOM around it. Like
// userPicker.ts (ADR 0074), a lib/*.ts module that builds DOM.
//
// userPicker.ts builds a <form> of its own, and forms do not nest: the picker
// and the submit button sit outside the setup <form>, tied to it by the `form`
// attribute where they need to be.
import { createStatusSpan } from './dom';
import { showError } from './errorUi';
import {
  EXPIRY_PRESETS,
  expiresAtFor,
  GM_EXPIRY_PRESETS,
  GM_LINK_SHOWN_ONCE_NOTICE,
  type GmExpiryPresetId,
  inviteUrl,
  LINK_SHOWN_ONCE_NOTICE,
} from './inviteLink';
import { renderLinkOnce } from './inviteLinksUi';
import { createInvite } from './invites';
import {
  emptySetupState,
  type GmChoice,
  runSetup,
  type SetupApi,
  SetupFailure,
  type SetupInput,
  type SetupState,
  type StepId,
  stepDoneLabel,
  stepLabel,
  stepsFor,
} from './setup';
import { createCampaign, createTenant, grantCampaignGm } from './tenants';
import type { UserRefOut } from './types';
import { mountUserPicker } from './userPicker';

const FORM_ID = 'setup-form';

function field(labelText: string, control: HTMLInputElement | HTMLSelectElement): HTMLLabelElement {
  const label = document.createElement('label');
  label.textContent = labelText;
  label.append(control);
  return label;
}

function radio(value: string, text: string, checked = false): HTMLLabelElement {
  const input = document.createElement('input');
  input.type = 'radio';
  input.name = 'gm-choice';
  input.value = value;
  input.checked = checked;
  const label = document.createElement('label');
  label.append(input, ` ${text}`);
  return label;
}

function presetSelect(
  presets: readonly { id: string; label: string }[],
  selected: string,
): HTMLSelectElement {
  const select = document.createElement('select');
  for (const preset of presets) {
    const option = document.createElement('option');
    option.value = preset.id;
    option.textContent = preset.label;
    option.selected = preset.id === selected;
    select.append(option);
  }
  return select;
}

// The real calls behind SetupApi: the ones /tenants makes, nothing new. Expiry
// is worked out when a link is made, so a retry an hour later is not already
// short of what the person chose.
function realApi(playerExpiry: () => string, gmExpiry: () => string): SetupApi {
  return {
    createLibrary: (name) => createTenant({ name }),
    createCampaign: (libraryId, campaign) =>
      createCampaign(libraryId, {
        name: campaign.name,
        slug: campaign.slug,
        game_system: campaign.gameSystem,
        description: '',
        secret: false,
      }),
    grantGm: grantCampaignGm,
    createInvite: async (libraryId, campaignId, role) => {
      const invite = await createInvite(libraryId, campaignId, {
        role,
        expires_at: expiresAtFor(
          (role === 'gm' ? gmExpiry() : playerExpiry()) as GmExpiryPresetId,
          new Date(),
        ),
      });
      return { token: invite.token };
    },
  };
}

export function renderSetup(meId: string, container: HTMLElement): void {
  const form = document.createElement('form');
  form.id = FORM_ID;
  form.className = 'create-tenant-form';

  const libraryName = document.createElement('input');
  libraryName.type = 'text';
  libraryName.required = true;
  const campaignName = document.createElement('input');
  campaignName.type = 'text';
  campaignName.required = true;
  const gameSystem = document.createElement('input');
  gameSystem.type = 'text';
  gameSystem.required = true;
  gameSystem.placeholder = 'e.g. D&D 5e';

  const who = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = 'Who runs the campaign?';
  const iDo = radio('me', 'I do', true);
  const find = radio('user', 'Someone I can find, by email or nickname');
  const link = radio('link', "Someone I'll send a link to (they can have an account or make one)");
  who.append(legend, iDo, find, link);

  const playerExpiry = presetSelect(EXPIRY_PRESETS, '1w');
  const gmExpiry = presetSelect(GM_EXPIRY_PRESETS, '3d');
  const gmExpiryField = field('GM link works for', gmExpiry);
  gmExpiryField.hidden = true;

  form.append(
    field('Library name', libraryName),
    field('Campaign name', campaignName),
    field('Game system', gameSystem),
    who,
    field('Link for your players works for', playerExpiry),
    gmExpiryField,
  );

  // The lookup for "someone I can find", outside the form (see the top of the file).
  const pickerBox = document.createElement('div');
  pickerBox.hidden = true;
  const pickerLabel = document.createElement('p');
  pickerLabel.textContent = 'Find the GM:';
  pickerBox.append(pickerLabel);
  let found: UserRefOut | null = null;
  mountUserPicker(pickerBox, (user) => {
    found = user;
  });

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.setAttribute('form', FORM_ID);
  submit.textContent = 'Set up';
  const formStatus = createStatusSpan();

  const choice = (): 'me' | 'user' | 'link' =>
    (form.querySelector('input[name="gm-choice"]:checked') as HTMLInputElement).value as
      | 'me'
      | 'user'
      | 'link';
  form.addEventListener('change', () => {
    pickerBox.hidden = choice() !== 'user';
    gmExpiryField.hidden = choice() !== 'link';
  });

  container.replaceChildren(form, pickerBox, submit, formStatus);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    let gm: GmChoice;
    if (choice() === 'me') gm = { kind: 'me' };
    else if (choice() === 'link') gm = { kind: 'link' };
    else if (found === null) {
      formStatus.textContent = 'Look the person up first, or choose another way.';
      return;
    } else gm = { kind: 'user', userId: found.id };

    const input: SetupInput = {
      libraryName: libraryName.value.trim(),
      campaignName: campaignName.value.trim(),
      gameSystem: gameSystem.value.trim(),
      gm,
      meId,
    };
    const gmLabel =
      gm.kind === 'user' && found ? (found.display_name ?? found.nickname ?? found.id) : null;
    const api = realApi(
      () => playerExpiry.value,
      () => gmExpiry.value,
    );
    renderProgress(container, input, gmLabel, api);
  });
}

// The chain as it runs: each step says what it is doing, and a failure stops
// here, says where and why, and offers to go on from that step.
function renderProgress(
  container: HTMLElement,
  input: SetupInput,
  gmLabel: string | null,
  api: SetupApi,
): void {
  const state: SetupState = emptySetupState();
  const steps = stepsFor(input.gm);
  const list = document.createElement('ul');
  list.className = 'list setup-steps';
  const rows = new Map<StepId, HTMLLIElement>();
  for (const step of steps) {
    const row = document.createElement('li');
    row.textContent = stepLabel(step);
    row.dataset.state = 'waiting';
    rows.set(step, row);
    list.append(row);
  }
  const problem = document.createElement('div');
  problem.setAttribute('role', 'alert');
  container.replaceChildren(list, problem);

  function mark(step: StepId, status: 'start' | 'done'): void {
    const row = rows.get(step);
    if (!row) return;
    row.dataset.state = status === 'start' ? 'working' : 'done';
    row.textContent = status === 'start' ? `${stepLabel(step)}…` : `✓ ${stepDoneLabel(step)}`;
  }

  async function attempt(): Promise<void> {
    problem.replaceChildren();
    try {
      await runSetup(input, state, api, mark);
    } catch (error) {
      if (!(error instanceof SetupFailure)) throw error;
      const row = rows.get(error.step);
      if (row) {
        row.dataset.state = 'failed';
        row.textContent = `✗ ${stepLabel(error.step)}`;
      }
      const why = createStatusSpan();
      showError(why, error.original);
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.textContent = 'Try again';
      retry.addEventListener('click', () => void attempt());
      const lead = document.createElement('p');
      lead.textContent =
        'It stopped here. What is already made is kept, and trying again goes on from this step.';
      problem.append(lead, why, retry);
      return;
    }
    renderResult(container, input, state, gmLabel);
  }
  void attempt();
}

// The result: the links, each shown once, and where to go next. "Done" clears a
// link from the page; nothing keeps it (ADR 0171's panel does the same).
function renderResult(
  container: HTMLElement,
  input: SetupInput,
  state: SetupState,
  gmLabel: string | null,
): void {
  const heading = document.createElement('h2');
  heading.textContent = 'Your table is ready';
  const summary = document.createElement('p');
  summary.textContent = `${input.campaignName} is in ${input.libraryName}.`;

  const who = document.createElement('p');
  if (input.gm.kind === 'me') who.textContent = "You're its GM.";
  else if (input.gm.kind === 'user')
    who.textContent = `${gmLabel ?? 'The person you found'} is its GM.`;
  else who.textContent = 'Send the GM link to the person who should run it.';

  const origin = window.location.origin;
  const boxes: HTMLElement[] = [];
  function linkBox(caption: string, token: string, notice: string, label: string): void {
    const wrap = document.createElement('div');
    wrap.className = 'setup-link';
    const text = document.createElement('p');
    text.textContent = caption;
    wrap.append(
      text,
      renderLinkOnce(inviteUrl(origin, token), () => wrap.replaceChildren(), notice, label),
    );
    boxes.push(wrap);
  }
  if (state.gmLinkToken !== null) {
    linkBox(
      'Link for your GM, which works once:',
      state.gmLinkToken,
      GM_LINK_SHOWN_ONCE_NOTICE,
      'GM invite link',
    );
  }
  if (state.playerLinkToken !== null) {
    linkBox(
      'Link for your players:',
      state.playerLinkToken,
      LINK_SHOWN_ONCE_NOTICE,
      'Link for your players',
    );
  }

  const next = document.createElement('p');
  const campaigns = document.createElement('a');
  campaigns.href = '/campaigns';
  campaigns.textContent = 'Your campaigns';
  const library = document.createElement('a');
  library.href = '/tenants';
  library.textContent = 'Manage the library';
  next.append(campaigns, ' · ', library);

  container.replaceChildren(heading, summary, who, ...boxes, next);
}
