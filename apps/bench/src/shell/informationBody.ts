import { validatePicture } from '@lorenzo/information-editor';
import type { Bench } from '../core/bench';
import type { TextDoc } from '../core/transport';
import { liveEditor } from './liveEditor';

/** Bench's in-place texts with the other payloads between them, in their stored order. */
export function informationBody(
  bench: Bench,
  entryId: string,
  doc: TextDoc | null,
  type: 'description' | 'note',
  go: (id: string) => void,
): HTMLElement {
  const root = document.createElement('div');
  root.className = 'information-body';
  // A pointer action beside the source must not collapse it between mouse-down and click.
  // Keyboard focus still reaches every action normally.
  root.addEventListener('mousedown', (event) => {
    if (
      event.target instanceof Element &&
      event.target.closest('button, summary') &&
      document.activeElement instanceof HTMLTextAreaElement &&
      root.contains(document.activeElement)
    )
      event.preventDefault();
  });
  if (doc) root.dataset.information = doc.id;
  const status = document.createElement('p');
  status.className = 'muted';
  status.hidden = true;
  const onPicture = bench.transport.appendPicture
    ? async (file: File) => {
        try {
          await validatePicture(file);
          for (const editor of root.querySelectorAll('.text-editor'))
            editor.dispatchEvent(new Event('information-flush'));
          await bench.addInformationPicture(entryId, doc?.id ?? null, type, file);
        } catch (error) {
          status.hidden = false;
          status.setAttribute('role', 'status');
          status.textContent =
            error instanceof Error ? error.message : 'The picture could not be added.';
        }
      }
    : undefined;
  const textEditor = (text: string, payloadId?: string, first = true) =>
    liveEditor({
      bench,
      go,
      home: entryId,
      key: `${type === 'description' ? `description:${entryId}` : `note:${doc?.id}`}${first ? '' : `:${payloadId}`}`,
      label:
        type === 'description'
          ? first
            ? 'Description'
            : 'Description continued'
          : `Note: ${doc?.title ?? 'Note'}`,
      placeholder: type === 'description' ? 'Write a description…' : 'Write a note…',
      text,
      onChange: (text) =>
        type === 'description'
          ? bench.setDescription(entryId, text, payloadId)
          : doc && bench.setNoteText(entryId, doc.id, text, payloadId),
      ...(onPicture && { onPicture }),
    });
  let first = true;
  for (const payload of doc?.information?.payloads ?? []) {
    if (payload.kind === 'description') {
      root.append(textEditor(payload.content, payload.id, first));
      first = false;
      continue;
    }
    const part = document.createElement('div');
    if (payload.kind === 'number') part.textContent = String(payload.value);
    else {
      const link = document.createElement('a');
      link.target = '_blank';
      link.rel = 'noopener';
      if (payload.kind === 'picture') {
        const image = document.createElement('img');
        image.alt = doc?.title || 'Attached image';
        image.className = 'information-picture';
        link.append(image);
      } else {
        link.textContent = payload.filename;
        link.download = payload.filename;
      }
      part.append(link);
      void bench.transport
        .payloadFile?.(payload.id, payload.updated_at)
        .then((url) => {
          link.href = url;
          const image = link.querySelector('img');
          if (image) image.src = url;
        })
        .catch(() => {
          part.textContent = 'This attachment could not be read.';
        });
    }
    if (payload.kind === 'picture' && doc?.information) {
      const menu = document.createElement('details');
      menu.className = 'picture-part-actions';
      const summary = document.createElement('summary');
      summary.textContent = '⋯';
      summary.setAttribute('aria-label', 'Picture actions');
      menu.append(summary);
      const parts = doc.information.payloads;
      const index = parts.findIndex((part) => part.id === payload.id);
      for (const [label, step] of [
        ['Move picture up', -1],
        ['Move picture down', 1],
      ] as const) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn quiet';
        button.textContent = label;
        button.disabled = index + step < 0 || index + step >= parts.length;
        button.addEventListener('click', () => {
          for (const editor of root.querySelectorAll('.text-editor'))
            editor.dispatchEvent(new Event('information-flush'));
          const ids = parts.map((part) => part.id);
          const before = JSON.stringify(ids);
          [ids[index], ids[index + step]] = [ids[index + step] as string, ids[index] as string];
          bench.setField(
            entryId,
            { kind: 'payload-order', id: doc.id },
            { value: before, version: `W/"${doc.information?.updated_at}"` },
            JSON.stringify(ids),
          );
        });
        menu.append(button);
      }
      if (bench.transport.removePicturePayload) {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn quiet';
        remove.textContent = 'Remove picture';
        remove.addEventListener('click', async () => {
          if (!window.confirm('Remove this picture? It cannot be restored with Undo.')) return;
          remove.disabled = true;
          try {
            for (const editor of root.querySelectorAll('.text-editor'))
              editor.dispatchEvent(new Event('information-flush'));
            await bench.removeInformationPicture(entryId, payload.id, `W/"${payload.updated_at}"`);
          } catch (error) {
            status.hidden = false;
            status.setAttribute('role', 'status');
            status.textContent =
              error instanceof Error ? error.message : 'The picture could not be removed.';
          } finally {
            remove.disabled = false;
          }
        });
        menu.append(remove);
      }
      part.append(menu);
    }
    root.append(part);
  }
  if (first) root.append(textEditor(doc?.text ?? ''));
  // Drops on the information's image or whitespace target this same information.
  if (onPicture) {
    root.addEventListener('dragover', (event) => {
      if (event.dataTransfer?.types.includes('Files')) {
        event.preventDefault();
        event.stopPropagation();
        root.classList.add('picture-drop-target');
      }
    });
    root.addEventListener('dragleave', () => root.classList.remove('picture-drop-target'));
    root.addEventListener('drop', (event) => {
      root.classList.remove('picture-drop-target');
      const file = Array.from(event.dataTransfer?.files ?? []).find((file) =>
        file.type.startsWith('image/'),
      );
      if (file) {
        event.preventDefault();
        event.stopPropagation();
        void onPicture(file);
      }
    });
  }
  const upload = bench.informationUpload(entryId, doc?.id ?? null, type);
  if (upload) {
    status.hidden = false;
    status.setAttribute('role', 'status');
    status.textContent = upload.busy ? 'Adding picture…' : upload.problem;
    if (!upload.busy) {
      const retry = document.createElement('button');
      retry.type = 'button';
      retry.className = 'btn quiet';
      retry.textContent = 'Retry picture';
      retry.addEventListener(
        'click',
        () => void bench.retryInformationPicture(entryId, doc?.id ?? null, type),
      );
      const dismiss = document.createElement('button');
      dismiss.type = 'button';
      dismiss.className = 'btn quiet';
      dismiss.textContent = 'Dismiss upload error';
      dismiss.addEventListener('click', () =>
        bench.dismissInformationPicture(entryId, doc?.id ?? null, type),
      );
      root.append(retry, dismiss);
    }
  }
  root.append(status);
  return root;
}
