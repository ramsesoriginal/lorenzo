# Lorenzo Sessions

Static Astro app for campaign Session planning, reusable Scenes and personal/shared notes.
[RFC 0046](../../docs/rfcs/0046-sessions-scenes-and-lived-order.md), [ADR 0317](../../docs/adr/0317-sessions-scenes-and-collaborative-planning.md) (planning), [ADR 0318](../../docs/adr/0318-explicit-session-and-play-order.md) (play order) and [ADR 0319](../../docs/adr/0319-personal-lived-order-as-event-evidence.md) (lived order). Uses the shared brand, Authgear, typed API client and Information editor.

My sessions lists Sessions where you are an assigned GM or player. A Session has one campaign,
optional real-world date and in-world starting period, GMs and an initially empty player roster.
Players and their controlled Characters are selected separately. GMs create/reuse Scenes and
order their appearances. A reusable Scene and its Session appearance have separate audiences;
each appearance keeps this group's notes. Sharing an appearance does not open its Scene.

Notes offer Me and Session GMs or Session participants. Shared never means the whole library.
Existing administrators retain their access. Another campaign GM gains no Session-private notes
merely by GMing elsewhere. Removed roster members lose this route of access. Notes, references
and preparation order do not infer learning, lived order, causes or occurrence.

## Development

Copy `.env.example` to `.env` and set the Authgear endpoint and client id (`PUBLIC_API_BASE_URL` is optional). Use Node/pnpm from the repository.

```bash
mise run //apps/sessions:dev        # port 4326
mise run //apps/sessions:lint
mise run //apps/sessions:test
mise run //apps/sessions:build
mise run //apps/sessions:test-e2e   # real API on a disposable database, fake Authgear
```

No private bodies are persisted in browser storage. Appearance preference alone is remembered.

## Hosting

Deployed at <https://lorenzo-sessions.pages.dev/> on Cloudflare Pages; [docs/operations/sessions-setup.md](../../docs/operations/sessions-setup.md) records the setup procedure. Cross-app destinations are resolved through `GET /app-links`.

## Reusable Scene context

Open **Browse reusable scenes** from a Session to create or edit an independent Scene, its
link name and optional calendar period. Scene Facts, Events and participating Beings have
private relationships until explicitly shared. Readers must still see both entries. These
references never create Event participation or learning. Session references are shown separately
from Scene references; **Game time covered** selects existing calendar periods independently
of the Session start date. Session-specific notes belong to each appearance, not its reusable
Scene. Removing an appearance explicitly removes its notes and preserves the Scene.

## Recorded play

Recorded play keeps played and skipped appearances separately from preparation. A GM can
propose the outline as played, review the draft, then explicitly save. Later preparation edits
preserve the played record. Event presentations have independent identities and private
relationships until shared; readers still need access to both appearance and Event. Campaign
Session order is explicit, with unplaced Sessions preserved. GMs reorder only Sessions they
manage. Dates and play records never become Event-order evidence or learning history.

## Personal lived order

Follow **Personal lived order** to review a being's existing Event participations and explicitly
record lived-before assertions. Evidence starts private. A reviewed proposal can use permitted
played presentations as a starting point; repeated presentations name the same participation.
Reorder or omit participations before saving. The proposal saves atomically, rejects cycles and
never creates Event participation, causation or learning. Authoring retains Event-order manager
restrictions. Ordinary order rulings and each being's support remain independently removable.

## Page frame

The header, skip link, welcome, footer and theme toggle come from [`@lorenzo/app-shell`](../../packages/app-shell/README.md) over the shared brand ([ADR 0322](../../docs/adr/0322-calendars-and-sessions-share-a-header-and-the-brand-base.md)); `src/layouts/Base.astro` only names the product, its page links and its welcome text. At phone width the header shows the spark alone.

## What a save draws again

The Session page is drawn in regions (its head, details, roster, notes, references, game time, Scenes and each Scene card, adding a Scene, played order, Session order, lived order). A save reads the Session again, which moves its version for every panel, and then draws again only the regions it can have changed, each once its own data is ready: saving the details redraws the head and the details, a note redraws the notes, sharing or moving a Scene redraws its cards. What is being written in the other panels, and which panels are open, stays as it is. Adding or removing a Scene redraws the whole outline (a draft inside a Scene card is lost then), and a change in who may manage the Session draws the page again.
