# Lorenzo — Inventory Web

Static Astro frontend for browsing and moving character inventory — a kanban-style
board where columns are the containers a character owns and cards are item
instances, backed directly by the deployed [Lorenzo API](https://lorenzo-api-100817212329.europe-west1.run.app/openapi.json).
See [ADR 0004](../../docs/adr/0004-static-astro-frontend.md) (why this is a
static Astro app) and [docs/guides/adding-an-app.md](../../docs/guides/adding-an-app.md).

## Commands

Run from this directory, or via `mise run //apps/inventory-web:<task>` from the
repo root:

| Command          | Action                                    |
| ---------------- | ------------------------------------------ |
| `mise run dev`    | Start the dev server at `localhost:4321`   |
| `mise run lint`   | Biome + `astro check` + Prettier (`.astro`) |
| `mise run format` | Autoformat                                 |
| `mise run test`   | Run the test suite                         |
| `mise run build`  | Build the static site to `dist/`           |
