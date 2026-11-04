// Builds a copy of the prototype that runs without the repository around it: one index.html with the brand CSS,
// the proposed tokens, the shell, the icon sprite and the scripts inlined, and the brand fonts beside it.
// Usage: node docs/design/web/prototype/build-review-copy.mjs OUT_DIR [--fragment]
// --fragment writes the page without the html, head and body tags, for a host that adds its own.
import { readFileSync, writeFileSync, mkdirSync, cpSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const brand = resolve(here, '../../../../apps/brand');
const args = process.argv.slice(2);
const fragment = args.includes('--fragment');
const out = resolve(args.find((a) => !a.startsWith('--')) || 'review-copy');
const read = (p) => readFileSync(p, 'utf8');

const css = ['normalize.css', 'tokens.css', 'fonts.css', 'base.css', 'motion.css'].map((f) => read(join(brand, f))).join('\n')
  + '\n' + read(join(here, 'proposed-tokens.css')) + '\n' + read(join(here, 'shell.css'));
const sprite = read(join(brand, 'icons.svg')).replace(/<\?xml[^>]*\?>/, '');
// The icon references point at the sprite inside the page instead of at a file.
const js = ['data.js', 'core.js', 'pages.js', 'app.js'].map((f) => read(join(here, f))).join('\n').replaceAll('../../../brand/assets/', 'assets/').replace("const ICONS = '../../../../apps/brand/icons.svg';", "const ICONS = '';");

const body = `<div style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">${sprite}</div>
<div class="proto-bar" id="proto" role="region" aria-label="Prototype controls"></div>
<div class="stage"><div class="frame" id="frame"></div></div>
<script>
${js}
</script>`;
const html = fragment
  ? `<title>Web design prototype</title>\n<style>\n${css}\n</style>\n${body}\n`
  : `<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Web design prototype</title>
<style>
${css}
</style>
</head>
<body>
${body}
</body>
</html>
`;
mkdirSync(out, { recursive: true });
writeFileSync(join(out, 'index.html'), html);
cpSync(join(brand, 'fonts'), join(out, 'fonts'), { recursive: true });
mkdirSync(join(out, 'assets'), { recursive: true });
for (const f of ['lorenzo_horizontal_lockup_light_bg.svg', 'lorenzo_horizontal_lockup_dark_bg.svg']) cpSync(resolve(here, '../../../brand/assets', f), join(out, 'assets', f));
console.log('Wrote', join(out, 'index.html'), `(${Math.round(html.length / 1024)} KB) and fonts/ and assets/`);
