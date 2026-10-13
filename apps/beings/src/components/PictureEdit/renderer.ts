// The being's main picture (ADR 0237, 0272): choose a file and use it, or remove the one it has.
// The same four types and 2 MB limit as the API's; it says so before uploading rather than after.

import { client, unwrap } from '../../lib/api';
import { errorMessage } from '../../lib/errorMessage';
import { say } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Picture edit');

const TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
const MAX_BYTES = 2_000_000;

/** Why this file can't be the picture, or null if it can. */
export function pictureProblem(file: { type: string; size: number }): string | null {
  if (!TYPES.includes(file.type)) return "That file type won't work. Use a PNG, JPEG, WebP or GIF.";
  if (file.size > MAX_BYTES) return 'That picture is over 2 MB. Choose a smaller one.';
  return null;
}

export type PictureEditOptions = {
  root: HTMLElement;
  tenantId: string;
  // After the picture was set or removed.
  onChanged: () => void;
};

export type RenderedPictureEdit = {
  load(entityId: string, hasPicture: boolean): void;
};

export function renderPictureEdit(options: PictureEditOptions): RenderedPictureEdit {
  const { root, tenantId } = options;
  const file = required<HTMLInputElement>(root, '[data-file]');
  const upload = required<HTMLButtonElement>(root, '[data-upload]');
  const remove = required<HTMLButtonElement>(root, '[data-remove]');
  const status = required<HTMLElement>(root, '[data-status]');

  let entityId: string | null = null;

  async function run(work: () => Promise<void>, doing: string, done: string) {
    upload.disabled = true;
    remove.disabled = true;
    say(status, doing);

    try {
      await work();
      say(status, done);
      options.onChanged();
    } catch (error) {
      say(status, errorMessage(error), true);
    } finally {
      upload.disabled = false;
      remove.disabled = false;
    }
  }

  upload.addEventListener('click', () => {
    const chosen = file.files?.[0];

    if (!entityId || !chosen) {
      say(status, 'Choose a picture first.', true);
      return;
    }

    const problem = pictureProblem(chosen);

    if (problem) {
      say(status, problem, true);
      return;
    }

    const id = entityId;

    void run(
      async () => {
        await unwrap(
          await client.PUT('/tenants/{tenant_id}/entities/{entity_id}/picture', {
            params: { path: { tenant_id: tenantId, entity_id: id } },
            // OpenAPI types a file as a string; the serializer sends the real File as multipart, and
            // the browser adds the boundary to the content type.
            body: { file: chosen.name },
            bodySerializer: () => {
              const data = new FormData();

              data.append('file', chosen);

              return data;
            },
          }),
        );
        file.value = '';
      },
      'Uploading…',
      'Saved.',
    );
  });

  remove.addEventListener('click', () => {
    if (!entityId) return;

    const id = entityId;

    void run(
      async () => {
        await unwrap(
          await client.DELETE('/tenants/{tenant_id}/entities/{entity_id}/picture', {
            params: { path: { tenant_id: tenantId, entity_id: id } },
          }),
        );
      },
      'Removing…',
      'Removed.',
    );
  });

  return {
    load(id, hasPicture) {
      entityId = id;
      root.hidden = false;
      remove.hidden = !hasPicture;
    },
  };
}
