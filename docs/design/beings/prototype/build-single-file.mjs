// Builds one self-contained HTML file from the prototype, to open from anywhere (an email, a
// published page) without serving the repository. It inlines what index.html links: apps/brand's
// stylesheets, the icon sprite and the two lockups, plus sheet.css, data.js and app.js.
//
//   node docs/design/beings/prototype/build-single-file.mjs OUT.html
//
// Nothing is copied into the repository; the output is for sharing.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../../../..");
const out = process.argv[2];
if (!out) {
  console.error("usage: build-single-file.mjs OUT.html");
  process.exit(1);
}

const read = (...p) => readFileSync(join(...p), "utf8");
const brand = (f) => read(root, "apps/brand", f);
const css = [
  "normalize.css",
  "tokens.css",
  "base.css",
  "layout.css",
  "components.css",
  "motion.css",
]
  .map(brand)
  .join("\n");
const dataUri = (f) =>
  "data:image/svg+xml;base64," +
  Buffer.from(read(root, "docs/brand/assets", f)).toString("base64");

let html = read(here, "index.html");
const body = html.slice(html.indexOf("<body>") + 6, html.indexOf("</body>"));
const title = /<title>(.*?)<\/title>/.exec(html)[1];

const page = `<title>${title}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Newsreader:wght@400&display=swap">
<style>
${css}
${read(here, "sheet.css")}
</style>
<script>
  // "System" theme sets nothing on the root element; the brand tokens only know [data-theme].
  if (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.dataset.theme = "dark";
  }
</script>
<div hidden>${brand("icons.svg")}</div>
${body
  .replace(/<script src="[^"]+"><\/script>/g, "")
  .replace(
    "../../../brand/assets/lorenzo_horizontal_lockup_light_bg.svg",
    dataUri("lorenzo_horizontal_lockup_light_bg.svg"),
  )
  .replace(
    "../../../brand/assets/lorenzo_horizontal_lockup_dark_bg.svg",
    dataUri("lorenzo_horizontal_lockup_dark_bg.svg"),
  )}
<script>
${read(here, "data.js")}
</script>
<script>
${read(here, "app.js")}
</script>
`;
writeFileSync(out, page);
console.log(out, Math.round(page.length / 1024) + " KB");
