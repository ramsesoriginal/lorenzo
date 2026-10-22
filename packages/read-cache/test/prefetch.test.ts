import { describe, expect, it } from 'vitest';
import { createPrefetchQueue } from '../src/prefetch';

function deferred() {
  let done: () => void = () => {};
  const promise = new Promise<void>((resolve) => {
    done = resolve;
  });

  return { promise, done };
}

describe('the prefetch queue', () => {
  it('runs two reads at once and queues the rest', async () => {
    const queue = createPrefetchQueue();
    const jobs = [deferred(), deferred(), deferred()];
    const started: number[] = [];

    jobs.forEach((job, index) => {
      queue.enqueue(`k${index}`, () => {
        started.push(index);

        return job.promise;
      });
    });
    expect(started).toEqual([0, 1]);
    jobs[0]?.done();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(started).toEqual([0, 1, 2]);
  });

  it('ignores a key it has seen, and stops at its limits', () => {
    const queue = createPrefetchQueue({ concurrent: 1, queued: 2, intents: 3 });
    const never = () => new Promise<void>(() => {});

    expect(queue.enqueue('a', never)).toBe(true);
    expect(queue.enqueue('a', never)).toBe(false);
    expect(queue.enqueue('b', never)).toBe(true);
    expect(queue.enqueue('c', never)).toBe(true);
    expect(queue.enqueue('d', never)).toBe(false);
  });

  it('starts over for a new view', () => {
    const queue = createPrefetchQueue({ intents: 1 });
    const never = () => new Promise<void>(() => {});

    expect(queue.enqueue('a', never)).toBe(true);
    expect(queue.enqueue('b', never)).toBe(false);
    queue.reset();
    expect(queue.enqueue('b', never)).toBe(true);
  });

  it('survives a read that fails', async () => {
    const queue = createPrefetchQueue({ concurrent: 1 });
    const order: string[] = [];

    queue.enqueue('a', async () => {
      order.push('a');
      throw new Error('no');
    });
    queue.enqueue('b', async () => {
      order.push('b');
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(order).toEqual(['a', 'b']);
  });
});
