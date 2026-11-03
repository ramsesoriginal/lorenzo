# lorenzo-map

The one validator of Lorenzo map systems and geometry (ADR 0336, ADR 0337). Pure Python, no database. It also holds the theme names (ADR 0352), the grid kinds, cells and the one
hex convention (ADR 0354, 0355) with their golden files, the view of a Map, and a sphere's
longitude and latitude, its geometry rule and its projection (ADR 0357), and a layer's calibration and opacity (ADR 0361).
The straight-line distance between two positions on a Map is a pure function here too (ADR 0366), in the
author's own unit and never converted, with a `metric` on square and rectangular systems and a golden file the
tests hold it to.

Run `mise run //packages/map-engine:test` and `:lint`.
