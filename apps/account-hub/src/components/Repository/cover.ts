// A repository's cover on its Profile tab (RFC 0038 §2, ADR 0385): the cover as it is now, a picture
// chosen and looked at before it is uploaded, Replace, and Remove after a confirm. Every member sees the
// cover; only an Owner has the buttons. It has its own buttons, and is not part of the form's Save.
//
// Not the shared PictureUpload (ADR 0085): that one uploads the moment a file is picked, is a square
// of 128 pixels, removes without asking and has nothing to say for no picture, and the cover is a wide
// strip that is looked at first and has Discover's own stand-in to explain. What they share is what is
// shared: the types and size the API takes (lib/profilePicture.ts), the status line and the picture
// fetched with the token (lib/pictureFetch.ts). The cover is not counted by the quotas (ADR 0298), so
// nothing here says anything of them.

import { avatarInitial } from '../../lib/format';
import {
  COVER_CANCEL,
  COVER_CHOOSE,
  COVER_HEADING,
  COVER_HELP,
  COVER_REMOVE,
  COVER_REMOVE_CONFIRM,
  COVER_REMOVED,
  COVER_REMOVING,
  COVER_REPLACE,
  COVER_STAGED,
  COVER_UPLOAD,
  COVER_UPLOADED,
  COVER_UPLOADING,
  NO_COVER,
  NO_COVER_INSTEAD,
} from '../../lib/profileEditor';
import { PICTURE_ACCEPT, pictureProblem } from '../../lib/profilePicture';
import { deleteRepositoryCover, ownCoverUrl, uploadRepositoryCover } from '../../lib/repositories';
import { say, sayError } from '../../lib/statusLine';
import { requiredIn } from '../../lib/template';
import type { TenantSummaryOut } from '../../lib/types';

const required = requiredIn('Repository');

export type CoverControls = {
  clear(): void;
  // Shows the cover of a repository; `owner` says whether the buttons are there.
  paint(repository: TenantSummaryOut, hasCover: boolean, owner: boolean): Promise<void>;
  // Moves the cursor to where the cover is chosen.
  focus(): void;
};

// `root` is the <Repository /> article. `hooks.shown` is told what the cover is whenever it is drawn, with
// the picture as a blob address (null for none), for what shows it elsewhere; `hooks.changed` when an
// upload or a removal went through.
export function createCoverControls(
  root: HTMLElement,
  hooks: { shown(hasCover: boolean, url: string | null): void; changed(): void },
): CoverControls {
  const card = required<HTMLElement>(root, '[data-cover-card]');
  const picture = required<HTMLImageElement>(card, '[data-cover-picture]');
  const none = required<HTMLElement>(card, '[data-cover-none]');
  const initial = required<HTMLElement>(card, '[data-cover-initial]');
  const staged = required<HTMLElement>(card, '[data-cover-staged]');
  const stagedPicture = required<HTMLImageElement>(card, '[data-cover-staged-picture]');
  const upload = required<HTMLButtonElement>(card, '[data-cover-upload]');
  const cancel = required<HTMLButtonElement>(card, '[data-cover-cancel]');
  const help = required<HTMLElement>(card, '[data-cover-help]');
  const buttons = required<HTMLElement>(card, '[data-cover-buttons]');
  const choose = required<HTMLButtonElement>(card, '[data-cover-choose]');
  const remove = required<HTMLButtonElement>(card, '[data-cover-remove]');
  const file = required<HTMLInputElement>(card, '[data-cover-file]');
  const status = required<HTMLElement>(card, '[data-cover-status]');

  required<HTMLElement>(card, '[data-cover-heading]').textContent = COVER_HEADING;
  required<HTMLElement>(card, '[data-cover-none-title]').textContent = NO_COVER;
  required<HTMLElement>(card, '[data-cover-none-text]').textContent = NO_COVER_INSTEAD;
  required<HTMLElement>(card, '[data-cover-staged-text]').textContent = COVER_STAGED;
  help.textContent = COVER_HELP;
  upload.textContent = COVER_UPLOAD;
  cancel.textContent = COVER_CANCEL;
  remove.textContent = COVER_REMOVE;
  file.accept = PICTURE_ACCEPT;

  let shown: TenantSummaryOut | null = null;
  let hasCover = false;
  let shownUrl: string | null = null;
  let chosen: File | null = null;
  let stagedUrl: string | null = null;
  // Whatever was asked last paints.
  let turn = 0;

  function forgetUrl(): void {
    if (shownUrl) URL.revokeObjectURL(shownUrl);

    shownUrl = null;
  }

  function unstage(): void {
    if (stagedUrl) URL.revokeObjectURL(stagedUrl);

    stagedUrl = null;
    chosen = null;
    file.value = '';
    staged.hidden = true;
    stagedPicture.removeAttribute('src');
  }

  function paintState(): void {
    choose.textContent = hasCover ? COVER_REPLACE : COVER_CHOOSE;
    remove.hidden = !hasCover;
    none.hidden = hasCover;
    picture.hidden = !hasCover || shownUrl === null;
  }

  // The cover as the API has it now, fetched with the token.
  async function showCurrent(repository: TenantSummaryOut): Promise<void> {
    const mine = ++turn;

    forgetUrl();
    picture.removeAttribute('src');
    paintState();

    if (!hasCover) {
      hooks.shown(false, null);

      return;
    }

    try {
      const url = await ownCoverUrl(repository.id);

      if (mine !== turn || shown !== repository) {
        URL.revokeObjectURL(url);

        return;
      }

      shownUrl = url;
      picture.src = url;
      paintState();
      hooks.shown(true, url);
    } catch {
      // A cover that cannot be read is left out, as in Discover: the stand-in stays.
      if (mine === turn) {
        shownUrl = null;
        hooks.shown(true, null);
        paintState();
      }
    }
  }

  choose.addEventListener('click', () => file.click());

  file.addEventListener('change', () => {
    const picked = file.files?.[0];

    if (!picked) return;

    // Told here what the API would only refuse after the upload.
    const problem = pictureProblem(picked);

    if (problem) {
      say(status, problem, true);
      file.value = '';

      return;
    }

    unstage();
    chosen = picked;
    stagedUrl = URL.createObjectURL(picked);
    stagedPicture.src = stagedUrl;
    staged.hidden = false;
    say(status, '');
  });

  cancel.addEventListener('click', () => {
    unstage();
    say(status, '');
    choose.focus();
  });

  upload.addEventListener('click', () => {
    const repository = shown;
    const picked = chosen;

    if (!repository || !picked) return;

    upload.disabled = true;
    say(status, COVER_UPLOADING);

    void (async () => {
      try {
        await uploadRepositoryCover(repository.id, picked);

        if (shown !== repository) return;

        unstage();
        hasCover = true;
        await showCurrent(repository);
        say(status, COVER_UPLOADED);
        hooks.changed();
      } catch (cause) {
        // The API's words, with the picture still staged: choose another, or cancel.
        sayError(status, cause);
      } finally {
        upload.disabled = false;
      }
    })();
  });

  remove.addEventListener('click', () => {
    const repository = shown;

    if (!repository || !window.confirm(COVER_REMOVE_CONFIRM)) return;

    remove.disabled = true;
    say(status, COVER_REMOVING);

    void (async () => {
      try {
        await deleteRepositoryCover(repository.id);

        if (shown !== repository) return;

        hasCover = false;
        await showCurrent(repository);
        say(status, COVER_REMOVED);
        hooks.changed();
      } catch (cause) {
        sayError(status, cause);
      } finally {
        remove.disabled = false;
      }
    })();
  });

  return {
    clear() {
      shown = null;
      turn++;
      forgetUrl();
      unstage();
      picture.removeAttribute('src');
      picture.hidden = true;
      none.hidden = true;
      buttons.hidden = true;
      help.hidden = true;
      say(status, '');
    },

    async paint(repository, cover, owner) {
      shown = repository;
      hasCover = cover;
      initial.textContent = avatarInitial(repository.name);
      buttons.hidden = !owner;
      help.hidden = !owner;
      unstage();
      say(status, '');
      await showCurrent(repository);
    },

    focus() {
      card.focus();
      (buttons.hidden ? card : choose).focus();
    },
  };
}
