# 0051 - Building on a repository you do not publish: include, protect, hide

Status: proposed (2026-11-06). The options below come from a conversation with the maintainer, who wants all of
them; the slices, the numbers and rules marked *proposed default* and the open questions are not decided yet. It
takes up the question [RFC 0038](0038-public-repositories-and-discovery.md) parks under "Later, not now:
pass-through grants for a private upstream", and replaces that sketch with the design below. It changes nothing
decided in RFC 0037 or RFC 0038 until a slice is accepted.

## Purpose

Let the Owner of a repository B make it public when something it is built on, A, is not, and say what a library
that copies B then gets of A. Today that is refused: a public repository needs every repository it is built on to
be public too ([ADR 0289](../adr/0289-the-flip-rules-and-the-bridge-skew-gate.md)), because a library cannot be
granted a private upstream by an Owner who never saw it ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)).
That is the right rule for a source that is public; it is the wrong one for a source its Owner wants to share only
through what is built on it: a rules text, a licensed base, a half-finished setting, a library of parts.

## Decided inputs

What the maintainer asked for, from the first conversation.

1. **A repository can be made public without its sources being public.**
2. **A source A can be private, protected, or public but unlisted**, as well as public as today.
3. **When B is made public over a source A, the Owner of B chooses one of three ways to carry A:** include it
   (flatten A into B), keep it separate and visible (show A's items), or keep it separate and hidden (hide A's
   items). Hidden items stay in the library and are still what inheritance resolves through.
4. **A's Owner can say "stay hidden"**, which leaves only include and hide for repositories built on A.

## Hard invariants

- **No new way in.** A repository can only be built on what its Owner can already read. Protecting A does not let a
  stranger build on it: building on A takes the grant A's Owner gives, as today.
- **A protected repository is not discoverable.** It is not in Discover, the facets, search or any storefront; a
  visitor's routes under `/repositories/{id}` answer as for a private repository; its profile and cover are not
  readable by a visitor.
- **A protected repository is read only as a step of another's copy.** A library never copies it alone
  (`409 repository-protected`), and reads it only while it holds a copy of a public repository that is built on it.
  Nothing else reads it.
- **One Owner's content is not re-published by another without a yes.** Including A in B needs the user to be an
  Owner of A or A's terms to allow it. A grant to read A is not that yes.
- **How A is carried is part of the release.** A release records it, a release is immutable, and changing it is a
  breaking change, because the rows a library holds change origin.
- **Hidden is a filter, not secrecy.** What a repository built on A inherits from A reaches the library as values
  on B's entries, and the rows live in the library's own tenant. Content that must stay out of every library has to
  be left out of the repository. GM-only text already travels in copies, with the Owner warned ([ADR 0290](../adr/0290-the-flips-as-routes-and-the-visibility-switch.md)); hiding does not change that.
- **The wall of [ADR 0002](../adr/0002-multi-tenancy-shared-schema-rls.md) stays tenant isolation by RLS.** Every
  new read path is `FOR SELECT`, narrow, written out where the policy needs it, and tested against the function
  that says the same rule, as ADR 0287 did for public.

## What this relies on and leaves alone

- **A bridge carries only what it authored; every copy link names an origin**
  ([ADR 0120](../adr/0120-bridge-repositories-and-dependency-manifests.md)). B's own tenant holds copies of A, with
  A as their origin. That is what makes flattening a choice made when the release is built rather than a rewrite of
  B.
- **A public repository is read through its current release document**
  ([ADR 0286](../adr/0286-the-read-switch-for-public-repositories.md)), and the document records the repositories
  it is built on. A flattened release records fewer.
- **The skew gate** ([ADR 0289](../adr/0289-the-flip-rules-and-the-bridge-skew-gate.md)): a public repository
  publishes only while it has taken the current release of everything it is built on. It stays, and for a flattened
  source it means the flatten is made from A's current release.
- **Grants and the copy engine** ([ADR 0118](../adr/0118-repository-tenants-subscriptions-and-a-gated-read.md),
  [ADR 0119](../adr/0119-copying-a-repository-into-a-tenant.md), [ADR 0121](../adr/0121-repository-updates-and-re-sync.md),
  [ADR 0287](../adr/0287-who-may-read-a-public-repository.md)): what a library gets of a step, the collision list
  and the update engine are unchanged; this RFC changes which steps a manifest has, and how a row of a step
  reads.
- **Publisher, quotas, cooldown, delist and retire**
  ([ADR 0298](../adr/0298-quotas-on-a-repository.md), [ADR 0299](../adr/0299-what-a-public-repository-says-about-its-publisher-and-hides-about-its-libraries.md),
  [ADR 0301](../adr/0301-release-fan-out-and-cooldown.md), [ADR 0303](../adr/0303-operator-delist.md),
  [ADR 0384](../adr/0384-deprecating-a-repository.md)) apply to a protected repository as they do to a public one,
  except where a rule below says otherwise.
- **The review element** ([ADR 0389](../adr/0389-the-shared-review-element.md)) takes plain labels, so the update
  inbox can show a hidden row without its name.
- **Not changed:** a private B built on a protected A. Libraries reach a private repository by invitation, and A's
  Owner invites them too, as today.

## Design

One ADR per slice, numbered when the slice is decided.

### The three decisions

| Decision | Whose | Values |
| --- | --- | --- |
| How far A reaches | A's Owner | private, protected, public (listed), public unlisted |
| How A may be used | A's Owner | which of include, show and hide a repository built on A may choose: its **terms** |
| How B carries A | B's Owner, for each repository B is built on | include, show, hide, within A's terms |

**Terms.** Three settings on the profile, each on or off: *may be shown*, *may be hidden*, *may be included*. The
screen offers two presets and the three switches under them: **Open** (all three) and **Stay hidden** (hidden and
included, not shown). *Proposed default:* a protected repository is Open; a public one cannot forbid show, because
anyone can copy it, so only *may be included* is its own setting and it starts on; a private one starts with
*may be included* off, which makes include available only to its Owners.

**B's choice.** A column on B's copy record of A, `inclusion`, one of `show` (the default, today's behaviour),
`hide` or `include`. B's Owner sets it in Studio and it is read when a release is made. A release's document
records the choice for every repository B is built on, as it records the set today.

### H1. Include A in B at release (flatten)

The cheapest of the four and it needs no new visibility. When a release of B is made with `inclusion = include` for
A, the document is built with B's copies of A taken as B's own rows: the copy links to A are left out, and A is
not among the repositories the release is built on. B's tenant is unchanged and keeps its live copy of A, so B's
Owner goes on authoring on top of it and taking A's updates; only the published document is flat.

- **What is included.** Everything B's copy of A holds that the document carries today, which is what a library
  would get of A as a separate step plus B's own edits to it, which ADR 0120 otherwise leaves out of what
  libraries get. A flattened release is therefore a different set of rows from a separate one.
- **Gates change with it.** The checks that read B's copy records (`built_on_not_public`, `public_dependents`, the
  skew gate) read the choice: an included source is not a dependency for the stack rule, and still has to be
  current for the flatten, so B cannot flatten a stale copy. Making A private is not refused for a dependent that
  includes it.
- **Consent.** `include` is offered when the user is an Owner of A or A's terms allow it, and refused otherwise
  (`409 repository-not-includable`, naming A). The Make public dialog says what including does and asks for the
  terms line of ADR 0299 to cover it.
- **Attribution.** B's storefront says what it includes and under which licence, taken from A's profile. A's
  Owner still sees B among A's dependents, since the owner's list ([ADR 0204](../adr/0204-the-owner-sees-who-copied-a-repository.md))
  reads B's copy record, which an included copy leaves in place.
- **No shared identity.** Two repositories that each include A give a library two sets of A's rows with different
  origins; the copy engine's collision list resolves the overlap. Re-targeting a flattened row to a library's
  existing copy of A is not built (open question 3).
- **Changing the choice is a breaking release**: the detector marks it, and the Make public dialog and the release
  composer say why.

*Slice H1:* the `inclusion` column and the terms on the profile, the document builder and the gates reading the
choice, the include option in Studio's built-on card and in the Make public dialog, attribution on the storefront,
the breaking-change rule, tests (API, hub real-API, 375px).

*Built as [ADR 0431](../adr/0431-including-a-repository-in-the-release-of-one-built-on-it.md).* The RFC stays the
spec; where the build differs, it says so here:

- **Terms.** H1 builds the one switch, *may be included*, and stores nothing for a default: null is the default for
  the repository's visibility (private no, public yes) and an Owner's value wins. The other two switches and the
  presets come with H3 and H4; `inclusion` allows `show` and `include` only until H4 widens it.
- **The breaking rule** is a second list beside the detector's, not a reason of it: a new reason would change a
  response enum of the contract, which the contract's diff calls breaking. `inclusion_changes` is each repository
  whose choice differs from what the current public release recorded (`repository_profile.release_sources`); a
  publish with any, like one with detector hits, needs `acknowledge_breaking`, and the release is marked breaking.
- **Consent is asked once, when the choice is set**, and not again when a release is made (the maintainer's
  decision). A's Owner changing its terms later affects only choices made afterwards, not an existing choice and
  not the release of the repository that already made it.
- **Attribution** is taken from a snapshot of A's name and licence written into the release (and kept on the
  profile for the storefront), not read from A's profile, which may be private.
- **The choice is read** from the list of repositories a repository copied, the flip check and the Owner's list of
  who copied it; the library's dependencies read (ADR 0198) is unchanged and has no step for an included
  repository.

### H2. Public but unlisted

A flag on the profile, `listed`, true by default and settable by an Owner of a public repository. Discover and its
facets add one condition (`discover.listed()` and the listing's policy); the storefront and the copy by address
work for anyone signed in who has the address; search never returns it. Every gate of a public repository stands:
summary, terms line, release, quotas, cooldown, delist, retire. Studio's visibility card gains "List on Discover".
It stands alone and is the smallest of the four.

*Slice H2:* the column, the condition, the toggle, the storefront's "not listed" note for its Owners, tests.

### H3. Protected (show)

A third value of `visibility`. A protected repository has a profile (no summary or cover required, none shown) and
a first release made as the flip is made, as a public one has, since a library reads it through its release
document.

- **Flips.** Private to protected is atomic with the first release, as private to public is. Protected to private
  is refused while a public repository is built on it with `inclusion` other than `include`
  (`409 public-repositories-built-on-it`), and the libraries that read it through one lose that path when the last
  such repository goes. Protected to public needs the summary and the terms line, as private to public does; public
  to protected removes it from Discover and ends the visitors' reads.
- **The stack rule.** Every repository B is built on is public, protected or included. `built_on_not_public`
  becomes "not reachable", naming each repository that is private and not included, and whether the user may
  include it. A protected repository's own sources follow the same rule.
- **The gate.** `repository_read_tenant_id()` and the profile and subscription policies gain one case: a
  protected, published repository is readable for the copy and update of a library that holds, or is copying, a
  public repository whose release lists it. It is read only through `reading_repository` with the repository the
  reader is going through, never ambient, and never by the visitors' routes. *Proposed default:* the rule is
  checked at read time against the libraries' copy records, so a library's access ends when its last qualifying
  repository does, with no revocation fan-out; the library's own subscription row has `source = protected` for
  listing. The ADR settles the exact predicate and the recursion hazard ADR 0287 found in the profile policy.
- **The copy plan.** A protected repository is a step of a manifest and never its head; the plan marks it
  "protected" and the copy of a public repository inserts the library's grant for it as for any step. The Shelf and
  the hub's built-on lists say "a protected repository", naming it only where its terms allow (open question 2).
- **What A's Owner sees.** The dependents list of ADR 0204 shows the public repositories built on A and the
  libraries that hold it through them, as it shows copies today.
- **Updates.** A release of A is announced to the libraries that hold it, as today; the skew gate makes each public
  repository built on A take it before it releases again.

*Slice H3:* the visibility value and its migration (gate, policies, constraints in one, as ADR 0303 and ADR 0384
did), the flips, the stack rule, the copy plan, the read at read time, Studio's visibility card and built-on card,
Shelf's pill, tests across every reader and every state (visitor, library through a public repository, library
with an invitation, member, operator; protected, public, private, retired, delisted).

### H4. Hide A's items

`inclusion = hide` marks the rows a library holds from A as hidden for that library: left out of entry lists,
search, pickers, previews, graph and map drawings and direct links, and read-only. They are still there for
inheritance, effective values, formulas and the updates that touch them.

- **Where the flag lives.** On the copy link of each row, which every copied row already has (ADR 0120), set at
  copy and at update from the choice of the repositories that bring the row. *Show wins:* a row is hidden only when
  every repository the library holds that brings it hides it.
- **Reads.** One place decides, the entry audience of [RFC 0044](0044-facts-audiences-and-information-bundles.md):
  a hidden row is an entry no library member can read. A spike settles whether that fits, and in particular that
  the effective-stat views, the inheritance edge and the provenance of
  [ADR 0276](../adr/0276-where-a-stat-value-comes-from.md) still resolve through such an entry; if they cannot, the
  filter goes in the entity reads instead and every client that lists entries is checked for the leak.
- **What the library sees of a hidden ancestor.** An inherited value reads as before, with its source named
  "a hidden entry".
- **Updates.** A release that changes hidden rows reaches the library as a count and a label ("3 changes to hidden
  entries"), applied with the rest; a breaking change among them is acknowledged as one line. The review element
  takes the label as plain text, so the inbox draws it without a name.
- **Deletes.** A library cannot delete a hidden row. When nothing visible refers to it and no repository it holds
  brings it any more, it is removed with the update that drops it (open question 4).
- **Exports.** The export and the CLI's reads honour the flag; a hidden row is not in a library's export.

*Slice H4:* the spike, the flag and its derivation, the read filter, the inbox and provenance wording, the exports,
every client that lists entries (Bench, Beings, Sessions, Maps, Calendars, Social, Writing, Inventory, the CLI),
tests per client.

### Combinations

- **One library, two repositories with different choices.** B hides A, C shows it: A's rows are visible, by show
  wins. B includes A, C does not: B's included rows and C's A rows overlap, and the collision list decides.
- **A public A and `hide`.** Allowed and cosmetic: A is copyable by anyone, so hiding only tidies one library. It
  is offered, and the dialog says so.
- **Different repositories, different choices.** B may include A while C, built on A, shows it. A's Owner sees
  each dependent and the choice it made in the dependents list.

## For the interface design

### Words (use these)

| On screen | Meaning |
| --- | --- |
| **Protected** | Not listed or copyable on its own; only repositories built on it reach it |
| **Listed on Discover** | The toggle of a public repository |
| **How repositories built on this one may use it** | A's terms: *Open*, *Stay hidden*, and the three switches *May be shown*, *May be hidden*, *May be included* |
| **Include in this repository** | B's choice `include`: its entries become this repository's own |
| **Keep separate and visible** | `show` |
| **Keep separate and hidden** | `hide` |
| **a hidden entry** | the name of a hidden ancestor in a provenance line |
| **Changing how this is included makes a breaking release** | The note on the choice, after the first public release |

Library, repository, release, Owner, entry, copy, "built on" are used as ADR 0194 has them; the screens never say
tenant, grant, subscription, flatten or source.

### Screens

- **Studio, visibility card:** private, protected or public, and for public the "Listed on Discover" toggle; the
  readiness list says what each choice needs.
- **Studio, built-on card:** each repository this one is built on, its state, the choice among the modes A's terms
  allow, and why one is not offered.
- **Studio, profile:** A's terms, under the visibility card, for an Owner.
- **Make public dialog:** the built-on list with a choice for each, the effect of each in a sentence, the terms
  line.
- **Shelf:** a "protected" pill on a repository a library holds through another, and a note that it cannot be
  copied alone.

## Delivery

| Slice | What | Needs | Touches |
| --- | --- | --- | --- |
| H1 | Include A in B at release; A's terms; the choice column; attribution. **Built**, [ADR 0431](../adr/0431-including-a-repository-in-the-release-of-one-built-on-it.md) | RFC 0037 R5 to R8, ADR 0385 | api, hub |
| H2 | Public but unlisted | RFC 0038 D3 | api, hub |
| H3 | Protected: the value, the flips, the stack rule, the gate, the copy plan | H1 (terms, the choice), ADR 0287, ADR 0289 | api, hub |
| H4 | Hide A's items | H3, the spike | api, hub, bench, beings, sessions, maps, calendars, social, writing, inventory, cli |

H1 and H2 are independent of each other and of the rest. H1 alone answers "B public without A public" when A's
Owner agrees. H3 adds shared identity and updates from A. H4 is optional and is decided after H3 has been used.

## Not in scope

A private repository's pass-through (a named bridge passing A's access to the libraries its Owner invites); a
per-entry "internal" flag inside A; re-targeting a flattened row to a library's existing copy of A; any secrecy
guarantee against a library's Owner; licence checking beyond showing A's licence; protecting a repository from a
library that holds it by invitation; an Owner asking A's Owner for the three switches from inside Lorenzo.

## Open questions

Each is settled in the ADR of the slice that needs it.

1. Whether *may be included* has a fourth preset, "Sealed" (hidden only, never included), or stays a switch.
2. Whether B's storefront and Shelf name a protected or a hidden source. *Proposed default:* an included source is
   always named, with its licence; a protected one is named only where its terms allow.
3. Whether a flattened row is re-targeted to a library's existing copy of A, which would give shared identity after
   flattening.
4. What happens to hidden rows nothing visible uses: removed with the update that drops them, or kept.
5. Whether hiding rides on RFC 0044's audiences or needs its own filter, decided by H4's spike.
6. Whether changing a repository's choice before its first public release is free (*proposed default*) or already
   breaking.
7. Whether hidden rows count toward a library's entry limit. *Proposed default:* they do not, as the copy engine's
   rows do not for a repository's quota.
8. Whether the three presets are enough names, and whether "Stay hidden" is the word.

## Alternatives considered

- **Pass-through grants for a named bridge** (RFC 0038's sketch): A's Owner allows a named repository to pass A's
  access on. It gives A's Owner control per bridge and costs a second route to a grant through a bridge, a manifest
  that changes with the bridge and revoke rules for each pair. Protected reaches the same libraries through the
  grants A's Owner has already given (building on A takes one), with a single new state.
- **Hide without protect:** public, unlisted and hidden only. A's content is then copyable by anyone with the
  address, which is what the Owner of a protected source does not want.
- **A repository-wide "internal" flag only:** no per-bridge choice, one mode for every repository built on A. It is
  simpler and cannot say "include for B, show for C".

## Consequences

Easier: a repository whose sources the Owner does not want public can still be public; a rules text can be built
on by many repositories and read by none directly; including a source needs no new visibility; the stack rule and
the skew gate keep their meaning.

Harder, and accepted:

- A protected repository adds a second opening in the wall of ADR 0002, narrower than public's, and every reader
  and state of it has to be tested.
- Hiding is not secrecy, and the screen has to say so; the leak through inherited values and the update inbox is
  designed in, not fixed.
- A release's document records how each source is carried, and changing that is a breaking release.
- A flattened source gives up live updates from A and shared identity across repositories; the Owner of B takes
  A's updates and releases again.
- H4 touches every client that lists entries, so it is the last slice and is optional.
