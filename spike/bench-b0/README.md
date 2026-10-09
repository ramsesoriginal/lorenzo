# Bench B0 spike (throwaway)

[RFC 0039](../../docs/rfcs/0039-bench-authoring-offline-and-extensibility.md) slice B0. **Never merged**: this branch exists so the findings in the RFC's "What was tried" can be reproduced. It is not `apps/bench`.

```bash
cd spike/bench-b0 && npm install
npm test                 # builds, starts the stub API, runs 18 Playwright tests in Chromium
npm run export-size      # (the export-size spec runs inside `npm test`; numbers go to findings/findings.ndjson)
```

- `src/` the client: own signal helper, IndexedDB store, command model, outbox runner (Web Locks), light-DOM custom elements. No framework.
- `scripts/server.mjs` a stub of W1 (checked writes), W2 (client ids, replay) and W3 (cursor-paged gzip export, revision ETag).
- `scripts/gen.mjs` a **simulated** repository: the real seed could not be built where this ran (no Docker or Postgres).
- Not covered: a service worker, the real API, a phone, names-first/lazy bodies.
