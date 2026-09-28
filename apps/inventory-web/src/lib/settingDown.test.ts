import { describe, expect, it, vi } from 'vitest';
import { LorenzoApiError } from './api';
import { deleteSplitQuestion, isStackRefusal, splitQuestion } from './settingDown';

vi.mock('./auth', () => ({ getAccessToken: vi.fn() }));

describe('splitQuestion', () => {
  it('asks nothing for single items', () => {
    expect(splitQuestion([{ title: 'Rope', quantity: null }])).toBeNull();
    expect(splitQuestion([{ title: 'Rope', quantity: 1 }, { title: 'Book' }])).toBeNull();
  });

  it('says how many items a stack becomes', () => {
    expect(splitQuestion([{ title: 'Arrow', quantity: 20 }])).toBe(
      'Setting down Arrow ×20 leaves 20 separate items. Set it down?',
    );
  });

  it('asks once for a selection, naming a lone stack or counting several', () => {
    expect(splitQuestion([{ title: 'Rope' }, { title: 'Arrow', quantity: 3 }])).toBe(
      'Setting these down leaves Arrow ×3 as 3 separate items. Set them down?',
    );
    expect(
      splitQuestion([
        { title: 'Arrow', quantity: 3 },
        { title: 'Bolt', quantity: 5 },
      ]),
    ).toBe('Setting these down leaves 2 stacks as 8 separate items. Set them down?');
  });
});

describe('isStackRefusal', () => {
  it('knows the refusal of a stack out of every container', () => {
    expect(isStackRefusal(new LorenzoApiError('No', 409, 'stack-needs-container'))).toBe(true);
    expect(isStackRefusal(new LorenzoApiError('No', 409, 'item-bound'))).toBe(false);
    expect(isStackRefusal(new Error('No'))).toBe(false);
  });
});

describe('deleteSplitQuestion', () => {
  it('names what is deleted', () => {
    expect(deleteSplitQuestion('Chest')).toBe(
      `Deleting "Chest" sets down what's inside it, and a stack among that becomes single items. Delete it?`,
    );
  });
});
