// The static demo (ADR 0511): the semilive editor over a plain text area, and the text it holds.
import { createEditor } from '../src';

const textarea = document.querySelector<HTMLTextAreaElement>('#source');
const out = document.querySelector<HTMLElement>('#out');
document.querySelector('#unbuilt')?.remove();
if (textarea && out) {
  textarea.value =
    '# A river crossing\n\nThe ferryman knew **every** crossing, and none of them twice.\n\n- a lantern\n- a rope\n\n> "The water remembers," he said.[^1]\n\n[^1]: He said it often.';
  createEditor({ textarea, toolbar: ['bold', 'italic', 'heading', 'bullets', '|', 'undo', 'redo'] });
  const show = () => {
    out.textContent = textarea.value;
  };
  textarea.addEventListener('input', show);
  show();
}
