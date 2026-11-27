import { el } from './dom';

/**
 * A standing as the design's grammar draws it (SO3): the number always, a quiet bar scaled to the
 * stat's own minimum and maximum, and a word for how it is known. The bar is left out where the
 * stat has no scale, and below zero it is hatched, so nothing rests on colour.
 */
export function standingMark(
  value: number | string | boolean,
  scale: { min: number | null; max: number | null },
  state: 'direct' | 'inherited' | 'derived',
) {
  const root = el('span', '', 'standing');
  root.dataset.state = state;
  root.append(el('span', String(value), 'standing-num'));
  const { min, max } = scale;
  if (typeof value === 'number' && min !== null && max !== null && max > min) {
    const bar = el('span', '', 'standing-bar');
    bar.setAttribute('aria-hidden', 'true');
    const fill = el('i');
    const share = (Math.min(Math.max(value, min), max) - min) / (max - min);
    // A scale that crosses zero is drawn from its middle outwards; otherwise from its start.
    if (min < 0 && max > 0) {
      const zero = -min / (max - min);
      const left = Math.min(share, zero);
      fill.style.marginLeft = `${left * 100}%`;
      fill.style.width = `${Math.abs(share - zero) * 100}%`;
      if (value < 0) fill.className = 'neg';
    } else {
      fill.style.width = `${share * 100}%`;
    }
    bar.append(fill);
    root.append(bar);
  }
  if (state !== 'direct') root.append(el('span', state, 'standing-mark'));
  return root;
}

/** A standing that is not known as of the date lens: no number, a word, drawn dotted (SO4). */
export function unknownMark(words: string) {
  const root = el('span', '', 'standing');
  root.dataset.state = 'unknown';
  root.append(el('span', '?', 'standing-num'), el('span', words, 'standing-mark'));
  return root;
}
