import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts", "src/migrate.ts", "scripts/register-commands.ts"],
  format: ["esm"],
  target: "node22",
  platform: "node",
  outDir: "dist",
  clean: true,
  sourcemap: true,
  // Bundling (rather than a plain tsc emit) is what lets source files use
  // extensionless-friendly relative imports under "moduleResolution":
  // "bundler" while still producing output `node` can run directly - esbuild
  // resolves and rewrites these at bundle time, so there's no NodeNext-style
  // ".js on every relative import" bookkeeping to maintain by hand (ADR 0029).
  splitting: false,
  skipNodeModulesBundle: true,
});
