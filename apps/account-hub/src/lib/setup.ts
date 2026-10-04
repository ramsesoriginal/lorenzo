// One-click setup (ADR 0180), the logic without the DOM: the slug derived from a
// name, the steps a choice needs, and a runner that makes them in order and can
// be run again from the step that failed. Dependency-free like format.ts. The
// API calls are handed in (SetupApi), so a test can fail any step and watch the
// retry skip what is already made.

// What the form asks: who runs the campaign.
export type GmChoice =
  | { kind: 'me' }
  | { kind: 'user'; userId: string }
  // A single-use GM link (ADR 0177), for someone who has an account or doesn't.
  | { kind: 'link' };

export type StepId = 'library' | 'campaign' | 'gm' | 'gm-link' | 'player-link';

export interface SetupInput {
  libraryName: string;
  campaignName: string;
  gameSystem: string;
  gm: GmChoice;
  // The signed-in person: the GM when the choice is `me`.
  meId: string;
}

// What has been made so far. Kept by whoever runs the setup and handed back to
// `runSetup` to resume: a step already done is not done twice.
export interface SetupState {
  libraryId: string | null;
  campaignId: string | null;
  gmDone: boolean;
  gmLinkToken: string | null;
  playerLinkToken: string | null;
}

export function emptySetupState(): SetupState {
  return {
    libraryId: null,
    campaignId: null,
    gmDone: false,
    gmLinkToken: null,
    playerLinkToken: null,
  };
}

// The calls the chain makes: the same ones /tenants already makes, nothing new
// (ADR 0180). `role` is what the link makes whoever opens it (ADR 0177).
export interface SetupApi {
  createLibrary(name: string): Promise<{ id: string }>;
  createCampaign(
    libraryId: string,
    campaign: { name: string; slug: string; gameSystem: string },
  ): Promise<{ id: string }>;
  grantGm(libraryId: string, campaignId: string, userId: string): Promise<void>;
  createInvite(
    libraryId: string,
    campaignId: string,
    role: 'player' | 'gm',
  ): Promise<{ token: string }>;
}

// The steps a choice needs, in the order they are made.
export function stepsFor(gm: GmChoice): StepId[] {
  return ['library', 'campaign', gm.kind === 'link' ? 'gm-link' : 'gm', 'player-link'];
}

export function stepLabel(step: StepId): string {
  switch (step) {
    case 'library':
      return 'Making the library';
    case 'campaign':
      return 'Making the campaign';
    case 'gm':
      return 'Making the GM';
    case 'gm-link':
      return 'Making the GM link';
    case 'player-link':
      return 'Making the link for your players';
  }
}

export function stepDoneLabel(step: StepId): string {
  switch (step) {
    case 'library':
      return 'Library made';
    case 'campaign':
      return 'Campaign made';
    case 'gm':
      return 'GM set';
    case 'gm-link':
      return 'GM link made';
    case 'player-link':
      return 'Link for your players made';
  }
}

// A step that did not work, and which one, so the page can say where it stopped
// and offer to go on from there.
export class SetupFailure extends Error {
  readonly step: StepId;
  readonly original: unknown;

  constructor(step: StepId, original: unknown) {
    super(`Setup stopped at "${step}"`);
    this.name = 'SetupFailure';
    this.step = step;
    this.original = original;
  }
}

// The API's slug grammar (apps/api's slug check): lowercase letters and digits,
// single hyphens between words. Accents are folded to their letter, anything else
// is a separator, and a name with nothing usable in it is still a valid slug.
const MAX_SLUG_LENGTH = 60;

export function slugify(name: string, fallback = 'campaign'): string {
  const slug = name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, MAX_SLUG_LENGTH)
    .replace(/-+$/g, '');
  return slug === '' ? fallback : slug;
}

// Makes whatever is not yet made, in order, and records it in `state` as it goes
// (so a failure part-way leaves the state describing exactly what exists).
// Throws SetupFailure at the first step that fails; calling it again with the
// same state carries on from there. `onStep` hears each step start and finish.
export async function runSetup(
  input: SetupInput,
  state: SetupState,
  api: SetupApi,
  onStep: (step: StepId, status: 'start' | 'done') => void = () => {},
): Promise<SetupState> {
  async function run(step: StepId, alreadyDone: boolean, action: () => Promise<void>) {
    if (alreadyDone) return;
    onStep(step, 'start');
    try {
      await action();
    } catch (error) {
      throw new SetupFailure(step, error);
    }
    onStep(step, 'done');
  }

  await run('library', state.libraryId !== null, async () => {
    state.libraryId = (await api.createLibrary(input.libraryName)).id;
  });
  const libraryId = state.libraryId as string;

  await run('campaign', state.campaignId !== null, async () => {
    state.campaignId = (
      await api.createCampaign(libraryId, {
        name: input.campaignName,
        slug: slugify(input.campaignName),
        gameSystem: input.gameSystem,
      })
    ).id;
  });
  const campaignId = state.campaignId as string;

  if (input.gm.kind === 'link') {
    await run('gm-link', state.gmLinkToken !== null, async () => {
      state.gmLinkToken = (await api.createInvite(libraryId, campaignId, 'gm')).token;
    });
  } else {
    const gmUserId = input.gm.kind === 'me' ? input.meId : input.gm.userId;
    await run('gm', state.gmDone, async () => {
      await api.grantGm(libraryId, campaignId, gmUserId);
      state.gmDone = true;
    });
  }

  await run('player-link', state.playerLinkToken !== null, async () => {
    state.playerLinkToken = (await api.createInvite(libraryId, campaignId, 'player')).token;
  });
  return state;
}
