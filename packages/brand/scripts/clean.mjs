// Removes the files build.mjs copies in, so nothing generated is left on
// disk (mise's `clean` task, see ADR 0098 and this package's own README).
import { readFileSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pkgRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const { files } = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8'));

for (const file of files) {
  rmSync(join(pkgRoot, file), { recursive: true, force: true });
}
