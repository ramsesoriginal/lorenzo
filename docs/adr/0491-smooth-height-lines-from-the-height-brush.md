# 0491 - Smooth height lines from the Height brush

Status: accepted, decided with the maintainer on 2026-11-17. Amends what [ADR 0480](0480-the-height-brush.md) writes. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps). Tracked in [#1267](https://github.com/ramsesoriginal/lorenzo/issues/1267).

## Context

The Height brush traces a line from a field of 128 samples across the sheet and writes it as a polyline of straight runs, so a hill drawn for a printed map shows its corners.

## Decision

- **A line the Height brush draws is a smooth curve.** The traced points are first thinned to within a quarter of a sample, as before, and the line is then written as one open bezier part through what is left: the curve the Spline tool draws ([ADR 0471](0471-the-spline-tool.md)), at its tension of 0.5. A line that closes on itself is a curve that closes smoothly, its first point also its last.
- **It is a height line as any other** ([ADR 0473](0473-the-height-line-tool.md)): the bezier carries its height and unit, is read back by the brush as it is drawn, and its points can be changed as a spline's.
- The height lines of Fill by marching squares are not changed.

## Validation and delivery

Unit tests: an open and a closed line through their points, smooth where a closed one meets itself, every point of the curve within a sample of the traced line, within the placement's limits. The browser test of the Height brush checks the parts written are bezier height lines.

## Excluded

Smoothing the lines of Fill by marching squares, the outlines of caves and fills, and lines drawn by hand.
