// Copies apps/brand's own files into this package (gitignored, never
// hand-edited - see ADR 0098 and this package's own README). A plain
// node script, not a shell `cp`, specifically so `pnpm run build` is
// self-sufficient: Cloudflare Pages' build command is a bare
// `pnpm install && pnpm run build`, with no mise in the picture at all,
// so anything a consuming app's own build depends on has to work without
// mise ever running (confirmed the hard way - see apps/inventory-web's
// own build failure this fixed). mise's `build` task now just calls this
// same script, so there's exactly one implementation of the copy, not a
// shell version and a node version that can drift apart.
import { cpSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const brandDir = join(pkgRoot, '..', '..', 'apps', 'brand');
const { files } = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'));

for (const file of files) {
  cpSync(join(brandDir, file), join(pkgRoot, file), { recursive: true });
}
