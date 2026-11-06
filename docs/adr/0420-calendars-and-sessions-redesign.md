# 0420 - Calendars and Sessions, redesigned

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/calendars-sessions](../design/web/calendars-sessions/README.md), CS1 to CS7. Follows [RFC 0046](../rfcs/0046-sessions-scenes-and-lived-order.md) and [RFC 0028](../rfcs/0028-time-causality-and-calendars.md).

## Context

Calendars and Sessions share data (a Session starts in a period; an Event is presented in a Session) but not a place. The maintainer asked for them to be designed together.

## Decision

- **Two apps, linked by data** (CS1), each with its own Home. A Session links to its starting period and the periods it covers; a calendar day lists the Sessions that start or cover it; an Event lists where it was presented. The status bar shows the in-world date of the Session being looked at and nothing elsewhere. There is no campaign-wide "now".
- **The month is the main view** (CS2, CS6), a calm grid with the day panel docked beside it (a sheet on a narrow window) and a strip of segments above; a year view is second. A month cell shows the moon, up to two marks and "+N".
- **The time filter is one shared component** (CS2, CS7): a line of time that any list or map can be looked at through. It is built once and shared; Maps' date lens is its first user. It keeps a density mark for every marked day.
- **Events are a tab of Calendars** (CS3), with participant, causal and story-order filters; "Order and causes" opens from an Event. Clocks are a tab shown only when the library has clocks.
- **A Session is one page of regions** (CS4, CS6): details, roster, notes, references, game time, Scenes, played record, campaign order and lived order. There is no bar of switches: a View menu lists the views and the parts, regions fold, and a line at the foot says what is hidden. **Prepare** and **Played** are saved views of those switches, not modes, and a Session opens in Prepare each time (CS7). Hiding a region hides only the drawing. Scenes and lived order are tabs of Sessions.

## Consequences

- The time filter is a candidate for `apps/brand` and is listed in the design's follow-ups.
- A date is never inferred; a Session or a period with no date behaves as if time did not exist.
