import type { Bi } from './profile';

// A page as data: both languages side by side, so one cannot grow a section the other lacks.
// Text is rendered as text, never as HTML.
export type Block = { p: Bi } | { ul: Bi[] } | { table: { head: Bi[]; rows: Bi[][] } };

export type Section = { id: string; heading: Bi; blocks: Block[] };

export type Doc = { title: Bi; sections: Section[] };

export type Lang = 'de' | 'en';

export const bi = (de: string, en: string): Bi => ({ de, en });
export const same = (text: string): Bi => ({ de: text, en: text });

/** The date the fixed text of the notice and the policy last changed (git has the history). */
export const TEXT_CHANGED = '2026-11-07';
