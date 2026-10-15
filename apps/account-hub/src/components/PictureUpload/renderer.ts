// A tenant's or a campaign's own picture widget (ADR 0085) - reused as-is for both call sites,
// the way the user picker (ADR 0074) is reused across pages. Unlike /me/picture
// (MeOut.picture_url, always resolvable via a Gravatar fallback), tenants/campaigns have no
// server-provided picture_url field and GET .../picture has no fallback at all - a 404 when
// nothing's uploaded (ADR 0056) - so the <img> needs its own onerror handler rather than
// trusting a bare src to always resolve. A picture that wants the token (a repository's, ADR 0300)
// is given as a function that fetches it and answers a `blob:` address; one that does not is given
// as its address.

import { PICTURE_ACCEPT, pictureProblem } from '../../lib/profilePicture';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';

const required = requiredIn('Picture upload');

export type PictureUploadOptions = {
  url: string | (() => Promise<string>);
  onUpload(file: File): Promise<void>;
  onDelete(): Promise<void>;
};

// `root` is the <PictureUpload /> block.
export function renderPictureUpload(root: HTMLElement, options: PictureUploadOptions): void {
  const { url, onUpload, onDelete } = options;
  const img = required<HTMLImageElement>(root, '[data-picture]');
  const fileInput = required<HTMLInputElement>(root, '[data-file]');
  const removeButton = required<HTMLButtonElement>(root, '[data-remove]');
  const status = required<HTMLElement>(root, '[data-status]');

  // The picture sits at one address whatever it is, so after a change the browser is asked for it
  // afresh, or it would go on showing the one it already has.
  let version = '';
  let turn = 0;
  // Shown from its address, or fetched first; whatever was asked last wins, and one that does not
  // come (no picture, or none this person may see) is left out like a broken one.
  const show = () => {
    if (typeof url === 'string') {
      img.src = `${url}${version}`;

      return;
    }

    const mine = ++turn;

    url()
      .then((src) => {
        if (mine === turn) img.src = src;
      })
      .catch(() => {
        if (mine === turn) img.hidden = true;
      });
  };

  // Only what the API takes, so a picker doesn't offer an SVG.
  fileInput.accept = PICTURE_ACCEPT;

  img.addEventListener('error', () => {
    img.hidden = true;
  });
  img.addEventListener('load', () => {
    img.hidden = false;
  });
  show();

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files?.[0];

    if (!file) return;

    // Told here what the API would only refuse after the upload.
    const problem = pictureProblem(file);

    if (problem) {
      say(status, problem, true);
      fileInput.value = '';

      return;
    }

    say(status, 'Uploading…');

    try {
      await onUpload(file);
      version = `?v=${Date.now()}`;
      show();
      say(status, 'Updated.');
    } catch (cause) {
      sayError(status, cause);
    } finally {
      fileInput.value = '';
    }
  });

  removeButton.addEventListener('click', async () => {
    say(status, 'Removing…');

    try {
      await onDelete();
      version = `?v=${Date.now()}`;
      img.hidden = true;
      say(status, 'Removed.');
    } catch (cause) {
      sayError(status, cause);
    }
  });
}
