// Slugs (ADR 0107, 0113): the logic is packages/entity-parts (ADR 0526), shared with the other app that
// has them; this binds its calls to this app's client and words, so the rest of the app imports as
// before.
import type { components } from './api';
import { slugs } from './entityParts';

export { type SlugKind, slugCandidates } from '@lorenzo/entity-parts';

export type ResolvedSlug = components['schemas']['ResolvedSlugOut'];

export const { resolveSlugs, suggestSlug, slugProblem, saveSlug } = slugs;
