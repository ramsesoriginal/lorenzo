/** The card the API's preview route gives for an entry (`LinkPreviewOut`, ADR 0264). Declared here
 * so the package needs no generated client: an app's `loadCard` returns it. */
export type EntryCard = {
  entity_id: string;
  name: string;
  slug?: string | null;
  kinds: readonly string[];
  /** The registry template that built the card; a client may style by it. */
  template?: string;
  /** The main picture's content URL, a protected file; null when there is none. */
  picture_url?: string | null;
  stats: readonly { name: string; value: number | string }[];
  /** The start of the description as plain words; empty when there is none. */
  excerpt: string;
};

/** The library and entry an element stands for. */
export type PreviewTarget = { tenant: string; id: string };
