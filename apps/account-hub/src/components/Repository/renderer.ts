// One repository in Studio's main area (ADR 0202): its heading, an Overview of what state it is in,
// and People. Showing another replaces it, and an answer that arrives after that is dropped. What
// a person may do follows from their role on it: an Owner changes who works on it, an Owner or an
// Organizer edits it and gives it a picture.

import { displayNameFor, isTenantAdmin } from '../../lib/format';
import { showLorenzoScript } from '../../lib/lorenzoScript';
import { sayError } from '../../lib/statusLine';
import {
  COMMAND_LINE_NOTE,
  canChangePeople,
  LIVE_NOTICE,
  ROLE_MEANINGS,
  ROLES_NOTE,
  repositoryState,
  roleLabel,
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
import { renderTenantEdit } from '../TenantEdit/renderer';

const required = requiredIn('Repository');

export type RepositoryHooks = {
  // Something changed that the list around it shows (a person left, a role changed).
  onChanged(): void;
  // The name or link name was saved.
  onRenamed(updated: TenantOut): void;
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
  const commandLine = required<HTMLElement>(root, '[data-command-line]');
  const people = required<HTMLElement>(root, '[data-people]');
  const roles = required<HTMLElement>(root, '[data-roles]');
  const membershipsSlot = required<HTMLElement>(root, '[data-memberships-slot]');
  const peopleList = required<HTMLElement>(root, '[data-people-list]');

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
  let lastId: string | null = null;

  // The meaning of each role, written once, whoever reads it.
  roles.replaceChildren(
    ...ROLE_MEANINGS.map(({ label, meaning }) => {
      const item = document.createElement('li');
      const term = document.createElement('strong');

      term.textContent = label;
      item.append(term, ` ${meaning}`);

      return item;
    }),
  );
  required<HTMLElement>(root, '[data-roles-note]').textContent = ROLES_NOTE;

  function empty(): void {
    pictureSlot.replaceChildren();
    pictureSlot.hidden = true;
    membershipsSlot.replaceChildren();
    membershipsSlot.hidden = true;
    peopleList.replaceChildren();
    peopleList.hidden = true;
    overview.hidden = true;
    people.hidden = true;
    live.hidden = true;
    showLorenzoScript(description, '');
  }

  function paintOverview(detail: TenantOut): void {
    const current = repositoryState(detail.published_at);

    state.className = current.published ? 'pill pill-success' : 'pill';
    state.textContent = current.label;
    stateExplanation.textContent = current.explanation;
    required<HTMLElement>(live, '[data-live-text]').textContent = LIVE_NOTICE;
    live.hidden = !current.published;
    commandLine.textContent = COMMAND_LINE_NOTE;
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

      return;
    }

    peopleList.replaceChildren(
      ...members.map((member) => {
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

        paintOverview(detail);
        paintPeople(
          repository,
          roster?.items.filter(
            (entry): entry is MembershipRosterEntryOut => entry.kind === 'membership',
          ) ?? [],
        );
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
