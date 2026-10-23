# Lorenzo Writing

A quiet writing surface for library and repository Authors. The first slice uses existing
Scenes as standalone drafts with a designated manuscript Information bundle: LorenzoScript,
ordered pictures and text, conditional autosave, per-account browser draft recovery and saved
server revisions. Descriptions and notes stay separate. See RFC 0047 and ADRs 0327–0329.

Books, Editions, Chapters, tellings, Carriers and the subsequent workflow slices remain in
[the accepted proposal](../../docs/rfcs/0047-lorenzo-writing.md); this app does not claim them yet.

## Run and verify

- `mise run //apps/writing:dev` — port 4327.
- `mise run //apps/writing:lint`, `:test`, `:build` — normal app checks.
- `mise run //apps/writing:test-e2e` — real API, isolated Postgres database, fake Authgear.
  Set `E2E_BROWSER_CHANNEL=msedge` to use installed Edge locally.

The app uses the shared brand, app shell, API client, LorenzoScript editor and Information
bundle editor. No app-specific CSS. `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT`,
`PUBLIC_AUTHGEAR_CLIENT_ID` and optional `PUBLIC_BRANDING_CSS_URL` configure the build.

Unsent drafts (including image Files) live in IndexedDB, separately by API/account/library/
manuscript and editor session. They survive closing a tab. Local drafts are opened only after
the server authorizes the current editor; signing out clears the visible page, not that account's
pending recovery. Storage failure warns to keep the tab open. Concurrent server edits stop
autosave and require an explicit choice. This is not offline browsing or live collaboration.
Server revisions contain prior content, never old sharing grants; deleting Information deletes
its history. This screen does not offer that destructive action.

Hosting is **not configured or deployed**. Follow [the setup guide](../../docs/operations/writing-setup.md).
