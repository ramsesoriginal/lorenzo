// A tenant's or a campaign's own picture widget (ADR 0085) - reused as-is
// for both call sites, the way userPicker.ts (ADR 0074) is reused across
// pages. Unlike /me/picture (MeOut.picture_url, always resolvable via a
// Gravatar fallback), tenants/campaigns have no server-provided
// picture_url field and GET .../picture has no fallback at all - a 404
// when nothing's uploaded (ADR 0056) - so the <img> needs its own onerror
// handler rather than trusting a bare src to always resolve.

import { createStatusSpan } from './dom';

export function renderPictureUpload(
  url: string,
  onUpload: (file: File) => Promise<void>,
  onDelete: () => Promise<void>,
): HTMLElement {
  const container = document.createElement('span');
  container.className = 'picture-upload';

  const img = document.createElement('img');
  img.src = url;
  img.alt = '';
  img.width = 48;
  img.height = 48;
  img.addEventListener('error', () => {
    img.hidden = true;
  });
  img.addEventListener('load', () => {
    img.hidden = false;
  });

  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = 'image/*';

  const deleteButton = document.createElement('button');
  deleteButton.type = 'button';
  deleteButton.textContent = 'Remove picture';

  const status = createStatusSpan();

  container.append(img, fileInput, deleteButton, status);

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    status.textContent = 'Uploading…';
    try {
      await onUpload(file);
      img.src = url;
      status.textContent = '';
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    } finally {
      fileInput.value = '';
    }
  });

  deleteButton.addEventListener('click', async () => {
    status.textContent = 'Removing…';
    try {
      await onDelete();
      img.hidden = true;
      status.textContent = '';
    } catch (e) {
      status.textContent = e instanceof Error ? e.message : String(e);
    }
  });

  return container;
}
