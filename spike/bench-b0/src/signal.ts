// The "tiny signal and computed-value helper" of RFC 0039 §9. Own code, no dependency.
type Fn = () => void;
let running: Effect | null = null;

class Effect {
  deps = new Set<Set<Effect>>();
  scheduled = false;
  constructor(readonly fn: Fn) {}
  run() {
    this.scheduled = false;
    for (const d of this.deps) d.delete(this);
    this.deps.clear();
    const prev = running;
    running = this;
    try {
      this.fn();
    } finally {
      running = prev;
    }
  }
  schedule() {
    if (this.scheduled) return;
    this.scheduled = true;
    queueMicrotask(() => this.scheduled && this.run());
  }
}

export interface Signal<T> {
  (): T;
  set(v: T): void;
  peek(): T;
}

export function signal<T>(initial: T, equal: (a: T, b: T) => boolean = Object.is): Signal<T> {
  let value = initial;
  const subs = new Set<Effect>();
  const read = (() => {
    if (running) {
      subs.add(running);
      running.deps.add(subs);
    }
    return value;
  }) as Signal<T>;
  read.peek = () => value;
  read.set = (v: T) => {
    if (equal(value, v)) return;
    value = v;
    for (const e of [...subs]) e.schedule();
  };
  return read;
}

export function effect(fn: Fn): () => void {
  const e = new Effect(fn);
  e.run();
  return () => {
    for (const d of e.deps) d.delete(e);
    e.deps.clear();
    e.scheduled = false;
  };
}
