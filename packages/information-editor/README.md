# Information editor

Small framework-free controls for information bundles, shared by the apps that edit information.
The API remains the authority for editing and reading. See
[RFC 0044](../../docs/rfcs/0044-facts-audiences-and-information-bundles.md) and
[ADR 0304](../../docs/adr/0304-atomic-information-audiences.md). The controls take the app's
`LorenzoClient` from [`@lorenzo/api-client`](../api-client).

- `renderAudienceControl`: the audience editor. It inspects recipients only when opened. Saving
  replaces the explicit audience atomically with the version read when the control opened. A stale
  edit preserves the selection and asks the editor to reopen it. `audienceWithRecipients` is the
  normalisation it applies to a selection.
- `renderBundleEditor`, `renderInformationPayloads`, `validatePicture`: editing and reading a
  bundle's ordered text and picture payloads, and bounding an acquired image before it is staged.
- `saveInformationBundle`, `sameBundle`, `initialText` / `INITIAL_TEXT`: saving an ordered bundle
  without replacing unknown payloads or broadening its audience, and comparing contents. Types:
  `Information`, `Payload`, `DraftPayload`, `BundleFields`, `BundleReceipt`.

Run `mise run //packages/information-editor:test` and `:lint`.
