// A repository's page on /discover (ADR 0292): its cover, what it says of itself, its latest release,
// what it is built on, and "Copy to a library…", which picks the library and hands over to Shelf's
// copy wizard (ADR 0201), the page that checks a copy first. What a visitor may look at before copying
// is the preview below it (RFC 0038 §5, ADR 0293), which the Owner's switch decides.

import {
  BUILT_ON_NOT_PUBLIC,
  builtOnLines,
  copyTargetLabel,
  copyTargets,
  creditLine,
  discoverHref,
  factsOf,
  hasPrivateUpstream,
  licenceLine,
  publishedByLine,
  REPORT_LABEL,
  releaseGroups,
  releaseHeading,
  reportHref,
} from '../../lib/discover';
import { getStorefront, listPublicDependencies, listPublicReleases } from '../../lib/discoverApi';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import { visitorSource } from '../../lib/previewApi';
import { shelfHref } from '../../lib/shelf';
import { sayError } from '../../lib/statusLine';
import { cloneRoot, requiredIn } from '../../lib/template';
import { listMyTenants } from '../../lib/tenants';
import { createPreview } from '../Preview/renderer';
import { showCover } from './cover';

const required = requiredIn('Storefront');

export type Storefront = {
  // Paints a repository's page. Resolves to false when it is not listed, and shows nothing, for
  // the page to say so.
  show(repositoryId: string, isCurrent: () => boolean): Promise<boolean>;
};

function pair(list: HTMLElement, term: string, value: string): void {
  const dt = document.createElement('dt');
  const dd = document.createElement('dd');

  dt.textContent = term;
  dd.textContent = value;
  list.append(dt, dd);
}

// An external link, as the API stored it (https only, RFC 0038 §2): shown with `rel="nofollow
// noopener"` and opened in its own tab.
function externalLink(url: string, text: string): HTMLAnchorElement {
  const link = document.createElement('a');

  link.href = url;
  link.textContent = text;
  link.rel = 'nofollow noopener';
  link.target = '_blank';

  return link;
}

// `root` is the <Discover /> block, whose templates are used, and `view` the repository's page.
export function createStorefront(root: HTMLElement, view: HTMLElement): Storefront {
  const cover = required<HTMLImageElement>(view, '[data-cover]');
  const name = required<HTMLElement>(view, '[data-name]');
  const summary = required<HTMLElement>(view, '[data-summary]');
  const publishedBy = required<HTMLElement>(view, '[data-published-by]');
  const tags = required<HTMLElement>(view, '[data-tags]');
  const facts = required<HTMLElement>(view, '[data-facts]');
  const description = required<HTMLElement>(view, '[data-description]');
  const licence = required<HTMLElement>(view, '[data-licence]');
  const creditsSection = required<HTMLElement>(view, '[data-credits-section]');
  const credits = required<HTMLElement>(view, '[data-credits]');
  const reportLine = required<HTMLElement>(view, '[data-report-line]');
  const report = required<HTMLAnchorElement>(view, '[data-report]');
  const partError = required<HTMLElement>(view, '[data-part-error]');
  const releaseSection = required<HTMLElement>(view, '[data-release-section]');
  const release = required<HTMLElement>(view, '[data-release]');
  const releaseNotes = required<HTMLElement>(view, '[data-release-notes]');
  const othersSection = required<HTMLDetailsElement>(view, '[data-others-section]');
  const othersTitle = required<HTMLElement>(view, '[data-others-title]');
  const others = required<HTMLElement>(view, '[data-others]');
  const builtOnSection = required<HTMLElement>(view, '[data-built-on-section]');
  const builtOn = required<HTMLElement>(view, '[data-built-on]');
  const builtOnNone = required<HTMLElement>(view, '[data-built-on-none]');
  const builtOnNote = required<HTMLElement>(view, '[data-built-on-note]');
  // Looking inside, as a visitor: the Owner's switch says how much (ADR 0293).
  const preview = createPreview(view, { list: true });

  const copy = {
    open: required<HTMLButtonElement>(view, '[data-copy-open]'),
    panel: required<HTMLElement>(view, '[data-copy]'),
    error: required<HTMLElement>(view, '[data-copy-error]'),
    none: required<HTMLElement>(view, '[data-copy-none]'),
    choose: required<HTMLElement>(view, '[data-copy-choose]'),
    library: required<HTMLSelectElement>(view, '[data-copy-library]'),
    go: required<HTMLAnchorElement>(view, '[data-copy-go]'),
  };

  // The repository on show, for the copy button.
  let shown: string | null = null;
  let targetsLoaded = false;

  function closeCopy(): void {
    copy.panel.hidden = true;
    copy.open.setAttribute('aria-expanded', 'false');
    copy.error.hidden = true;
    targetsLoaded = false;
  }

  function aim(): void {
    if (shown === null) return;

    const slug = copy.library.selectedOptions[0]?.dataset.slug;

    if (slug) copy.go.href = shelfHref(slug, shown, 'new');
  }

  copy.library.addEventListener('change', aim);

  // The libraries to copy into are read when "Copy to a library…" is first pressed, not for
  // every page.
  copy.open.addEventListener('click', () => {
    const opening = copy.panel.hidden;

    copy.panel.hidden = !opening;
    copy.open.setAttribute('aria-expanded', String(opening));

    if (!opening || targetsLoaded) return;

    targetsLoaded = true;
    copy.error.hidden = true;

    void (async () => {
      try {
        const targets = copyTargets((await listMyTenants()).items);

        copy.none.hidden = targets.length > 0;
        copy.choose.hidden = targets.length === 0;
        copy.library.replaceChildren(
          ...targets.map((target) => {
            const option = document.createElement('option');

            option.value = target.id;
            option.dataset.slug = target.slug;
            option.textContent = copyTargetLabel(target);

            return option;
          }),
        );
        aim();
      } catch (cause) {
        targetsLoaded = false;
        sayError(copy.error, cause);
      }
    })();
  });

  function paintReleases(
    releases: Awaited<ReturnType<typeof listPublicReleases>>,
    paintTurn: () => boolean,
  ): void {
    if (!paintTurn()) return;

    const groups = releaseGroups(releases);

    releaseSection.hidden = groups.latest === null;
    others.replaceChildren();
    othersSection.hidden = groups.others.length === 0;
    othersSection.open = false;
    releaseNotes.hidden = true;

    if (!groups.latest) return;

    release.textContent = releaseHeading(groups.latest);

    const notes = groups.latest.notes?.trim() ?? '';

    releaseNotes.textContent = notes;
    releaseNotes.hidden = notes === '';

    othersTitle.textContent = groups.othersHeading;
    others.replaceChildren(
      ...groups.others.map((other) => {
        const item = cloneRoot(root, '[data-other-release-template]');
        const text = other.notes?.trim() ?? '';
        const notesLine = required<HTMLElement>(item, '[data-notes]');

        required<HTMLElement>(item, '[data-heading]').textContent = releaseHeading(other);
        notesLine.textContent = text;
        notesLine.hidden = text === '';

        return item;
      }),
    );
  }

  function paintBuiltOn(
    dependencies: Awaited<ReturnType<typeof listPublicDependencies>>,
    paintTurn: () => boolean,
  ): void {
    if (!paintTurn()) return;

    const lines = builtOnLines(dependencies);

    builtOnSection.hidden = false;
    builtOn.replaceChildren(
      ...lines.map((line) => {
        const item = cloneRoot(root, '[data-built-on-template]');
        const link = required<HTMLAnchorElement>(item, '[data-name]');
        const note = required<HTMLElement>(item, '[data-note]');

        if (line.href) {
          link.href = line.href;
          link.textContent = line.name;
        } else {
          // Nothing to open: its page is not there.
          const plain = document.createElement('span');

          plain.textContent = line.name;
          link.replaceWith(plain);
        }

        note.textContent = line.note ?? '';
        note.hidden = line.note === null;

        return item;
      }),
    );
    builtOnNone.hidden = lines.length > 0;
    builtOnNote.textContent = BUILT_ON_NOT_PUBLIC;
    builtOnNote.hidden = !hasPrivateUpstream(dependencies);
  }

  return {
    async show(repositoryId, isCurrent) {
      const storefront = await getStorefront(repositoryId);

      if (!isCurrent()) return true;
      if (!storefront) return false;

      const { item, profile } = storefront;

      shown = item.id;
      closeCopy();
      copy.go.removeAttribute('href');
      partError.hidden = true;
      releaseSection.hidden = true;
      builtOnSection.hidden = true;
      preview.hide();

      showCover(cover, null, item, isCurrent);
      name.textContent = item.name;
      summary.textContent = item.summary;
      summary.hidden = item.summary === '';

      const publisher = publishedByLine(item.publishers);

      publishedBy.textContent = publisher ?? '';
      publishedBy.hidden = publisher === null;

      // A plain link, and only where the deployment says where a report goes (ADR 0299).
      const mailto = reportHref(storefront.report_mailto);

      report.textContent = REPORT_LABEL;
      if (mailto) report.href = mailto;
      else report.removeAttribute('href');
      reportLine.hidden = mailto === null;

      tags.replaceChildren(
        ...profile.tags.map((tag) => {
          const li = cloneRoot(root, '[data-tag-link-template]');
          const link = required<HTMLAnchorElement>(li, '[data-text]');

          link.textContent = tag;
          link.href = discoverHref({ tag });

          return li;
        }),
      );
      tags.hidden = profile.tags.length === 0;

      facts.replaceChildren();

      for (const fact of factsOf(item)) pair(facts, fact.term, fact.value);

      facts.hidden = facts.children.length === 0;

      showLorenzoScript(description, storefront.description);

      const licenceText = licenceLine(profile.licence);

      licence.replaceChildren(
        licenceText.url ? externalLink(licenceText.url, licenceText.text) : licenceText.text,
      );

      credits.replaceChildren(
        ...profile.credits.map((credit) => {
          const line = creditLine(credit);
          const li = cloneRoot(root, '[data-credit-template]');
          const who = required<HTMLElement>(li, '[data-name]');

          who.replaceChildren(line.url ? externalLink(line.url, line.name) : line.name);
          required<HTMLElement>(li, '[data-role]').textContent = line.role ?? '';

          return li;
        }),
      );
      creditsSection.hidden = profile.credits.length === 0;

      // Looking inside is read at the same time, with its own failure: the page does not wait for it.
      void preview.show(visitorSource(item.id), 'visitor', isCurrent);

      // Releases and what it is built on come from routes of their own, and either may fail
      // without taking the page with it.
      const [releases, dependencies] = await Promise.allSettled([
        listPublicReleases(item.id),
        listPublicDependencies(item.id),
      ]);

      if (!isCurrent()) return true;

      if (releases.status === 'fulfilled') paintReleases(releases.value, isCurrent);
      if (dependencies.status === 'fulfilled') paintBuiltOn(dependencies.value, isCurrent);

      const failed = [releases, dependencies].find((result) => result.status === 'rejected');

      if (failed?.status === 'rejected') sayError(partError, failed.reason);

      return true;
    },
  };
}
