// The operator profile (ADR 0439): everything the legal pages say that is specific to one
// deployment. It is supplied at build time, never kept in the repository, and an incomplete one
// fails the build with the names of what is missing.

export type Bi = { de: string; en: string };

export type TaxId = { kind: 'none' } | { kind: 'vat' | 'wid'; value: string };

export type Provider = {
  name: string;
  purpose: Bi;
  /** Where the provider processes the data, as the operator has confirmed it with the provider. */
  location: Bi;
  /** What allows a transfer outside the EU, or that there is none. */
  transfer: Bi;
  policyUrl: string;
};

export type LegalProfile = {
  /** True only for the sample profile of a development build. */
  sample: boolean;
  /** The date of the last change to this profile, YYYY-MM-DD. */
  changedOn: string;
  /** The date a lawyer reviewed the texts, YYYY-MM-DD. While absent, every page says it is a draft. */
  reviewedOn: string | null;
  operator: {
    name: string;
    street: string;
    postalCode: string;
    city: string;
    country: string;
    email: string;
    /** A second quick way to reach the operator, or 'none'. */
    secondContact: string;
    taxId: TaxId;
    /** Where reports about content go; the operator's email when absent. */
    reportEmail: string | null;
  };
  supervisoryAuthority: { name: string; url: string };
  providers: Provider[];
  retention: { logs: Bi; backups: Bi; activityLog: Bi };
  /** A support link the policy names as a link out, or null. */
  support: { name: string; url: string } | null;
};

const PLACEHOLDER = /^\s*(todo|tbd|tba|xxx+|changeme|placeholder|fixme|\.\.\.|<[^>]*>)\s*$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

class Problems {
  readonly list: string[] = [];

  add(path: string, why: string) {
    this.list.push(`${path}: ${why}`);
  }
}

function text(value: unknown, path: string, problems: Problems): string {
  if (typeof value !== 'string' || value.trim() === '') {
    problems.add(path, 'is required');
    return '';
  }
  if (PLACEHOLDER.test(value)) {
    problems.add(path, `still holds a placeholder (${JSON.stringify(value)})`);
  }
  return value.trim();
}

function bi(value: unknown, path: string, problems: Problems): Bi {
  const object = (value ?? {}) as Record<string, unknown>;
  return {
    de: text(object.de, `${path}.de`, problems),
    en: text(object.en, `${path}.en`, problems),
  };
}

function url(value: unknown, path: string, problems: Problems): string {
  const found = text(value, path, problems);
  if (found && !/^https:\/\/[^\s/]+\.[^\s/]+/.test(found))
    problems.add(path, 'must be an https:// address');
  return found;
}

function date(value: unknown, path: string, problems: Problems): string {
  const found = text(value, path, problems);
  if (found && !DATE.test(found)) problems.add(path, 'must be a date, YYYY-MM-DD');
  return found;
}

function taxId(value: unknown, path: string, problems: Problems): TaxId {
  const object = (value ?? {}) as Record<string, unknown>;
  if (object.kind === 'none') return { kind: 'none' };
  if (object.kind === 'vat' || object.kind === 'wid') {
    return { kind: object.kind, value: text(object.value, `${path}.value`, problems) };
  }
  problems.add(
    path,
    "must say {kind: 'none'} or {kind: 'vat' | 'wid', value}; a missing number is not 'none'",
  );
  return { kind: 'none' };
}

/** Checks a parsed profile. Throws one error that names every missing or unusable field. */
export function parseProfile(raw: unknown, sample = false): LegalProfile {
  const problems = new Problems();
  const root = (raw ?? {}) as Record<string, unknown>;
  const operator = (root.operator ?? {}) as Record<string, unknown>;
  const second = operator.secondContact;
  const authority = (root.supervisoryAuthority ?? {}) as Record<string, unknown>;
  const retention = (root.retention ?? {}) as Record<string, unknown>;
  const support =
    root.support === null || root.support === undefined
      ? null
      : (root.support as Record<string, unknown>);

  const profile: LegalProfile = {
    sample,
    changedOn: date(root.changedOn, 'changedOn', problems),
    reviewedOn:
      root.reviewedOn === null || root.reviewedOn === undefined
        ? null
        : date(root.reviewedOn, 'reviewedOn', problems),
    operator: {
      name: text(operator.name, 'operator.name', problems),
      street: text(operator.street, 'operator.street', problems),
      postalCode: text(operator.postalCode, 'operator.postalCode', problems),
      city: text(operator.city, 'operator.city', problems),
      country: text(operator.country, 'operator.country', problems),
      email: text(operator.email, 'operator.email', problems),
      secondContact:
        second === 'none'
          ? 'none'
          : text(second, "operator.secondContact (a value, or 'none')", problems),
      taxId: taxId(operator.taxId, 'operator.taxId', problems),
      reportEmail:
        operator.reportEmail === null || operator.reportEmail === undefined
          ? null
          : text(operator.reportEmail, 'operator.reportEmail', problems),
    },
    supervisoryAuthority: {
      name: text(authority.name, 'supervisoryAuthority.name', problems),
      url: url(authority.url, 'supervisoryAuthority.url', problems),
    },
    providers: [],
    retention: {
      logs: bi(retention.logs, 'retention.logs', problems),
      backups: bi(retention.backups, 'retention.backups', problems),
      activityLog: bi(retention.activityLog, 'retention.activityLog', problems),
    },
    support: support
      ? {
          name: text(support.name, 'support.name', problems),
          url: url(support.url, 'support.url', problems),
        }
      : null,
  };

  if (!Array.isArray(root.providers) || root.providers.length === 0) {
    problems.add('providers', 'needs at least one provider');
  } else {
    root.providers.forEach((entry, index) => {
      const path = `providers[${index}]`;
      const one = (entry ?? {}) as Record<string, unknown>;
      profile.providers.push({
        name: text(one.name, `${path}.name`, problems),
        purpose: bi(one.purpose, `${path}.purpose`, problems),
        location: bi(one.location, `${path}.location`, problems),
        transfer: bi(one.transfer, `${path}.transfer`, problems),
        policyUrl: url(one.policyUrl, `${path}.policyUrl`, problems),
      });
    });
  }

  if (problems.list.length > 0) {
    throw new Error(
      `The legal pages cannot be built: the operator profile is incomplete (ADR 0439).\n- ${problems.list.join('\n- ')}`,
    );
  }
  return profile;
}

/**
 * The profile of this build. `LEGAL_PROFILE` is JSON; `LEGAL_PROFILE_SAMPLE=1` selects the
 * sample, which every page marks as such. With neither, the build fails.
 */
export function loadProfile(
  env: Record<string, string | undefined>,
  sampleProfile: unknown,
): LegalProfile {
  const given = env.LEGAL_PROFILE?.trim();
  if (given) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(given);
    } catch (error) {
      throw new Error(
        `The legal pages cannot be built: LEGAL_PROFILE is not JSON (${(error as Error).message}).`,
      );
    }
    return parseProfile(parsed);
  }
  if (env.LEGAL_PROFILE_SAMPLE === '1') return parseProfile(sampleProfile, true);
  throw new Error(
    'The legal pages cannot be built: set LEGAL_PROFILE (the operator profile, ADR 0439), or LEGAL_PROFILE_SAMPLE=1 for a development build.',
  );
}
