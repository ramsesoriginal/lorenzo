// The LIVE banner (RFC 0039 B3): says, wherever a published repository is edited, that the
// libraries which copied it see the edits. Hiding it lasts until the page is loaded again, since
// it is a notice about what editing does, not a setting.
//
// "Edited since release X" for a public repository waits for the release ledger (RFC 0037); until
// then a published repository is the only case there is.

export class LiveBanner {
  private published = false;
  private hidden = false;

  constructor(private readonly root: HTMLElement) {
    this.draw();
  }

  /** Whether the open repository is published. */
  set(published: boolean) {
    this.published = published;
    this.draw();
  }

  private draw() {
    const show = this.published && !this.hidden;
    this.root.hidden = !show;
    this.root.replaceChildren();
    if (!show) return;
    const pill = document.createElement('span');
    pill.className = 'pill';
    pill.textContent = 'Live';
    const text = document.createElement('span');
    text.textContent =
      'Libraries that copied this repository see your edits when they next check for updates.';
    const hide = document.createElement('button');
    hide.type = 'button';
    hide.className = 'btn';
    hide.textContent = 'Hide';
    hide.addEventListener('click', () => {
      this.hidden = true;
      this.draw();
    });
    this.root.append(pill, text, hide);
  }
}
