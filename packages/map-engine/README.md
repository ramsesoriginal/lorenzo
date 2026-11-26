# lorenzo-map

The one validator of Lorenzo map systems and geometry (ADR 0336, ADR 0337). Pure Python, no database. It also holds the theme names (ADR 0352), the grid kinds, cells and the one
hex convention (ADR 0354, 0355) with their golden files, the view of a Map, and a sphere's
longitude and latitude, its geometry rule and its projection (ADR 0357), and a layer's calibration and opacity (ADR 0361).
The straight-line distance between two positions on a Map is a pure function here too (ADR 0366), in the
author's own unit and never converted, with a `metric` on square and rectangular systems and a golden file the
tests hold it to.

Run `mise run //packages/map-engine:test` (pytest) and `:lint` (uv lock check, ruff check and format check, mypy over `src`); `:build` is `uv build`.

## What it exports

`lorenzo_map` re-exports its public names from `__init__.py`. The validators are `validate_system`, `validate_geometry`, `validate_placement` (with `validate_z`), `validate_role`, `validate_style`, `validate_view`, `validate_calibration`, `validate_opacity` and `validate_theme_hint`; a refusal is a `MapDocumentError`. Around them are the closed lists (`ROLES`, `STROKES`, `WEIGHTS`, `GRID_KINDS`, `APERTURES`, `ORIENTATIONS`, `PROJECTIONS`, `METRICS`, `THEME_NAMES`, `WRITABLE_KINDS`), the format names (`SYSTEM_FORMAT`, `GEOMETRY_FORMAT`), the limits (`MAX_*`) and the pure functions for grids (`cell_at`, `cell_centre`, `cell_count`, `cell_polygon`, `in_grid`), spheres (`is_sphere`) and distance (`straight_distance`). `apps/api` is the one app that uses it (`lorenzo-map`, a path dependency, copied into its image); `packages/map-renderer` and `apps/maps` hold TypeScript counterparts to the same rules.

## Golden files

`golden/*.json` are the examples the Python and TypeScript sides are both held to; each file's `about` says what it holds and which ADR decided it. `geometry`, `geometry-sphere`, `system`, `themes`, `cells`, `cell-outlines` and `distance` are rules of this package, read by its tests (`tests/`); `caves`, `fills` and `collapse` are what the generators in `apps/maps` draw, and this package's tests check that the geometry validator accepts the geometry of `caves` and `fills`, and that the cells of `collapse` are cells of the grid. The TypeScript tests that read them are in `apps/maps/tests/unit` (`geometry`, `caves`, `fills`, `collapse`, `cell-outlines`) and `packages/map-renderer/test` (`cells`, `themes`).
