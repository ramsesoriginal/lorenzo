// Runs `ahead` when `element` is likely to be clicked next: the pointer rests on it a moment, it
// gets keyboard focus, or the button goes down, which is some tens of milliseconds before the
// click lands - all a quick click on a big target gives. Sweeping the pointer across a row of
// them starts nothing.
const INTENT_MS = 60;

export function onIntent(element: HTMLElement, ahead: () => void, signal: AbortSignal) {
  let timer: ReturnType<typeof setTimeout> | undefined;

  const cancel = () => clearTimeout(timer);

  element.addEventListener(
    'pointerenter',
    () => {
      cancel();
      timer = setTimeout(ahead, INTENT_MS);
    },
    { signal },
  );
  element.addEventListener('pointerleave', cancel, { signal });
  element.addEventListener('pointerdown', ahead, { signal });
  element.addEventListener('focus', ahead, { signal });
  element.addEventListener('blur', cancel, { signal });
}
