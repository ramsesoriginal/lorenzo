// Toasts (ADR 0415): at the bottom, directly above the status bar (above the tab bar on a phone), in
// a live region. Three kinds: a quiet confirmation, a reversible action with Undo, and an error that
// stays until it is dismissed and offers "Try again". One that leaves by itself stays ten seconds and
// shows its countdown.

import { createToastTimer } from './toast-timer';

export type ToastKind = 'ok' | 'undo' | 'error';

export type ToastOptions = {
  kind?: ToastKind;
  title: string;
  text?: string;
  /** Undo for an `undo` toast, "Try again" for an error: what the button says and does. */
  action?: { label: string; run(): void };
  /** How long it stays, if it leaves by itself. */
  ms?: number;
};

export type ToastHandle = { dismiss(): void };

export const TOAST_MS = 10_000;
const MAX = 3;
const SVG = 'http://www.w3.org/2000/svg';

const ICON: Record<ToastKind, string> = { ok: 'select-item', undo: 'undo', error: 'warning' };

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: string) {
  const node = document.createElement(tag);

  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;

  return node;
}

function icon(sprite: string, name: string): SVGSVGElement {
  const svg = document.createElementNS(SVG, 'svg');
  const use = document.createElementNS(SVG, 'use');

  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  use.setAttribute('href', `${sprite}#icon-${name}`);
  svg.append(use);

  return svg;
}

export function createToasts(host: HTMLElement, sprite: string) {
  function dismiss(card: HTMLElement, now = false) {
    if (!card.isConnected || card.classList.contains('out')) return;

    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

    if (now || reduced) {
      card.remove();

      return;
    }
    card.classList.add('out');
    setTimeout(() => card.remove(), 230);
  }

  return {
    show(options: ToastOptions): ToastHandle {
      const kind = options.kind ?? 'ok';
      const timed = kind !== 'error';
      const card = el('div', 'toast-card');
      const body = el('div', 'toast-text');

      card.dataset.kind = kind;
      card.setAttribute('role', kind === 'error' ? 'alert' : 'status');
      body.append(el('div', 'toast-title', options.title));
      if (options.text) body.append(el('div', 'toast-meta', options.text));
      card.append(icon(sprite, ICON[kind]), body);

      if (options.action) {
        const action = options.action;
        const button = el('button', 'btn btn-secondary toast-action', action.label);

        button.type = 'button';
        button.addEventListener('click', () => {
          action.run();
          dismiss(card);
        });
        card.append(button);
      }

      const close = el('button', 'icon-button');

      close.type = 'button';
      close.setAttribute('aria-label', 'Dismiss');
      close.append(icon(sprite, 'close'));
      close.addEventListener('click', () => dismiss(card));
      card.append(close);

      host.append(card);
      while (host.children.length > MAX) dismiss(host.firstElementChild as HTMLElement, true);

      if (timed) {
        const ms = options.ms ?? TOAST_MS;
        const bar = () => {
          card.querySelector('.toast-bar')?.remove();

          const fresh = el('span', 'toast-bar');

          fresh.setAttribute('aria-hidden', 'true');
          fresh.style.setProperty('--toast-ms', `${ms}ms`);
          card.append(fresh);
        };
        const timer = createToastTimer(ms, () => dismiss(card));
        const hold = () => timer.hold();
        const release = () => {
          if (card.matches(':hover') || card.contains(document.activeElement)) return;
          bar();
          timer.release();
        };

        bar();
        timer.start();
        card.addEventListener('pointerenter', hold);
        card.addEventListener('pointerleave', release);
        card.addEventListener('focusin', hold);
        card.addEventListener('focusout', () => setTimeout(release, 0));
        card.addEventListener('animationend', () => {
          // The bar ran out under a pointer that was not there to see it: nothing to do.
        });
      }

      return { dismiss: () => dismiss(card) };
    },
  };
}
