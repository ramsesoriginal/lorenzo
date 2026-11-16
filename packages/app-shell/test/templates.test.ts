import { describe, expect, it } from 'vitest';
import { defaultSaving, pageClass, TEMPLATES } from '../src/templates';

describe('page templates', () => {
  it('gives each of the seven a container', () => {
    expect(TEMPLATES).toHaveLength(7);
    expect(pageClass('reading')).toBe('shell-page shell-page--reading');
    expect(pageClass('form')).toBe('shell-page shell-page--form');
    expect(pageClass('list-detail')).toBe('shell-page');
    expect(pageClass('home')).toBe('shell-page');
  });

  it('lets the board, the workspace and the editor use the full width', () => {
    for (const t of ['board', 'workspace', 'editor'] as const) {
      expect(pageClass(t)).toContain('shell-page--wide');
    }
  });

  it('saves a form explicitly and an editor as it goes; the rest say so themselves', () => {
    expect(defaultSaving('form')).toBe('explicit');
    expect(defaultSaving('editor')).toBe('autosave');
    expect(defaultSaving('list-detail')).toBe('none');
  });
});
