// $…$ and $$…$$ (ADR 0102): a documented subset of TeX, turned into MathML Core,
// which browsers draw natively. Anything outside the subset makes `mathml` return
// null, and the renderer shows the TeX source as code instead.
import { escapeHtml } from './html';
import { MAX_NESTING } from './inline';

const el = (tag: string, body: string, attrs = '') => `<${tag}${attrs}>${body}</${tag}>`;
const mi = (s: string, attrs = '') => el('mi', escapeHtml(s), attrs);
const mo = (s: string, attrs = '') => el('mo', escapeHtml(s), attrs);

/** Greek letters, in Unicode order from `first`; TeX's `\epsilon` and `\phi` are the lunate forms. */
const LETTERS =
  'alpha beta gamma delta varepsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho varsigma sigma tau upsilon varphi chi psi omega';
const greek = (first: number, name: (n: string) => string) =>
  Object.fromEntries(
    LETTERS.split(' ').map((n, k) => [name(n), String.fromCodePoint(first + k)] as const),
  );
const GREEK: Record<string, string> = {
  ...greek(0x3b1, (n) => n),
  // Uppercase has no variants, so `varphi`'s slot is `\Phi`, and `varsigma`'s (unassigned) is
  // overwritten by `sigma`'s.
  ...greek(0x391, (n) => n.replace(/^var/, '').replace(/^./, (c) => c.toUpperCase())),
  epsilon: 'ϵ',
  phi: 'ϕ',
  vartheta: 'ϑ',
  varpi: 'ϖ',
  varrho: 'ϱ',
};

// biome-ignore format: a symbol table reads best compact
const OPERATORS: Record<string, string> = {
  times: '×', cdot: '⋅', pm: '±', mp: '∓', div: '÷', ast: '∗', star: '⋆', circ: '∘', bullet: '∙',
  le: '≤', leq: '≤', ge: '≥', geq: '≥', ne: '≠', neq: '≠', approx: '≈', equiv: '≡', sim: '∼',
  simeq: '≃', cong: '≅', propto: '∝', ll: '≪', gg: '≫',
  to: '→', rightarrow: '→', leftarrow: '←', gets: '←', leftrightarrow: '↔', Rightarrow: '⇒',
  Leftarrow: '⇐', Leftrightarrow: '⇔', implies: '⟹', iff: '⟺', mapsto: '↦',
  in: '∈', notin: '∉', ni: '∋', subset: '⊂', supset: '⊃', subseteq: '⊆', supseteq: '⊇',
  cup: '∪', cap: '∩', setminus: '∖', forall: '∀', exists: '∃', neg: '¬', lnot: '¬',
  land: '∧', wedge: '∧', lor: '∨', vee: '∨', oplus: '⊕', otimes: '⊗',
  mid: '∣', parallel: '∥', perp: '⊥', ldots: '…', dots: '…', cdots: '⋯', vdots: '⋮', ddots: '⋱',
  langle: '⟨', rangle: '⟩', lfloor: '⌊', rfloor: '⌋', lceil: '⌈', rceil: '⌉', vert: '|',
  Vert: '‖', '|': '‖', '{': '{', '}': '}', $: '$', '%': '%', '#': '#', '&': '&', _: '_',
};
// biome-ignore format: a symbol table reads best compact
const IDENTIFIERS: Record<string, string> = {
  infty: '∞', partial: '∂', nabla: '∇', emptyset: '∅', varnothing: '∅', hbar: 'ℏ', ell: 'ℓ',
  aleph: 'ℵ', Re: 'ℜ', Im: 'ℑ', prime: '′', degree: '°', angle: '∠', triangle: '△',
};
/** Big operators: these take limits under and over; integrals take them as scripts. */
// biome-ignore format: a symbol table reads best compact
const LIMITS: Record<string, string> = {
  sum: '∑', prod: '∏', coprod: '∐', bigcup: '⋃', bigcap: '⋂', bigoplus: '⨁', bigotimes: '⨂',
};
const INTEGRALS: Record<string, string> = { int: '∫', iint: '∬', iiint: '∭', oint: '∮' };
const words = (s: string) => new Set(s.split(' '));
const FUNCTIONS = words(
  'arccos arcsin arctan arg cos cosh cot coth csc deg det dim exp gcd hom inf ker lg lim liminf limsup ln log max min Pr sec sin sinh sup tan tanh',
);
const LIMIT_FUNCTIONS = words('det gcd inf lim liminf limsup max min Pr sup');
// biome-ignore format: a symbol table reads best compact
const SPACES: Record<string, string> = {
  ',': '0.1667em', ':': '0.2222em', '>': '0.2222em', ';': '0.2778em', ' ': '0.25em',
  '!': '-0.1667em', quad: '1em', qquad: '2em',
};
// biome-ignore format: a symbol table reads best compact
const ACCENTS: Record<string, string> = {
  hat: '^', bar: '¯', overline: '¯', vec: '→', dot: '˙', ddot: '¨', tilde: '~',
};
const ASCII_OPERATORS = "+=<>()[]|/,;:!.?*'";

class Unsupported extends Error {}
const fail = (): never => {
  throw new Unsupported();
};

type Atom = { html: string; limits?: boolean };

/** MathML for `tex` (without the `<math>` element), or null outside the supported subset. */
export function mathml(tex: string): string | null {
  let i = 0;
  let depth = 0;
  const peek = () => {
    while (i < tex.length && /\s/.test(tex[i] as string)) i++;
    return tex[i];
  };
  const command = (): string => {
    const m = /^\\([A-Za-z]+|[^A-Za-z])/.exec(tex.slice(i)) ?? fail();
    i += m[0].length;
    return m[1] as string;
  };
  const wrap = (parts: string[]) =>
    parts.length === 1 ? (parts[0] as string) : el('mrow', parts.join(''));

  /** Terms up to (and past) `close`. */
  function group(close: string): string {
    const parts: string[] = [];
    while (peek() !== close) {
      if (i >= tex.length) fail();
      parts.push(term());
    }
    i++;
    return wrap(parts);
  }

  /** Raw text up to the brace matching one just opened, for `\text{…}`. */
  function raw(): string {
    if (peek() !== '{') fail();
    const start = ++i;
    for (let level = 0; i < tex.length; i++) {
      if (tex[i] === '{') level++;
      else if (tex[i] === '}' && level-- === 0) return tex.slice(start, i++);
    }
    return fail();
  }

  /** An argument: a `{group}` or one token, so `x^10` is x¹0, as in TeX. */
  function arg(): string {
    const c = peek();
    if (c !== undefined && /\d/.test(c)) {
      i++;
      return el('mn', c);
    }
    return atom().html;
  }

  function term(): string {
    const base = atom();
    let sub = '';
    let sup = '';
    for (let c = peek(); c === '^' || c === '_' || c === "'"; c = peek()) {
      i++;
      if (c === '^') sup = arg();
      else if (c === '_') sub = arg();
      else {
        let primes = '′';
        for (; tex[i] === "'"; i++) primes += '′';
        sup = mo(primes);
      }
    }
    if (!sub && !sup) return base.html;
    const [under, over, both] = base.limits
      ? ['munder', 'mover', 'munderover']
      : ['msub', 'msup', 'msubsup'];
    if (sub && sup) return el(both, base.html + sub + sup);
    return sub ? el(under, base.html + sub) : el(over, base.html + sup);
  }

  function atom(): Atom {
    if (++depth > MAX_NESTING) fail();
    const c = peek() ?? fail();
    let result: Atom;
    if (c === '{') {
      i++;
      result = { html: group('}') };
    } else if (c === '\\') {
      result = control(command());
    } else {
      const number = /^\d+(?:\.\d+)?/.exec(tex.slice(i));
      const ch = number?.[0] ?? String.fromCodePoint(tex.codePointAt(i) as number);
      i += ch.length;
      if (number) result = { html: el('mn', ch) };
      else if (ch === '~') result = control(' ');
      else if (/[A-Za-z]/.test(ch)) result = { html: mi(ch) };
      else if (ch === '-') result = { html: mo('−') };
      else if (ASCII_OPERATORS.includes(ch)) result = { html: mo(ch) };
      else if ('&#%}^_\\'.includes(ch)) result = fail();
      else result = { html: /\p{L}/u.test(ch) ? mi(ch) : mo(ch) };
    }
    depth--;
    return result;
  }

  /** The delimiter after `\left` or `\right`; `.` means none. */
  function delimiter(): string {
    const c = peek();
    if (c === '\\') {
      const name = command();
      return name in OPERATORS ? mo(OPERATORS[name] as string) : fail();
    }
    if (c === undefined || !'.()[]|/'.includes(c)) return fail();
    i++;
    return c === '.' ? '' : mo(c);
  }

  function control(name: string): Atom {
    if (name in SPACES) return { html: el('mspace', '', ` width="${SPACES[name]}"`) };
    if (name in LIMITS) return { html: mo(LIMITS[name] as string), limits: true };
    if (name in INTEGRALS) return { html: mo(INTEGRALS[name] as string) };
    if (name in OPERATORS) return { html: mo(OPERATORS[name] as string) };
    if (name in IDENTIFIERS) return { html: mi(IDENTIFIERS[name] as string) };
    if (name in GREEK) {
      // Uppercase Greek is upright in TeX; a single-letter <mi> would be italic.
      const upright = /^[A-Z]/.test(name) ? ' mathvariant="normal"' : '';
      return { html: mi(GREEK[name] as string, upright) };
    }
    if (FUNCTIONS.has(name)) {
      if (!LIMIT_FUNCTIONS.has(name)) return { html: mi(name) };
      return { html: mo(name, ' movablelimits="true" form="prefix"'), limits: true };
    }
    if (name in ACCENTS) {
      return { html: el('mover', arg() + mo(ACCENTS[name] as string), ' accent="true"') };
    }
    switch (name) {
      case 'frac':
        return { html: el('mfrac', arg() + arg()) };
      case 'binom':
        return {
          html: el('mrow', mo('(') + el('mfrac', arg() + arg(), ' linethickness="0"') + mo(')')),
        };
      case 'sqrt': {
        if (peek() !== '[') return { html: el('msqrt', arg()) };
        i++;
        const index = group(']');
        return { html: el('mroot', arg() + index) };
      }
      case 'text':
        // Spaces at the edges would be collapsed away; keep them as no-break spaces.
        return {
          html: el('mtext', escapeHtml(raw().replace(/^ | $/g, String.fromCharCode(0xa0)))),
        };
      case 'operatorname':
        return { html: mi(raw()) };
      case 'left': {
        const open = delimiter();
        const parts: string[] = [];
        for (peek(); !/^\\right(?![A-Za-z])/.test(tex.slice(i)); peek()) {
          if (i >= tex.length) fail();
          parts.push(term());
        }
        i += '\\right'.length;
        return { html: el('mrow', open + parts.join('') + delimiter()) };
      }
    }
    return fail();
  }

  try {
    const parts: string[] = [];
    while (peek() !== undefined) parts.push(term());
    return parts.join('');
  } catch (e) {
    if (e instanceof Unsupported) return null;
    throw e;
  }
}
