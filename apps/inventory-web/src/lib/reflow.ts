// Runs `mutate` inside a same-document View Transition when the browser has them and the
// user hasn't asked for reduced motion; a plain DOM mutation otherwise.
export function withReflow(mutate: () => void) {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!reduceMotion && document.startViewTransition) {
    document.startViewTransition(mutate);
  } else {
    mutate();
  }
}
