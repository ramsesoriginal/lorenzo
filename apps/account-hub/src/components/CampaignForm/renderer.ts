// Making a campaign and editing one (ADR 0080): one form, in two modes. A new campaign asks for
// every field and is created; an existing one is shown with what it has and only what changed is
// sent, and it may also say whether its players can make their own items (ADR 0185, 0188, which
// the create call has no field for).

import { createDescriptionEditor } from '../../lib/lorenzoScript';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import { createCampaign, updateCampaign } from '../../lib/tenants';
import type { CampaignOut, CampaignUpdate, TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Campaign form');

export type CampaignFormOptions =
  | { mode: 'create'; tenant: TenantSummaryOut; onDone: () => void }
  // The list's CampaignSummaryOut has no description, so an edit needs the full campaign.
  | { mode: 'edit'; tenant: TenantSummaryOut; campaign: CampaignOut; onDone: () => void };

// `root` is the <CampaignForm /> form. `onDone` is called when a campaign is made, a change is
// saved, there was nothing to save, or Cancel was pressed.
export function renderCampaignForm(root: HTMLElement, options: CampaignFormOptions): void {
  if (!(root instanceof HTMLFormElement)) throw new Error('Campaign form is not a form.');

  const form = root;
  const nameInput = required<HTMLInputElement>(form, '[data-name]');
  const slugInput = required<HTMLInputElement>(form, '[data-slug]');
  const gameSystemInput = required<HTMLInputElement>(form, '[data-game-system]');
  const descriptionInput = required<HTMLTextAreaElement>(form, '[data-description]');
  const secretInput = required<HTMLInputElement>(form, '[data-secret]');
  const selfServiceInput = required<HTMLInputElement>(form, '[data-self-service]');
  const status = required<HTMLElement>(form, '[data-status]');

  const editing = options.mode === 'edit';

  required<HTMLElement>(form, '[data-heading]').hidden = editing;
  required<HTMLElement>(form, '[data-self-service-field]').hidden = !editing;
  required<HTMLElement>(form, '[data-cancel]').hidden = !editing;
  required<HTMLElement>(form, '[data-submit]').textContent = editing ? 'Save' : 'Create campaign';
  // A new campaign has a description; an existing one may have had it emptied.
  descriptionInput.required = !editing;

  if (options.mode === 'edit') {
    const { campaign, onDone } = options;

    nameInput.value = campaign.name;
    slugInput.value = campaign.slug;
    gameSystemInput.value = campaign.game_system;
    descriptionInput.value = campaign.description;
    secretInput.checked = campaign.secret;
    selfServiceInput.checked = campaign.player_self_service;

    required<HTMLButtonElement>(form, '[data-cancel]').addEventListener('click', onDone);
  }

  // The description is LorenzoScript (RFC 0027); made once its value is set, so the preview starts
  // from the text.
  const descriptionEditor = createDescriptionEditor(descriptionInput);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();

    if (options.mode === 'create') {
      say(status, 'Creating…');

      try {
        await createCampaign(options.tenant.id, {
          name: nameInput.value.trim(),
          slug: slugInput.value.trim(),
          game_system: gameSystemInput.value.trim(),
          description: descriptionInput.value.trim(),
          secret: secretInput.checked,
        });
        form.reset();
        // A reset doesn't tell the editor, whose preview follows what is typed.
        void descriptionEditor.refresh();
        say(status, '');
        options.onDone();
      } catch (e) {
        sayError(status, e);
      }

      return;
    }

    const { tenant, campaign, onDone } = options;
    const patch: CampaignUpdate = {};

    if (nameInput.value.trim() !== campaign.name) patch.name = nameInput.value.trim();
    if (slugInput.value.trim() !== campaign.slug) patch.slug = slugInput.value.trim();
    if (gameSystemInput.value.trim() !== campaign.game_system) {
      patch.game_system = gameSystemInput.value.trim();
    }
    if (descriptionInput.value.trim() !== campaign.description) {
      patch.description = descriptionInput.value.trim();
    }
    if (secretInput.checked !== campaign.secret) patch.secret = secretInput.checked;
    if (selfServiceInput.checked !== campaign.player_self_service) {
      patch.player_self_service = selfServiceInput.checked;
    }

    if (Object.keys(patch).length === 0) {
      onDone();

      return;
    }

    say(status, 'Saving…');

    try {
      await updateCampaign(tenant.id, campaign.id, patch);
      onDone();
    } catch (e) {
      sayError(status, e);
    }
  });
}
