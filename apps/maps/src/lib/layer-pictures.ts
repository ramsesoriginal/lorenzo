// The pictures under a Map as the renderer wants them (ADR 0362): each fetched with the bearer from
// the audience-checked content route, made into a `data:` URL here (never a `blob:` URL, an SVG
// included, ADR 0360) and measured. The renderer fetches and decodes nothing.
import type { Layer } from '@lorenzo/map-renderer';
import { getAccessToken } from './auth';
import { API_BASE_URL } from './config';
import type { Header } from './map-api';

export type LayerOut = NonNullable<Header['layers']>[number];

/** The size an SVG draws at: its `viewBox`, else its `width` and `height`; null when it says none. */
export function svgSize(text: string): [number, number] | null {
  const root = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
  if (!root || root.localName !== 'svg') return null;
  const box = (root.getAttribute('viewBox') ?? '')
    .trim()
    .split(/[\s,]+/)
    .map(Number);
  if (box.length === 4 && (box[2] ?? 0) > 0 && (box[3] ?? 0) > 0) {
    return [box[2] as number, box[3] as number];
  }
  const width = Number.parseFloat(root.getAttribute('width') ?? '');
  const height = Number.parseFloat(root.getAttribute('height') ?? '');
  return width > 0 && height > 0 ? [width, height] : null;
}

function dataUrlOf(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('The picture could not be read.'));
    reader.readAsDataURL(blob);
  });
}

async function decode(href: string): Promise<[number, number]> {
  const image = new Image();
  image.src = href;
  await image.decode();
  return [image.naturalWidth, image.naturalHeight];
}

async function one(tenant: string, layer: LayerOut): Promise<Layer | null> {
  if (!layer.payload_id) return null;
  const token = await getAccessToken();
  const response = await fetch(
    `${API_BASE_URL}/tenants/${tenant}/payloads/${layer.payload_id}/content`,
    {
      cache: 'no-store',
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  if (!response.ok) throw new Error('This picture is not available.');
  const blob = await response.blob();
  const href = await dataUrlOf(blob);
  let size: [number, number] | null = null;
  if (layer.content_type === 'image/svg+xml') size = svgSize(await blob.text());
  size ??= await decode(href);
  if (!(size[0] > 0) || !(size[1] > 0)) throw new Error('This picture has no size.');
  return {
    id: layer.information_id,
    href,
    size,
    opacity: layer.opacity ?? null,
    calibration: (layer.calibration ?? null) as Layer['calibration'],
  };
}

/** Every layer that has a picture, bottom first, and how many could not be shown. */
export async function loadLayers(
  tenant: string,
  layers: readonly LayerOut[],
): Promise<{ layers: Layer[]; failed: number }> {
  const results = await Promise.all(
    layers.map((layer) =>
      one(tenant, layer).then(
        (loaded) => ({ loaded, failed: false }),
        () => ({ loaded: null, failed: true }),
      ),
    ),
  );
  return {
    layers: results.flatMap((r) => (r.loaded ? [r.loaded] : [])),
    failed: results.filter((r) => r.failed).length,
  };
}
