# RFC: Facts, explicit audiences and information bundles

Status: accepted, decided with the maintainer on 2026-10-16.

## Context

Lorenzo records entries and authored information about them, with static knowledge grants
(ADR 0028). The maintainer wants tenant-wide canonical facts as entries, optional explicit
subjects, concealed existence and names, and consistent audience and image editing in the
existing apps. This resolves RFC 0001's campaign-facts question differently: these facts are
tenant-wide, not campaign-scoped. It does not adopt the proposed epistemic or temporal
systems of RFC 0029 and RFC 0028.

## Decision

A fact is an entry of kind `fact`: an information anchor for a statement the author declares
true. It may be about zero or many entries. The explicit about relation and LorenzoScript
references are independent. There is no adjudication, confidence or truth interpreter.

An entry's audience gates both its existence and displayed name. Its information has its own
explicit audiences. Reading information requires existing resource access, entry visibility
and information visibility. Editing an information audience never grants entry visibility.
One combined existence/name gate is sufficient; identities and aliases are later work.

Information is an ordered bundle of payloads. Initially editors author LorenzoScript texts
and images. All payloads share the information audience. A sketch with an explanation is one
bundle; the annotated GM version is another. Descriptions remain singleton information, not
singleton text payloads. Main pictures keep their existing special rule.

Every information editor exposes its audience to callers authorized to edit it. It supports
characters, groups and existing player grants, and explains privileged role access. Reading a
note is not permission to inspect its other recipients. Group access follows membership;
retained personal memory is not inferred.

Beings and inventory-web use small extensions of their existing description/note forms.
Bench keeps in-place text editing and its command/conflict model. Drop targets the information
under the pointer; paste and a quiet keyboard-accessible add button target the information
containing the caret. Images append last, independent of caret text position. Mobile notes
allow gallery selection and camera capture, with encrypted durable drafts and replay-safe
uploads through the existing queue.

## Delivery

1. ADR 0304: atomic audience inspection and replacement, then existing web controls.
2. Facts and the shared outer gate, enabled first for facts, including complete discovery
   protection and repository round-trip behavior; Bench authoring and facts-about views.
3. Multi-payload API and ordered rendering, then Beings and inventory-web editors.
4. Bench payload commands and image insertion; online-only bytes as ADR 0243/0255.
5. Mobile audiences, protected pictures, gallery/camera and durable attachment synchronization.
6. Entry gates for beings and physical inventory are separately scoped once their mechanics
   and indirect disclosures are decided; existing data retains current access meanwhile.

Each implemented slice records its ADR and has an issue/milestone and tested vertical flow.
Subsequent ADRs use this feature's reusable documentation branch. No new app or speculative
framework is needed. Shared web components are extracted only for actual consumers.

## Consequences

Most content storage and audience concepts already exist. Concealing an entry is a new API
boundary: names, slugs, lists/counts, previews, backlinks, related summaries and protected bytes
must all obey it, including cache validation and release reads. Manually authored prose that
spells a secret is not automatically redacted.

Defaults preserve existing entries and clients. New facts start restricted. Repository-local
recipients need explicit copy rules, not cross-tenant grants. Images preserve the configured
upload limit; mobile prepares legible, correctly oriented pictures rather than raising it.

## Not in scope

Truth verdicts, confidence, learning history, OCR, general native LorenzoScript parity, new
payload kinds, a new facts app, and persistent offline Bench editing remain separate work.
