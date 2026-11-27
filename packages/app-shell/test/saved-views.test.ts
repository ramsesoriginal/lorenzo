import { JSDOM } from 'jsdom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mountSavedViews, type ViewRecord, type ViewStore, viewNameOf } from '../src/saved-views';

describe('the name of a view', () => {
  it('is what is left of it without stray spaces, and needs a word', () => {
    expect(viewNameOf('  Allies   of the court ')).toBe('Allies of the court');
    expect(viewNameOf('   ')).toBeNull();
    expect(viewNameOf('x'.repeat(81))).toBeNull();
    expect(viewNameOf('x'.repeat(80))).toBe('x'.repeat(80));
  });
});

describe('the saved views control', () => {
  let dom: JSDOM;

  beforeEach(() => {
    dom = new JSDOM('<!doctype html><body></body>');
    vi.stubGlobal('document', dom.window.document);
  });
  afterEach(() => vi.unstubAllGlobals());

  const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

  function setup(initial: ViewRecord[] = []) {
    const kept = [...initial];
    const store: ViewStore = {
      list: vi.fn(async () => [...kept]),
      save: vi.fn(async (name, query) => {
        const view = { id: `v${kept.length + 1}`, name, query };

        kept.push(view);
        return view;
      }),
      remove: vi.fn(async (id) => {
        kept.splice(
          kept.findIndex((view) => view.id === id),
          1,
        );
      }),
    };
    const apply = vi.fn();
    const say = vi.fn();
    const control = mountSavedViews({ store, current: () => ({ type: 'ally' }), apply, say });

    document.body.append(control.element);
    const $ = <T extends Element>(selector: string) => control.element.querySelector(selector) as T;

    return { control, store, apply, say, $ };
  }

  it('lists the views kept, and setting the list to one applies its query', async () => {
    const { control, apply, $ } = setup([{ id: 'a', name: 'Allies', query: { type: 'ally' } }]);

    await control.refresh();
    expect([...$<HTMLSelectElement>('select').options].map((o) => o.textContent)).toEqual([
      'Choose a view…',
      'Allies',
    ]);
    const select = $<HTMLSelectElement>('select');

    select.value = 'a';
    select.dispatchEvent(new dom.window.Event('change'));
    expect(apply).toHaveBeenCalledWith({ type: 'ally' });
  });

  it('keeps the filters as they are now under a name, and says so', async () => {
    const { control, store, say, $ } = setup();

    await control.refresh();
    expect($<HTMLSelectElement>('select').options[0]?.textContent).toBe('None saved yet');
    $<HTMLButtonElement>('button').click();
    const name = $<HTMLInputElement>('input');

    expect(name.closest('form')?.hidden).toBe(false);
    name.value = '  Court allies ';
    name.closest('form')?.dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    expect(store.save).toHaveBeenCalledWith('Court allies', { type: 'ally' });
    expect(say).toHaveBeenCalledWith('Saved the view “Court allies”.');
    expect($<HTMLSelectElement>('select').selectedOptions[0]?.textContent).toBe('Court allies');
  });

  it('asks for a name when there is none, and does not save', async () => {
    const { store, say, $ } = setup();

    $<HTMLButtonElement>('button').click();
    $<HTMLInputElement>('input')
      .closest('form')
      ?.dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    expect(store.save).not.toHaveBeenCalled();
    expect(say).toHaveBeenCalledWith('Give the view a name.', true);
  });

  it('deletes the view chosen, and says when it could not', async () => {
    const { control, store, say, $ } = setup([{ id: 'a', name: 'Allies', query: {} }]);

    await control.refresh();
    const select = $<HTMLSelectElement>('select');

    select.value = 'a';
    select.dispatchEvent(new dom.window.Event('change'));
    const buttons = [...control.element.querySelectorAll('button')];
    const remove = buttons.find((b) => b.textContent === 'Delete this view') as HTMLButtonElement;

    expect(remove.hidden).toBe(false);
    remove.click();
    await settle();
    expect(store.remove).toHaveBeenCalledWith('a');
    expect(say).toHaveBeenCalledWith('Deleted the view “Allies”.');
    expect(select.options).toHaveLength(1);

    vi.mocked(store.save).mockRejectedValueOnce(new Error('offline'));
    buttons[0]?.click();
    $<HTMLInputElement>('input').value = 'Again';
    $<HTMLInputElement>('input')
      .closest('form')
      ?.dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    expect(say).toHaveBeenLastCalledWith('Could not save the view. Try again.', true);
  });
});
