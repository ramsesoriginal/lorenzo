// Copies @lorenzo/brand's published files into public/branding/, so the
// default same-origin PUBLIC_BRANDING_CSS_URL (see src/lib/config.ts and
// ADR 0098) has something to actually serve without any new runtime
// dependency. Runs before both `astro dev` and `astro build` (package.json).
//
// fs.cpSync (not a shell `cp -r`) specifically to stay cross-platform - see
// ADR 0098's own "Gotcha hit building packages/brand's build task on
// Windows" note about shell-builtin portability traps.
import { cpSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
// @lorenzo/brand's own package.json isn't in its `exports` map (only the
// individual stylesheets/assets are) - resolve one of those instead and
// read package.json off the filesystem directly, bypassing exports
// resolution rather than fighting it.
const brandDir = dirname(require.resolve('@lorenzo/brand/tokens.css'));
const { files } = JSON.parse(readFileSync(join(brandDir, 'package.json'), 'utf8'));

const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'branding');

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

for (const file of files) {
  const from = join(brandDir, file);
  const to = join(outDir, file);
  cpSync(from, to, { recursive: true });
}
