// The legal notice, the privacy policy and the support link in the shell (ADR 0439). Where they
// are comes from the registry (`GET /app-links`, ADR 0273): the API names them only when a
// deployment has set LEGAL_URL and SUPPORT_URL, so a deployment without them shows no link and can
// never point at another operator's notice. The labels follow the page's language.

export type Lang = 'en' | 'de';

export const LEGAL_LABELS: Record<Lang, { notice: string; privacy: string; support: string }> = {
  en: { notice: 'Legal notice (Impressum)', privacy: 'Privacy policy', support: 'Support Lorenzo' },
  de: { notice: 'Impressum', privacy: 'Datenschutzerklärung', support: 'Lorenzo unterstützen' },
};

/** What `GET /app-links` answers that the legal links need. */
export type LegalRegistry = {
  links?: Record<string, string | undefined>;
  support_url?: string | null;
};

export type LegalLinks = { notice?: string; privacy?: string; support?: string };

/** The language of a page (`<html lang>`): German for `de`, `de-AT` and the like, else English. */
export function langOf(value: string | null | undefined): Lang {
  return (value ?? '').toLowerCase().startsWith('de') ? 'de' : 'en';
}

/** Only a web address is ever a link: an address from the API is data, not a script. */
function webAddress(value: string | null | undefined): string | undefined {
  const text = value?.trim();

  return text && /^https?:\/\//i.test(text) ? text : undefined;
}

/** The links a registry has, in the page's language. A link it does not have is left out. */
export function legalLinks(registry: LegalRegistry, lang: Lang): LegalLinks {
  const notice = webAddress(registry.links?.[`legal_notice_${lang}`]);
  const privacy = webAddress(registry.links?.[`legal_privacy_${lang}`]);
  const support = webAddress(registry.support_url);

  return {
    ...(notice ? { notice } : {}),
    ...(privacy ? { privacy } : {}),
    ...(support ? { support } : {}),
  };
}

const KINDS = ['notice', 'privacy', 'support'] as const;

/**
 * Fills the legal and support links of the page from a registry: each `[data-shell-link]` holder
 * is shown, with its anchor's address set, when the registry has that link, and hidden otherwise.
 * A link given in the page's own markup (a static address) is left as it is.
 */
export function bindLegalLinks(registry: LegalRegistry, root: ParentNode = document): void {
  const owner = 'documentElement' in root ? (root as Document) : (root as Element).ownerDocument;
  const lang = langOf(owner?.documentElement.lang);
  const found = legalLinks(registry, lang);

  for (const kind of KINDS) {
    for (const holder of root.querySelectorAll<HTMLElement>(`[data-shell-link="${kind}"]`)) {
      const anchor = holder.querySelector<HTMLAnchorElement>('a');
      const address = found[kind];

      if (!anchor || holder.dataset.static === '') continue;

      if (address) {
        anchor.href = address;
        holder.hidden = false;
      } else {
        anchor.removeAttribute('href');
        holder.hidden = true;
      }
    }
  }
}

/**
 * Asks the API for the registry and binds the links from it. `GET /app-links` is public and cached
 * for five minutes (ADR 0273), so an app that has read it already costs the browser no second
 * request. A failure leaves the links hidden: nothing here may break a page.
 */
export async function bindLegalLinksFromApi(
  apiBaseUrl: string,
  fetcher: typeof fetch = fetch,
  root: ParentNode = document,
): Promise<void> {
  try {
    const response = await fetcher(`${apiBaseUrl.replace(/\/$/, '')}/app-links`, {
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) return;

    bindLegalLinks((await response.json()) as LegalRegistry, root);
  } catch {
    // The links stay hidden.
  }
}
