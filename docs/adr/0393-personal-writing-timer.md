# 0393 - Personal writing timer

RFC 0047 W8b adds the optional timer agreed in ADR 0327, following personal length goals.

## Decision

An Author can open Writing timer inside Word count in Write, choose 1 to 1440 whole minutes,
and start, pause, resume or reset a countdown. The initial duration is 25 minutes. Completion
says Time elapsed quietly, without audio, notifications or assertions about words written.
The timer continues while its disclosure is closed or another entry in the same library is
open. It measures wall-clock time, including a suspended browser; changing the device clock
may change the remaining time. Net-new writing attribution is a subsequent W8 slice.

Keep one timer per API, signed-in account and library in this browser tab's sessionStorage.
Reload and navigation within the tab restore it after normal Author authorization. Another
tab has an independent timer, including when a browser initially clones its session storage.
Closing the tab ends its recovery lifetime. It is not synchronized between devices or tabs,
and it is not campaign Session data, manuscript content or repository content. No API/table
is introduced for a browser-tab timer. Only duration, remaining time and a deadline are stored.
Account changes never show another account's timer. Existing revocation/sign-out teardown
removes the visible controls. A storage failure leaves the timer usable in memory and visibly
states that reload recovery is unavailable; malformed stored state is ignored.

Use shared brand controls and existing disclosure layout without new CSS. Timer ticks update
only the time text, never replace the editor or move focus. Hide repetitive countdown changes
from live announcements; announce start, pause, resume, reset and completion once. Stop the
component's ticker when its authorized writing surface is removed. The deadline is the source
of truth, so delayed callbacks do not extend the timer.

## Validation

Exercise countdown, pause/resume, reset, elapsed deadlines, reload and entry navigation,
account isolation, storage failure, phone accessibility and editor focus with the real API.
Check pure state arithmetic with a controlled clock. Existing manuscript counts and private
targets must retain their behavior. Run Writing checks and affected CI before review.
