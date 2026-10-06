// What the API accepts as a profile picture (ADR 0056), so a person is told before the upload,
// not by a 422 after it. Pure and dependency-free like format.ts. The size is the API's
// `profile_picture_max_bytes` default; a server set differently still answers for itself.

const PICTURE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'] as const;
const PICTURE_MAX_BYTES = 2_000_000;

// For an <input type="file" accept>: the four types, so a picker doesn't offer an SVG.
export const PICTURE_ACCEPT = PICTURE_TYPES.join(',');

// Why this file can't be a profile picture, or null when it can.
export function pictureProblem(file: { type: string; size: number }): string | null {
  if (!(PICTURE_TYPES as readonly string[]).includes(file.type)) {
    return "That file type won't work. Use a PNG, JPEG, WebP or GIF.";
  }

  if (file.size > PICTURE_MAX_BYTES) {
    return 'That picture is over 2 MB. Choose a smaller one.';
  }

  return null;
}
