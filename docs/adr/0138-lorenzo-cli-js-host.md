# 0138 - The JS host: an embedded V8 in a token-free worker

Status: accepted

Slice 2 of [RFC 0025](../rfcs/0025-lorenzo-cli-mpmb-item-importer.md) (R1 of its cross-persona review, and its "spike before coding"). Builds on [ADR 0137](0137-lorenzo-cli-app-python-client-and-auth.md).

## Context

MPMB's additional-content files are executable JavaScript: `WeaponsList["longsword"] = {...}`, with RegExp literals, repeated keys, and calls to functions the sheet supplies. R1 decided to evaluate them in an embedded V8 (`mini-racer`) inside a disposable worker process that never holds a credential, behind a one-function engine protocol, and required a spike against the sheet's own data before building. This records what was built and what the spike showed, including where it changed R1.

## Decision

### The seam

`Engine.evaluate(EvalRequest) -> EvalResult`, both JSON-serialisable pydantic models (`lorenzo_cli.evalworker.protocol`). Anything with that method is an engine. `WorkerEngine` runs the real one in a subprocess; `V8Engine` is what runs inside it. A second engine (R1 names `pythonmonkey`, then a Node subprocess) would pass the same golden corpus and change nothing else.

### The worker

- `python -I -m lorenzo_cli.evalworker`: a plain subprocess, not `multiprocessing`. One request on stdin, one result on stdout.
- Its environment is built from scratch (`PATH`, `LANG`, `LC_ALL`, `SYSTEMROOT` only), so `LORENZO_TOKEN`, the stored login, and every other variable of the CLI stay out. It is started before login.
- The parent kills it after `wall_seconds` (60). Inside, each file gets `file_seconds` (20) and V8 a hard cap of `max_memory_mb` (64). `RLIMIT_CPU` is a Linux backstop; `RLIMIT_AS` is deliberately not set, since V8 reserves address space it doesn't use.
- It leaves with `os._exit`: `mini-racer`'s event-loop thread otherwise reports a finalization error on stderr during interpreter teardown.
- Bad requests, crashes and unreadable answers become one `EvalError`; a file that throws does not (see below).

### What a run does

1. Evaluates the **base** files (the sheet's own data), which define `Base_WeaponsList`, `Base_ArmourList` and the like.
2. **Initiates the lists** as the sheet's `InitiateLists()` does before any user script: each list becomes a deep copy of its `Base_` list, or is empty.
3. Evaluates the **content** files in the order given, all in one context.

Step 2 is not in R1; the spike found it necessary (below).

- **Names the sheet supplies.** A `ReferenceError` for a name this host lacks (`What`, `tDoc`, `app`...) adds a recording stub and restarts the run in a fresh context, at most `max_stub_retries` (100) times, and reports the stubs. A stub is a `Proxy` that absorbs any call, property read, write or `new` and returns itself, so `Value("a").b.c("x")` works.
- **Determinism.** `Math.random` returns 0.5 and `Date` is fixed at the epoch, so a run is a pure function of its input.
- **A file that throws** is reported against that file. What it defined before the error stays, and the next file still runs. An endless loop or a memory hog is stopped for its file only.
- **Tagged JSON.** A `RegExp` returns as `{"$re": [source, flags]}`; a function as `{"$fn": text}` and is never called; a value out of a stubbed call as `{"$stub": name}`, with its path listed in `stubs_in_data`; `NaN` and `Infinity` as `{"$num": ...}`; a `Date` as `{"$date": ms}`; a throwing getter as `{"$error": ...}`; a cycle as `{"$cycle": true}`. Repeated keys resolve as JavaScript does (the last wins). `lorenzo_cli.evalworker.tagged` is the only code that knows the tags.
- **Origins.** The result names the file each entry of each returned list came from: the last file that put a new object under the key, or the base file that defined it. A file that patches an entry in place does not take it over. RFC 0025 R4's per-file namespaces and "later file wins" need this.

### Tools

`lorenzo inspect [--base FILE...] FILE...` shows the files, per-list counts and origins, stubs, and any value a stub reached, without touching a tenant. `--json` prints the whole result. It exits 1 if any file failed.

### The golden corpus

`tests/corpus/<case>/` holds fixtures written for this repository in the shapes of the upstream templates, and an `expected.json` per case that the worker's output must equal. That, not the engine, is the contract. `LORENZO_UPDATE_GOLDEN=1` rewrites them after a deliberate change. The upstream repository and the sheet's data are GPL-3.0 and are **not** copied here; `tests/test_evalworker_upstream.py` runs against a local clone when `LORENZO_UPSTREAM_CORPUS` points at one.

## The spike

Run against `morepurplemorebetter/MPMBs-Character-Record-Sheet` at `076507d` (2026-09), on Linux under WSL, Python 3.14.6, `mini-racer` 0.14.1.

| Question (from R1) | Result |
| --- | --- |
| The sheet's own SRD data in one ordered context | `ListsSources.js`, `Lists.js`, `ListsGear.js`: 84 weapons, 14 armours, 107 gear, 11 packs, 37 tools, 16 ammunition, 6 sources. 12 stubbed names, 12 restarts. |
| Wall time | About 1.1 s for the whole worker, startup included, from a checkout on `/mnt/c`. Every restart together is a small part of it. |
| Peak heap | 0.9 MB live after the SRD run; 7.4 MB with every `_variables/*.js` file loaded (317 spells, 239 magic items, 131 creatures...). The 64 MB cap has a wide margin. |
| `$fn` on items | None on the SRD's weapons, armour, gear, packs, tools or ammunition. 98 `RegExp` attributes. No stub reached the data. |
| Chained call on a stub (`X("a").b`) | Works; the result is a stub, marked `$stub` if it reaches the data. |
| Stub-retry bound | 12 needed for the SRD, 16 for everything. 100 is generous, and each restart is cheap. |
| Limits work | An endless loop is stopped by `timeout_sec`; a memory hog is stopped by `max_memory`. `timeout=` on `mini-racer`'s `eval` is **milliseconds** and deprecated, so the code uses `timeout_sec`. |

Three findings changed the design:

- **Homebrew is written against lists that already hold the SRD.** `Expanded Armory & Gear`, a real homebrew file, does `WeaponsList["x"].regExpSearch = ...` on SRD entries. Run without the SRD it fails with a `TypeError`; run with a base phase it adds 29 weapons and 4 packs on top of 55 and 7 from the SRD. Hence the base files and the list initiation.
- **Provenance is needed, not optional.** With both in one list the importer must know which file an entry came from (R4's namespaces), so origins are part of the result.
- **The sheet supplies functions, not just constants.** `Kibbles Compendium of Craft and Creation` (452 KB) throws part-way even with all the sheet's data loaded, because it reads results of sheet functions such as `AddSubClass` that are stubs here. That is spells, classes and magic items, outside RFC 0025's scope, and it is reported per file and never silent. It bounds what "evaluate" means: an item attribute computed from a sheet call comes back as `$stub`, which the importer (slice 4) must treat as unknown.

## Consequences

- `mini-racer` is a dependency (a wheel of about 80 MB that bundles V8). Linux, including WSL, is the supported target; native Windows is untested.
- The sheet's data is not shipped with Lorenzo (GPL-3.0). To import the SRD items, or homebrew that patches them, the person supplies the sheet's `_variables` files as `--base`. How the SRD import itself is offered is for slice 4.
- A per-file failure doesn't stop a run, so callers decide whether it is fatal. `lorenzo inspect` treats it as failure (exit 1); the importer will treat an unresolved file as review-queue material rather than guess.
- The worker's start-up (about a second on a slow filesystem) is paid once per run.
