// How an app draws LorenzoScript text, which each app does with its own links (ADR 0240): the
// parts that show or edit text are given a renderer, and know only its shape.

/** One text's HTML, and what an author should know about links in it that won't work. */
export type Rendered = { html: string; notes: string[] };

/**
 * Renders texts; `homes` says which entity each text belongs to, which is what a `my/` link is
 * held by (ADR 0240). A text with none, a new one say, has no `my/` meaning.
 */
export type Renderer = (
  texts: string[],
  homes?: readonly (string | undefined)[],
) => Promise<Rendered[]>;

/** The renderer for texts that all belong to `home`. */
export const at =
  (renderer: Renderer, home: string | undefined): Renderer =>
  (texts) =>
    renderer(
      texts,
      texts.map(() => home),
    );
