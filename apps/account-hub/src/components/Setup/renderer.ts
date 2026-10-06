// /setup (ADR 0180): the form, then the chain of calls it asks for, then the result with its links.
// One phase of <Setup /> shows at a time. The logic is lib/setup.ts's; each phase has a module here.

import { expiresAtFor, type GmExpiryPresetId } from '../../lib/inviteLink';
import { createInvite } from '../../lib/invites';
import type { SetupApi } from '../../lib/setup';
import { requiredIn } from '../../lib/template';
import { createCampaign, createTenant, grantCampaignGm } from '../../lib/tenants';
import { bindSetupForm } from './form';
import { runProgress } from './progress';
import { showResult } from './result';

const required = requiredIn('Setup');

// The real calls behind SetupApi: the ones /tenants makes, nothing new. Expiry is worked out when a
// link is made, so a retry an hour later is not already short of what the person chose.
function realApi(playerExpiry: () => string, gmExpiry: () => string): SetupApi {
  return {
    createLibrary: (name) => createTenant({ name }),
    createCampaign: (libraryId, campaign) =>
      createCampaign(libraryId, {
        name: campaign.name,
        slug: campaign.slug,
        game_system: campaign.gameSystem,
        description: '',
        secret: false,
      }),
    grantGm: grantCampaignGm,
    createInvite: async (libraryId, campaignId, role) => {
      const invite = await createInvite(libraryId, campaignId, {
        role,
        expires_at: expiresAtFor(
          (role === 'gm' ? gmExpiry() : playerExpiry()) as GmExpiryPresetId,
          new Date(),
        ),
      });

      return { token: invite.token };
    },
  };
}

// `root` is the <Setup /> block; `meId` is the signed-in person, who is the GM when they say so.
export function renderSetup(root: HTMLElement, meId: string): void {
  const phases = {
    form: required<HTMLElement>(root, '[data-form-phase]'),
    progress: required<HTMLElement>(root, '[data-progress-phase]'),
    result: required<HTMLElement>(root, '[data-result-phase]'),
  };

  function show(phase: keyof typeof phases): void {
    for (const [name, element] of Object.entries(phases)) element.hidden = name !== phase;
  }

  bindSetupForm(root, meId, (submission) => {
    show('progress');

    const api = realApi(submission.playerExpiry, submission.gmExpiry);

    void runProgress(root, submission.input, api).then((state) => {
      showResult(root, submission.input, state, submission.gmLabel);
      show('result');
    });
  });
}
