import { describe, expect, it, vi } from 'vitest';
import { createPreviewState, HIDE_MS, SHOW_MS, type Timers } from '../src/state';

function setup() {
  let now = 0;
  let next = 0;
  const pending = new Map<number, { at: number; run: () => void }>();
  const timers: Timers = {
    set: (run, ms) => {
      pending.set(++next, { at: now + ms, run });
      return next;
    },
    clear: (handle) => {
      pending.delete(handle as number);
    },
  };
  const advance = (ms: number) => {
    now += ms;
    for (const [id, { at, run }] of [...pending]) {
      if (at <= now) {
        pending.delete(id);
        run();
      }
    }
  };
  const open = vi.fn();
  const close = vi.fn();
  return { state: createPreviewState<string>(open, close, timers), open, close, advance };
}

describe('createPreviewState', () => {
  it('opens after the pointer rests, not while it sweeps past', () => {
    const { state, open, advance } = setup();

    state.enter('a');
    advance(SHOW_MS - 1);
    state.leave();
    advance(SHOW_MS);

    expect(open).not.toHaveBeenCalled();

    state.enter('a');
    advance(SHOW_MS);

    expect(open).toHaveBeenCalledExactlyOnceWith('a');
    expect(state.shown()).toBe('a');
  });

  it('stays open when the pointer crosses to the card or back, and closes after it leaves', () => {
    const { state, open, close, advance } = setup();

    state.enter('a');
    advance(SHOW_MS);
    state.leave();
    advance(HIDE_MS - 1);
    state.holdCard();
    advance(1000);

    expect(close).not.toHaveBeenCalled();

    state.leave();
    state.enter('a');
    advance(1000);

    expect(close).not.toHaveBeenCalled();
    expect(open).toHaveBeenCalledOnce();

    state.leave();
    advance(HIDE_MS);

    expect(close).toHaveBeenCalledOnce();
    expect(state.shown()).toBeNull();
  });

  it('moves from one link to the next by opening the next after its delay', () => {
    const { state, open, advance } = setup();

    state.enter('a');
    advance(SHOW_MS);
    state.leave();
    state.enter('b');
    advance(SHOW_MS);

    expect(open.mock.calls).toEqual([['a'], ['b']]);
    expect(state.shown()).toBe('b');
  });

  it('opens at once on focus, closes on blur and on Escape', () => {
    const { state, open, close } = setup();

    state.focus('a');

    expect(open).toHaveBeenCalledExactlyOnceWith('a');

    state.escape();

    expect(close).toHaveBeenCalledOnce();

    state.focus('a');
    state.blur();

    expect(close).toHaveBeenCalledTimes(2);

    state.blur();

    expect(close).toHaveBeenCalledTimes(2);
  });

  it('a tap opens the card, a second tap on the same link follows it', () => {
    const { state, open } = setup();

    expect(state.tap('a')).toBe(false);
    expect(open).toHaveBeenCalledExactlyOnceWith('a');
    expect(state.tap('a')).toBe(true);
    expect(state.tap('b')).toBe(false);
    expect(state.shown()).toBe('b');
  });

  it('a tap elsewhere dismisses it', () => {
    const { state, close } = setup();

    state.tap('a');
    state.dismiss();

    expect(close).toHaveBeenCalledOnce();
    expect(state.tap('a')).toBe(false);
  });
});
