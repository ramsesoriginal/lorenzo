// Campaign create/edit panels, split out of tenants.astro - see ADR 0080.
// Like userPicker.ts (ADR 0074), this is a lib/*.ts module that builds and
// returns DOM, not just an API wrapper.

import { createCampaign, getCampaign, updateCampaign } from './tenants';
import type { CampaignOut, CampaignSummaryOut, CampaignUpdate, TenantSummaryOut } from './types';

// The list view's CampaignSummaryOut has no description, so editing needs
// the one extra GET .../campaigns/{id} fetch (CampaignOut) - only when
// Edit is actually clicked, not on every page load.
function renderEditCampaignForm(
  tenant: TenantSummaryOut,
  campaign: CampaignOut,
  onDone: () => void,
): HTMLFormElement {
  const form = document.createElement('form');
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.value = campaign.name;
  const slugInput = document.createElement('input');
  slugInput.type = 'text';
  slugInput.value = campaign.slug;
  const gameSystemInput = document.createElement('input');
  gameSystemInput.type = 'text';
  gameSystemInput.value = campaign.game_system;
  const descriptionInput = document.createElement('textarea');
  descriptionInput.value = campaign.description;
  const secretLabel = document.createElement('label');
  const secretInput = document.createElement('input');
  secretInput.type = 'checkbox';
  secretInput.checked = campaign.secret;
  secretLabel.append(secretInput, 'Secret');
  const saveButton = document.createElement('button');
  saveButton.type = 'submit';
  saveButton.textContent = 'Save';
  const cancelButton = document.createElement('button');
  cancelButton.type = 'button';
  cancelButton.textContent = 'Cancel';
  const status = document.createElement('span');
  status.className = 'status-text';
  status.setAttribute('role', 'status');

  form.append(
    nameInput,
    slugInput,
    gameSystemInput,
    descriptionInput,
    secretLabel,
    saveButton,
    cancelButton,
    status,
  );

  cancelButton.addEventListener('click', onDone);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
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

    if (Object.keys(patch).length === 0) {
      onDone();
      return;
    }
    status.textContent = 'Saving…';
    try {
      await updateCampaign(tenant.id, campaign.id, patch);
      onDone();
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });

  return form;
}

export function renderEditToggle(
  tenant: TenantSummaryOut,
  campaign: CampaignSummaryOut,
  onChanged: () => void,
): HTMLElement {
  const container = document.createElement('span');
  const editButton = document.createElement('button');
  editButton.type = 'button';
  editButton.textContent = 'Edit';
  const status = document.createElement('span');
  status.className = 'status-text';
  status.setAttribute('role', 'status');
  container.append(editButton, status);

  editButton.addEventListener('click', async () => {
    editButton.disabled = true;
    status.textContent = 'Loading…';
    try {
      const full = await getCampaign(tenant.id, campaign.id);
      status.textContent = '';
      container.replaceChildren(renderEditCampaignForm(tenant, full, onChanged));
    } catch (e) {
      editButton.disabled = false;
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });

  return container;
}

export function renderCreateCampaignForm(
  tenant: TenantSummaryOut,
  onCreated: () => void,
): HTMLElement {
  const form = document.createElement('form');
  const heading = document.createElement('h3');
  heading.textContent = 'Create a campaign';
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.placeholder = 'Name';
  nameInput.required = true;
  const slugInput = document.createElement('input');
  slugInput.type = 'text';
  slugInput.placeholder = 'Slug';
  slugInput.required = true;
  const gameSystemInput = document.createElement('input');
  gameSystemInput.type = 'text';
  gameSystemInput.placeholder = 'Game system';
  gameSystemInput.required = true;
  const descriptionInput = document.createElement('textarea');
  descriptionInput.placeholder = 'Description';
  descriptionInput.required = true;
  const secretLabel = document.createElement('label');
  const secretInput = document.createElement('input');
  secretInput.type = 'checkbox';
  secretLabel.append(secretInput, 'Secret');
  const button = document.createElement('button');
  button.type = 'submit';
  button.textContent = 'Create campaign';
  const status = document.createElement('span');
  status.className = 'status-text';
  status.setAttribute('role', 'status');

  form.append(
    heading,
    nameInput,
    slugInput,
    gameSystemInput,
    descriptionInput,
    secretLabel,
    button,
    status,
  );
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    status.textContent = 'Creating…';
    try {
      await createCampaign(tenant.id, {
        name: nameInput.value.trim(),
        slug: slugInput.value.trim(),
        game_system: gameSystemInput.value.trim(),
        description: descriptionInput.value.trim(),
        secret: secretInput.checked,
      });
      form.reset();
      status.textContent = '';
      onCreated();
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });
  return form;
}
