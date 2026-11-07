# 0435 - Repository text updates for nested leaf Chapters

RFC 0047 W9d extends ADR 0430 and retains the structural locks and reviewer boundaries of ADR 0344.

## Decision

A copied leaf Chapter may accept direct manuscript text updates at any Chapter depth within an
Edition when its full copied path still matches locally and upstream. Each nested context records
all Chapter edges from the leaf to the Edition: stable Chapter/parent identities, following payload
anchors and positions, plus Edition and Book. References use source identities as in ADR 0430.

New copies capture nested contexts. Existing direct-Edition contexts keep their format and remain
usable. Older nested copies have no inferred baseline and remain comparison-only. A malformed,
cyclic or detached ancestor chain is ineligible; no recursive traversal depends on Python's stack.
Coverage, tellings and redirects involving the leaf or any ancestor, Edition or Book still refuse
acceptance. Chapters with children remain outside this slice.

The full current paths enter the review version. A move, reorder, changed anchor, new dependency or
removal at any ancestor requires a fresh review, and a path that differs from the copied baseline
cannot take text updates. No placement, ancestor text, grants or audiences are changed. Existing
keep/take, atomic history/backlinks, unsaved-draft and session-credit protections remain in force.
The accepted leaf text appears through continuous Edition reading at its existing location.

This remains explicit text acceptance in unchanged composition. Applying structural changes,
updating non-leaf manuscripts and shared tellings, and recovering legacy baselines are later W9 work.

## Validation

Exercise nested private/live and public/released copies with payload anchors, stale local and source
ancestor edits, remapped paths, missing legacy contexts, cycles and dependencies. Preserve direct
Chapter/standalone regressions. Verify nested acceptance, reload and continuous Edition reading in
the browser, including unsaved protection, session credit and phone accessibility.

## History

Renumbered from 0431 on 2026-11-07 after the parallel RFC 0051 implementation also
claimed 0431. Numbers 0432-0434 were already recorded or reserved. The decision is unchanged.
