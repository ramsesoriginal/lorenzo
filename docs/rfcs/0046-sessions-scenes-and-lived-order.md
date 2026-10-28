# 0046 - Sessions, Scenes, play order and lived order

Status: accepted for the four delivery slices agreed with the maintainer on 2026-10-21, and built (2026-10-28).
Decisions: ADR 0317 (planning and collaboration), ADR 0318 (play records), ADR 0319 (lived order).
This narrows RFC 0028; it does not accept either original temporal candidate as a whole.

## Purpose

Give GMs a simple preparation and note-taking surface, and players their own notes on a
shared Session. Keep reusable narrative Scenes independent of their use in play. Record
presentation order separately from what a being lived and from Event causality.

## Agreed delivery

1. Session and Scene entries, entry-backed Scene appearances, campaign/GM/player/Character
   roster, optional dates, ordered preparation and Lorenzo Sessions, including Information.
2. Scene Fact/Event/Being relations, Session Fact/Event/period relations, reusable Scenes
   and independently permission-filtered references, including repository content support.
3. Explicit campaign Session order and played Scene/Event presentation records, separate
   from mutable preparation, with planned/played/skipped appearances.
4. Explicit lived-before assertions between existing Event participations, preserving
   provenance and constraining the existing guarded Event graph without implying causes.

Each is a tested API-and-app vertical PR, stacked after the documentation PR. No schema
or UI for later slices is built early merely to reserve space. Clocks, inferred learning,
branching/loops, repeated personal participation in the same Event and historical state
remain outside this delivery. No setting data is seeded.

## Boundaries

Calendar associations remain descriptive, not inferred intervals or proof of occurrence.
Session participation, Scene participation and Event participation are separate declarations.
References and played status grant no target visibility or Knowledge, and create no learning
or lived-order records. All three orders must survive an ordinary flashback without conflict.
