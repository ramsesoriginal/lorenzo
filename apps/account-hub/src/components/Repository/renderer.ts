// One repository in Studio's main area (ADR 0202): its heading, an Overview of what state it is in,
// and People. Showing another replaces it, and an answer that arrives after that is dropped. What
// a person may do follows from their role on it: an Owner changes who works on it, an Owner or an
// Organizer edits it and gives it a picture.

import { distinctPeople } from '../../lib/deleting';
import { displayNameFor, isTenantAdmin } from '../../lib/format';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import { sayError } from '../../lib/statusLine';
import {
  canChangePeople,
  LIVE_NOTICE,
  repositoryState,
  roleLabel,
  roleMeanings,
} from '../../lib/studio';
import { bindTabs } from '../../lib/tabs';
import { cloneRoot, requiredIn } from '../../lib/template';
import {
  deleteTenantPicture,
  getTenant,
  listTenantRoster,
  tenantPictureUrl,
  uploadTenantPicture,
} from '../../lib/tenants';
import type { MembershipRosterEntryOut, TenantOut, TenantSummaryOut } from '../../lib/types';
import { renderMembershipAdmin } from '../MembershipAdmin/renderer';
import { renderPictureUpload } from '../PictureUpload/renderer';
import { bindLeaveTenant } from '../Tenant/leaveTenant';
import { renderTenantDelete } from '../TenantDelete/renderer';
import { renderTenantEdit } from '../TenantEdit/renderer';
import { renderTenantInviteLinks } from '../TenantInviteLinks/renderer';
import { createPublishControls } from './publish';
import { createActivity, createBuiltOn, createReleases, createUsing } from './sections';
import { createShowcaseControls } from './showcase';
import { createViewAs } from './viewAs';
import { createVisibilityControls } from './visibility';

const required = requiredIn('Repository');

export type RepositoryHooks = {
  // Something changed that the list around it shows (a person left, a role changed).
  onChanged(): void;
  // The name or link name was saved.
  onRenamed(updated: TenantOut): void;
  // It was deleted (ADR 0267): the message to show where the page goes next.
  onDeleted(message: string, repository: TenantSummaryOut): void;
  // Whether the account may create libraries, which making (and removing) a Test library needs.
  mayCreate: boolean;
};

export type RenderedRepository = {
  show(repository: TenantSummaryOut): Promise<void>;
  hide(): void;
};

// `root` is the <Repository /> article.
export function renderRepository(
  root: HTMLElement,
  userId: string,
  hooks: RepositoryHooks,
): RenderedRepository {
  const name = required<HTMLElement>(root, '[data-name]');
  const slug = required<HTMLElement>(root, '[data-slug]');
  const role = required<HTMLElement>(root, '[data-role]');
  const description = required<HTMLElement>(root, '[data-tenant-description]');
  const pictureSlot = required<HTMLElement>(root, '[data-picture-slot]');
  const loading = required<HTMLElement>(root, '[data-loading]');
  const error = required<HTMLElement>(root, '[data-error]');
  const overview = required<HTMLElement>(root, '[data-overview]');
  const state = required<HTMLElement>(root, '[data-state]');
  const stateExplanation = required<HTMLElement>(root, '[data-state-explanation]');
  const live = required<HTMLElement>(root, '[data-live]');
  const people = required<HTMLElement>(root, '[data-people]');
  const roles = required<HTMLElement>(root, '[data-roles]');
  const membershipsSlot = required<HTMLElement>(root, '[data-memberships-slot]');
  const peopleList = required<HTMLElement>(root, '[data-people-list]');
  const linksSlot = required<HTMLElement>(root, '[data-links-slot]');
  const deleteSlot = required<HTMLElement>(root, '[data-delete-slot]');

  // Only the newest `show` paints.
  let latest = 0;

  const rename = (updated: TenantOut) => {
    name.textContent = updated.name;
    slug.textContent = updated.slug;
    showLorenzoScript(description, updated.description);
    hooks.onRenamed(updated);
  };
  const edit = renderTenantEdit(required<HTMLElement>(root, '[data-tenant-edit]'), rename);
  const leave = bindLeaveTenant(
    required<HTMLElement>(root, '[data-leave]'),
    userId,
    hooks.onChanged,
  );
  const tabs = bindTabs(required<HTMLElement>(root, '[data-tabs]'));
  // An invitation made or stopped changes only what the Libraries using it tab shows.
  // A publish or an unpublish changes what the page shows, so it is read again.
  const publishControls = createPublishControls(root, hooks.onChanged);
  // Private or public is a change of the same kind: the page reads the repository again after it.
  const visibility = createVisibilityControls(root, hooks.onChanged, (visibility) =>
    publishControls.markPublic(visibility === 'public'),
  );
  // What people can look at, and the entries featured: the Owner's, beside the switch.
  const showcase = createShowcaseControls(root);
  const viewAs = createViewAs(root, hooks.mayCreate);
  const releases = createReleases(root);
  const using = createUsing(root, () => undefined);
  const builtOn = createBuiltOn(root);
  const activity = createActivity(root);
  let lastId: string | null = null;

  // The meaning of each role, for whoever reads the people and cannot change them. An Owner's panel
  // says it itself.
  function showRoleMeanings(): void {
    roles.replaceChildren(
      ...roleMeanings('repository').map(({ label, meaning }) => {
        const item = document.createElement('li');
        const term = document.createElement('strong');

        term.textContent = label;
        item.append(term, ` ${meaning}`);

        return item;
      }),
    );
  }

  function empty(): void {
    pictureSlot.replaceChildren();
    pictureSlot.hidden = true;
    membershipsSlot.replaceChildren();
    membershipsSlot.hidden = true;
    linksSlot.replaceChildren();
    linksSlot.hidden = true;
    showRoleMeanings();
    peopleList.replaceChildren();
    peopleList.hidden = true;
    deleteSlot.replaceChildren();
    deleteSlot.hidden = true;
    overview.hidden = true;
    people.hidden = true;
    live.hidden = true;
    publishControls.clear();
    visibility.clear();
    showcase.clear();
    viewAs.clear();
    releases.clear();
    using.clear();
    builtOn.clear();
    activity.clear();
    showLorenzoScript(description, '');
  }

  function paintOverview(repository: TenantSummaryOut, detail: TenantOut): void {
    const current = repositoryState(detail.published_at);

    state.className = current.published ? 'pill pill-success' : 'pill';
    state.textContent = current.label;
    stateExplanation.textContent = current.explanation;
    required<HTMLElement>(live, '[data-live-text]').textContent = LIVE_NOTICE;
    live.hidden = !current.published;
    publishControls.paint(repository, current.published);
    void viewAs.paint(repository, current.published);
    void visibility.paint(repository);
    void showcase.paint(repository);
    overview.hidden = false;
  }

  function paintPeople(repository: TenantSummaryOut, members: MembershipRosterEntryOut[]): void {
    people.hidden = false;

    if (canChangePeople(repository.role)) {
      // The Owner's panel lists them with the controls to change a role or remove someone.
      const panel = cloneRoot(root, '[data-membership-admin-template]');

      renderMembershipAdmin(panel, repository, members, hooks.onChanged, {
        heading: 'Everyone with a role',
        inviteLabel: 'Add a person, as:',
      });
      membershipsSlot.replaceChildren(panel);
      membershipsSlot.hidden = false;

      // The panel says what each role allows, so the list of them is not shown twice.
      roles.replaceChildren();

      const links = cloneRoot(root, '[data-tenant-invite-links-template]');

      renderTenantInviteLinks(links, repository, 'role');
      linksSlot.replaceChildren(links);
      linksSlot.hidden = false;

      return;
    }

    // An Author reads no roster (the API gives it to the people who run the repository): they see
    // their own role, and what each role allows is above.
    const shown =
      members.length > 0
        ? members
        : [{ display_name: 'You', nickname: null, user_id: userId, role: repository.role }];

    peopleList.replaceChildren(
      ...shown.map((member) => {
        const item = cloneRoot(root, '[data-person-template]');

        required<HTMLElement>(item, '[data-name]').textContent = displayNameFor(member);
        required<HTMLElement>(item, '[data-person-role]').textContent = roleLabel(member.role);

        return item;
      }),
    );
    peopleList.hidden = false;
  }

  return {
    async show(repository) {
      const turn = ++latest;

      root.hidden = false;
      name.textContent = repository.name;
      slug.textContent = repository.slug;
      role.textContent = roleLabel(repository.role);
      error.hidden = true;
      empty();
      edit.show(repository);
      leave.show(repository);

      for (const noun of root.querySelectorAll<HTMLElement>('[data-noun]')) {
        noun.textContent = 'repository';
      }

      // Another repository starts on its first tab; the same one, loaded again after a change, stays.
      if (repository.id !== lastId) tabs.reset();

      lastId = repository.id;
      loading.hidden = false;

      try {
        const [{ tenant: detail }, roster] = await Promise.all([
          getTenant(repository.id),
          // Whoever works on it can read who else does; changing it is the Owner's.
          isTenantAdmin(repository) ? listTenantRoster(repository.id) : null,
        ]);

        if (turn !== latest) return;

        showLorenzoScript(description, detail.description);

        if (isTenantAdmin(repository)) {
          const picture = cloneRoot(root, '[data-picture-upload-template]');

          renderPictureUpload(picture, {
            url: tenantPictureUrl(repository.id),
            onUpload: (file) => uploadTenantPicture(repository.id, file),
            onDelete: () => deleteTenantPicture(repository.id),
          });
          pictureSlot.replaceChildren(picture);
          pictureSlot.hidden = false;
        }

        paintOverview(repository, detail);

        if (isTenantAdmin(repository)) {
          const removal = cloneRoot(root, '[data-tenant-delete-template]');

          renderTenantDelete(removal, hooks.onDeleted).show(repository, {
            accountMayDelete: hooks.mayCreate,
            known: { campaigns: null, people: roster ? distinctPeople(roster.items) : null },
          });
          deleteSlot.replaceChildren(removal);
          deleteSlot.hidden = false;
        }

        paintPeople(
          repository,
          roster?.items.filter(
            (entry): entry is MembershipRosterEntryOut => entry.kind === 'membership',
          ) ?? [],
        );

        // The tabs about its place among others each read their own and say their own failure.
        const current = () => turn === latest;

        await Promise.all([
          releases.load(repository, current, roster?.items ?? null),
          // Who copied it and the activity are the people who run it's to read; an Author's tabs are
          // the ones the API serves them.
          isTenantAdmin(repository) ? using.load(repository, current, null) : undefined,
          builtOn.load(repository, current, null),
          isTenantAdmin(repository)
            ? activity.load(repository, current, roster?.items ?? null)
            : undefined,
        ]);
      } catch (cause) {
        if (turn !== latest) return;

        sayError(error, cause);
      } finally {
        if (turn === latest) {
          loading.hidden = true;
          tabs.refresh();
        }
      }
    },

    hide() {
      latest++;
      root.hidden = true;
    },
  };
}
