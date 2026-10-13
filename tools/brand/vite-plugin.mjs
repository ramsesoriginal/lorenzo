import { createReadStream } from "node:fs";
import { readFile, realpath, stat } from "node:fs/promises";
import {
  dirname,
  extname,
  isAbsolute,
  join,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";

// tools/brand/vite-plugin.mjs -> repository root
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const sourceDir = join(repoRoot, "apps/brand");
const manifestPath = join(repoRoot, "packages/brand/package.json");

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".yaml": "application/yaml; charset=utf-8",
  ".yml": "application/yaml; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
};

function isWithin(parent, child) {
  const rel = relative(parent, child);
  return (
    rel === "" ||
    (rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel))
  );
}

/**
 * Serve canonical apps/brand assets at /branding/* during development.
 *
 * Production is unchanged: packages/brand and the consuming application's
 * build scripts remain responsible for copying assets into public/branding.
 */
export function lorenzoBrandDev() {
  return {
    name: "lorenzo-brand-dev",
    apply: "serve",

    async configureServer(server) {
      const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
      const entries = manifest.files;

      const allowedFiles = new Set(
        entries.filter((entry) => !entry.endsWith("/")),
      );
      const allowedDirectories = entries
        .filter((entry) => entry.endsWith("/"))
        .map((entry) => entry.slice(0, -1));

      function isPublished(path) {
        return (
          allowedFiles.has(path) ||
          allowedDirectories.some((dir) => path.startsWith(`${dir}/`))
        );
      }

      const realSourceDir = await realpath(sourceDir);

      // Reuse Vite's watcher, including any existing WSL polling settings.
      server.watcher.add(sourceDir);

      const reload = (file) => {
        const path = relative(sourceDir, resolve(file)).split(sep).join("/");

        if (isWithin(sourceDir, resolve(file)) && isPublished(path)) {
          server.ws.send({ type: "full-reload" });
        }
      };

      server.watcher.on("change", reload);
      server.watcher.on("add", reload);
      server.watcher.on("unlink", reload);

      server.httpServer?.once("close", () => {
        server.watcher.off("change", reload);
        server.watcher.off("add", reload);
        server.watcher.off("unlink", reload);
      });

      // Register before Vite/Astro's normal public-file middleware.
      server.middlewares.use(async (req, res, next) => {
        const rawPath = (req.url ?? "").split("?")[0];

        if (!rawPath.startsWith("/branding/")) {
          return next();
        }

        res.setHeader("Cache-Control", "no-store");

        if (req.method !== "GET" && req.method !== "HEAD") {
          res.writeHead(405, { Allow: "GET, HEAD" });
          res.end();
          return;
        }

        let assetPath;

        try {
          assetPath = decodeURIComponent(rawPath.slice("/branding/".length));
        } catch {
          res.writeHead(400);
          res.end("Invalid asset path");
          return;
        }

        // Prevent directory traversal and unauthorized files.
        const segments = assetPath.split("/");

        if (
          !assetPath ||
          assetPath.includes("\\") ||
          assetPath.includes("\0") ||
          segments.some(
            (segment) => !segment || segment === "." || segment === "..",
          ) ||
          !isPublished(assetPath)
        ) {
          res.writeHead(404);
          res.end("Brand asset not found");
          return;
        }

        const filePath = resolve(sourceDir, ...segments);

        if (!isWithin(sourceDir, filePath)) {
          res.writeHead(404);
          res.end("Brand asset not found");
          return;
        }

        try {
          // Resolve symlinks too, so they cannot escape the source directory.
          const actualPath = await realpath(filePath);

          if (!isWithin(realSourceDir, actualPath)) {
            res.writeHead(404);
            res.end("Brand asset not found");
            return;
          }

          const info = await stat(actualPath);

          if (!info.isFile()) {
            res.writeHead(404);
            res.end("Brand asset not found");
            return;
          }

          res.writeHead(200, {
            "Content-Type":
              contentTypes[extname(actualPath).toLowerCase()] ??
              "application/octet-stream",
            "Content-Length": info.size,
          });

          if (req.method === "HEAD") {
            res.end();
            return;
          }

          const stream = createReadStream(actualPath);

          stream.on("error", (error) => {
            if (!res.headersSent) {
              res.writeHead(500);
              res.end("Unable to read brand asset");
            } else {
              res.destroy(error);
            }
          });

          stream.pipe(res);
        } catch (error) {
          if (error.code === "ENOENT" || error.code === "ENOTDIR") {
            res.writeHead(404);
            res.end("Brand asset not found");
          } else {
            next(error);
          }
        }
      });
    },
  };
}
