// The starter vocabulary (RFC 0049 decision 8, ADR 0400): the words relationships are told in, as
// ordinary content a library adds on purpose. Nothing here is seeded, and no type carries an
// audience: every relationship starts restricted (ADR 0404). The standings' scales and the wording
// are the author's first pass, for the maintainer to review before the starter is published as a
// repository.

export interface StarterStanding {
  name: string;
  min: number;
  max: number;
}

export interface StarterType {
  name: string;
  /** The type this one is a kind of; none for a family of types. */
  parent?: string;
  /** A relationship of this type points one way. */
  directed?: boolean;
  /** How it reads from the first end ("is the parent of"), and from the second ("is a child of"). */
  readsAs?: string;
  readsAsBack?: string;
}

/** The three stats that say how a type points and reads: named here, set on the library. */
export const TYPE_STATS = {
  directed: 'relationship directed',
  readsAs: 'relationship reads as',
  readsAsBack: 'relationship reads as from the other end',
} as const;

export const STANDING_GROUP = 'Relationships';

export const STANDINGS: readonly StarterStanding[] = [
  { name: 'Reputation', min: -10, max: 10 },
  { name: 'Honor', min: -10, max: 10 },
  { name: 'Concordance', min: -10, max: 10 },
  { name: 'Faith', min: 0, max: 10 },
  { name: 'Familiarity', min: 0, max: 10 },
];

export const TYPES: readonly StarterType[] = [
  { name: 'Family' },
  {
    name: 'Parent of',
    parent: 'Family',
    directed: true,
    readsAs: 'is the parent of',
    readsAsBack: 'is a child of',
  },
  {
    name: 'Sibling of',
    parent: 'Family',
    readsAs: 'is a sibling of',
    readsAsBack: 'is a sibling of',
  },
  {
    name: 'Co-parent of',
    parent: 'Family',
    readsAs: 'is a co-parent with',
    readsAsBack: 'is a co-parent with',
  },
  {
    name: 'Married to',
    parent: 'Family',
    readsAs: 'is married to',
    readsAsBack: 'is married to',
  },
  {
    name: 'Partner of',
    parent: 'Family',
    readsAs: 'is the partner of',
    readsAsBack: 'is the partner of',
  },
  { name: 'Bond' },
  {
    name: 'Summoner of',
    parent: 'Bond',
    directed: true,
    readsAs: 'is the summoner of',
    readsAsBack: 'is summoned by',
  },
  {
    name: 'Patron of',
    parent: 'Bond',
    directed: true,
    readsAs: 'is the patron of',
    readsAsBack: 'is patroned by',
  },
  { name: 'Office' },
  {
    name: 'Diplomat for',
    parent: 'Office',
    directed: true,
    readsAs: 'is a diplomat for',
    readsAsBack: 'is represented by',
  },
  {
    name: 'Diplomat in',
    parent: 'Office',
    directed: true,
    readsAs: 'is a diplomat in',
    readsAsBack: 'receives the diplomat',
  },
  { name: 'Between realms' },
  {
    name: 'At war with',
    parent: 'Between realms',
    readsAs: 'is at war with',
    readsAsBack: 'is at war with',
  },
  {
    name: 'In alliance with',
    parent: 'Between realms',
    readsAs: 'is in alliance with',
    readsAsBack: 'is in alliance with',
  },
  { name: 'Intimacy' },
  {
    name: 'Romantic',
    parent: 'Intimacy',
    readsAs: 'is romantically involved with',
    readsAsBack: 'is romantically involved with',
  },
  {
    name: 'Sexual',
    parent: 'Intimacy',
    readsAs: 'is sexually involved with',
    readsAsBack: 'is sexually involved with',
  },
];

export interface StarterPlan {
  /** Types in an order where each comes after its parent. */
  types: readonly StarterType[];
  standings: readonly StarterStanding[];
}

/** What adding the starter would make, leaving out a type or a standing the library has by that
 * name (a stat is found by its name, so a second run adds nothing it already has). */
export function planStarter(have: {
  statNames: ReadonlySet<string>;
  entryNames: ReadonlySet<string>;
}): StarterPlan {
  return {
    types: TYPES.filter((t) => !have.entryNames.has(t.name)),
    standings: STANDINGS.filter((s) => !have.statNames.has(s.name)),
  };
}
