// The list's visible rows share their picture lookups across filtering and hover.
// At most four lookups (including protected image bytes) run at once.
export function createBeingPictures(fetchPicture: (id: string) => Promise<string | null>) {
  const kept = new Map<string, Promise<string | null>>();
  const waiting: Array<() => void> = [];
  let running = 0;

  function drain() {
    while (running < 4 && waiting.length > 0) waiting.shift()?.();
  }

  return (id: string): Promise<string | null> => {
    const known = kept.get(id);
    if (known) return known;
    let done: (picture: string | null) => void = () => {};
    const result = new Promise<string | null>((resolve) => {
      done = resolve;
    });
    kept.set(id, result);
    waiting.push(() => {
      running++;
      Promise.resolve()
        .then(() => fetchPicture(id))
        .then(done, () => {
          // A missing picture is kept; a failed lookup may be retried after filtering.
          kept.delete(id);
          done(null);
        })
        .finally(() => {
          running--;
          drain();
        });
    });
    drain();
    return result;
  };
}
