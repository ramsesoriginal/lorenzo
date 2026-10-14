import type { Page } from '@playwright/test';
import { type Api, ok } from '../../../inventory-web/tests/e2e/support/api';
import { API_URL } from '../../../inventory-web/tests/e2e/support/env';
import { addItem, addStatGroup, newRepository, newUser } from './support';

// A one-pixel PNG, for a picture on a row of text.
export const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

export type Level = 'off' | 'showcase' | 'public';

/** A row of text on an entry, Everyone's or GM only. */
export async function textOn(
  api: Api,
  repositoryId: string,
  entityId: string,
  title: string,
  content: string,
  isPublic: boolean,
) {
  return ok(
    api.POST('/tenants/{tenant_id}/entities/{entity_id}/information', {
      params: { path: { tenant_id: repositoryId, entity_id: entityId } },
      body: { title, type: 'note', is_public: isPublic, content, locale: 'en-US' },
    }),
  );
}

/** A picture on a row of text. */
export async function pictureOn(api: Api, repositoryId: string, informationId: string) {
  return ok(
    api.POST('/tenants/{tenant_id}/information/{information_id}/payloads', {
      params: { path: { tenant_id: repositoryId, information_id: informationId } },
      body: { file: 'picture.png' },
      bodySerializer: () => {
        const data = new FormData();

        data.append('file', new Blob([PNG], { type: 'image/png' }), 'picture.png');

        return data;
      },
    }),
  );
}

export async function setStat(
  api: Api,
  repositoryId: string,
  entityId: string,
  definitionId: string,
  value: number,
) {
  await ok(
    api.PUT('/tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}', {
      params: {
        path: { tenant_id: repositoryId, entity_id: entityId, stat_definition_id: definitionId },
      },
      body: { value, acquire_group: false },
    }),
  );
}

export async function feature(api: Api, repositoryId: string, entityIds: string[]) {
  await ok(
    api.PUT('/tenants/{tenant_id}/showcase', {
      params: { path: { tenant_id: repositoryId } },
      body: { entity_ids: entityIds },
    }),
  );
}

export async function setLevel(api: Api, repositoryId: string, preview: Level) {
  await ok(
    api.PATCH('/tenants/{tenant_id}/profile', {
      params: { path: { tenant_id: repositoryId } },
      body: { preview },
    }),
  );
}

export async function goPublic(api: Api, repositoryId: string, summary: string, preview: Level) {
  await ok(
    api.PUT('/tenants/{tenant_id}/public', {
      params: { path: { tenant_id: repositoryId } },
      body: { preview, breaking: false, acknowledge_breaking: true, summary, label: '1.0' },
    }),
  );
}

// What GM only text says, and what its title is: neither may ever be on a page or in an answer a
// reader gets.
export const SECRET_TEXT = 'The pommel hides a gem of great price';
export const SECRET_TITLE = 'GM secret';

/**
 * A repository with three entries: Owlbear (Everyone's text with a picture, a stat value, and GM
 * only text with a picture of its own), Griffin (Everyone's text) and Basilisk (Everyone's text).
 * Nothing is featured and it is private until `goPublic`.
 */
export async function previewWorld(prefix = 'preview') {
  const owner = await newUser(`${prefix}-owner`, ['tenant_creator']);
  const tag = crypto.randomUUID().slice(0, 8);
  const repository = await newRepository(owner.api, `Bestiary ${tag}`);
  const group = await addStatGroup(owner.api, repository.id, 'Physical', ['Weight']);
  const stats = await ok(
    owner.api.GET('/tenants/{tenant_id}/stat-definitions', {
      params: { path: { tenant_id: repository.id } },
    }),
  );
  const weight = stats.items.find((stat) => stat.stat_group_id === group.id);

  if (!weight) throw new Error('The stat was not made.');

  const owlbear = await addItem(owner.api, repository.id, 'Owlbear');
  const griffin = await addItem(owner.api, repository.id, 'Griffin');
  const basilisk = await addItem(owner.api, repository.id, 'Basilisk');

  await setStat(owner.api, repository.id, owlbear.entity_id, weight.id, 4);

  const habits = await textOn(
    owner.api,
    repository.id,
    owlbear.entity_id,
    'Habits',
    'Hunts at night, **loudly**.',
    true,
  );

  await pictureOn(owner.api, repository.id, habits.id);

  const secret = await textOn(
    owner.api,
    repository.id,
    owlbear.entity_id,
    SECRET_TITLE,
    SECRET_TEXT,
    false,
  );
  const secretPicture = await pictureOn(owner.api, repository.id, secret.id);

  await textOn(owner.api, repository.id, griffin.entity_id, 'Lair', 'Nests on high cliffs.', true);
  await textOn(
    owner.api,
    repository.id,
    basilisk.entity_id,
    'Gaze',
    'Turns the unwary to stone.',
    true,
  );

  return {
    owner,
    repository,
    tag,
    owlbear: owlbear.entity_id,
    griffin: griffin.entity_id,
    basilisk: basilisk.entity_id,
    secretPictureId: secretPicture.id,
  };
}

/**
 * Keeps every answer of the API a page receives (and every address it asks for), so a test can say
 * that GM only text came out of none of them. Start it before the page goes anywhere.
 */
export function watchAnswers(page: Page) {
  const urls: string[] = [];
  const bodies: string[] = [];

  page.on('response', async (response) => {
    if (!response.url().startsWith(API_URL)) return;

    urls.push(response.url());
    bodies.push(await response.text().catch(() => ''));
  });

  return { urls, bodies };
}
