# Information editor

Small framework-free controls for information bundles, shared by Beings, inventory-web and
Bench. The API remains the authority for editing and reading. See RFC 0044 and ADR 0304.

`renderAudienceControl` inspects recipients only when opened. Saving replaces the explicit
audience atomically with the version read when the control opened. A stale edit preserves the
selection and asks the editor to reopen it. Role-based access is explained separately.

Run `pnpm test` and `pnpm lint` from this package.
