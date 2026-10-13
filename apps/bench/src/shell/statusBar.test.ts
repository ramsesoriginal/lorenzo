import { describe, expect, it } from 'vitest';
import type { Command } from '../core/commands';
import { summarize, syncText } from './statusBar';

const cmd = (state: Command['state']) => ({ state }) as Command;

describe('the sync part of the status bar', () => {
  it('says Synced when nothing waits', () => {
    expect(syncText(summarize([]))).toBe('Synced');
  });
  it('counts what waits, sending included', () => {
    expect(syncText(summarize([cmd('waiting'), cmd('sending')]))).toBe('Waiting to sync (2)');
  });
  it('puts conflicts before attention before waiting', () => {
    expect(syncText(summarize([cmd('waiting'), cmd('attention')]))).toBe('Needs attention (1)');
    expect(syncText(summarize([cmd('attention'), cmd('conflict'), cmd('waiting')]))).toBe(
      'Conflict (1)',
    );
  });
});
