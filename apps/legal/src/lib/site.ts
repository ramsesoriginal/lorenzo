import type { Doc, Lang } from './doc';
import { TEXT_CHANGED } from './doc';
import { loadProfile } from './profile';
import { SAMPLE_PROFILE } from './sample-profile';
import { noticeDoc } from './texts/notice';
import { policyDoc } from './texts/policy';

// The pages and where they are (ADR 0439): one canonical address for each page in each language.
export const PATHS = {
  de: { notice: '/de/impressum/', policy: '/de/datenschutz/' },
  en: { notice: '/en/legal-notice/', policy: '/en/privacy-policy/' },
} as const;

export function pageFor(kind: 'notice' | 'policy', lang: Lang) {
  // Read when a page is built, so a missing profile fails the build (src/lib/profile.ts).
  const profile = loadProfile(process.env, SAMPLE_PROFILE);
  const doc: Doc = kind === 'notice' ? noticeDoc(profile) : policyDoc(profile);
  const other: Lang = lang === 'de' ? 'en' : 'de';
  return {
    profile,
    doc,
    title: doc.title[lang],
    changed: [profile.changedOn, TEXT_CHANGED].sort().at(-1) ?? TEXT_CHANGED,
    paths: PATHS[lang],
    other: PATHS[other][kind],
  };
}
