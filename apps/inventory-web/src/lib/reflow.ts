// Runs `mutate` inside a same-document View Transition when the browser has them and the
// user hasn't asked for reduced motion; a plain DOM mutation otherwise.
//
// Only what is named moves: `names` gives the elements that morph (each its own name, set before the
// old picture is taken and cleared when the transition is over). The rest of the page, the root, stays
// where it is, so a drag moves a card and not the whole page.
export function withReflow(
  mutate: () => void,
  options: { names?: [HTMLElement, string][]; after?: () => void } = {},
) {
  const { names = [], after } = options;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  for (const [element, name] of names) element.style.viewTransitionName = name;

  const done = () => {
    for (const [element] of names) element.style.viewTransitionName = '';

    after?.();
  };

  if (!reduceMotion && document.startViewTransition) {
    void document.startViewTransition(mutate).finished.then(done, done);
  } else {
    mutate();
    done();
  }
}
