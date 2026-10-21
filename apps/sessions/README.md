# Lorenzo Sessions

Static Astro app for campaign Session planning, reusable Scenes and personal/shared notes.
RFC 0046, ADR 0317. Uses the shared brand, Authgear, typed API client and Information editor.

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

Set PUBLIC_API_BASE_URL, PUBLIC_AUTHGEAR_ENDPOINT and PUBLIC_AUTHGEAR_CLIENT_ID from .env.example.
Use Node/pnpm from the repository. `mise run //apps/sessions:dev` serves port 4326. The app owns
lint, test, build and test-e2e tasks; browser tests run against the real API and disposable DB.
No private bodies are persisted in browser storage. Appearance preference alone is remembered.

## Hosting

See docs/operations/sessions-setup.md. The planned Pages address is a fallback until configured;
all cross-app destinations are resolved through GET /app-links.

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
