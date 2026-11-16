// The seven page templates (ADR 0412): which container a template gives a page. Pure, so it is
// tested without a browser. Reading has a 680px measure and a form 1040px; the board, the
// workspace and the editor are full width, because they carry their own columns (the editor's
// writing column is 720px inside it).

export type PageTemplate =
  | 'list-detail'
  | 'reading'
  | 'form'
  | 'editor'
  | 'board'
  | 'workspace'
  | 'home';

export const TEMPLATES: PageTemplate[] = [
  'list-detail',
  'reading',
  'form',
  'editor',
  'board',
  'workspace',
  'home',
];

const CLASS: Record<PageTemplate, string> = {
  'list-detail': 'shell-page',
  reading: 'shell-page shell-page--reading',
  form: 'shell-page shell-page--form',
  editor: 'shell-page shell-page--wide',
  board: 'shell-page shell-page--wide',
  workspace: 'shell-page shell-page--wide',
  home: 'shell-page',
};

/** The classes of a page's container for a template. */
export function pageClass(template: PageTemplate): string {
  return CLASS[template];
}

/** How a template saves by default (ADR 0412); a page may say otherwise, but it says which. */
export type SaveStyle = 'explicit' | 'autosave' | 'none';

export function defaultSaving(template: PageTemplate): SaveStyle {
  if (template === 'form') return 'explicit';
  if (template === 'editor') return 'autosave';

  return 'none';
}
