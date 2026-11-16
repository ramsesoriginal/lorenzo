// Deterministic numbers (ADR 0407). Layouts are iterative and amplify any difference between
// engines, so they use an integer generator, fixed counts and only + - * / and square root. Math.sin,
// Math.cos and Math.exp are approximated differently by implementations and are never used.

/** A 32-bit seeded generator (mulberry32): integer arithmetic only, so every engine agrees. */
export function createRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TWO_PI = 6.283185307179586;
const HALF_PI = 1.5707963267948966;
const PI = Math.PI;

/** Sine by range reduction and a fixed-degree series: + - * / only. Accurate to about 1e-12. */
export function sin(x: number): number {
  // Reduce to [-pi, pi], then to [-pi/2, pi/2] by symmetry.
  let t = x - TWO_PI * Math.floor((x + PI) / TWO_PI);
  if (t > HALF_PI) t = PI - t;
  else if (t < -HALF_PI) t = -PI - t;
  const t2 = t * t;
  let term = t;
  let sum = t;
  for (let n = 1; n <= 9; n += 1) {
    term = (-term * t2) / (2 * n * (2 * n + 1));
    sum += term;
  }
  return sum;
}

export function cos(x: number): number {
  return sin(x + HALF_PI);
}

/** Two decimals, the precision a Scene is written in; -0 becomes 0. */
export function round2(value: number): number {
  if (!Number.isFinite(value)) throw new RangeError(`Not a finite number: ${value}`);
  const rounded = Math.round(value * 100) / 100;
  return rounded === 0 ? 0 : rounded;
}

export const TAU = TWO_PI;
