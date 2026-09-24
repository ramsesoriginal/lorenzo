# LorenzoScript

LorenzoScript is Lorenzo's Markdown dialect, used for every description text ([RFC 0027](../../docs/rfcs/0027-lorenzoscript.md)). It follows [CommonMark](https://spec.commonmark.org/)'s structure, with the deviations listed at the end of this file.

This file is both the definition and the test suite ([ADR 0100](../../docs/adr/0100-lorenzoscript-core-parser-and-renderer.md)). Every `example` block below is run as a test: the LorenzoScript source, a line holding only `.`, then the HTML it must render to. An example that ends there has no references. The others add another `.` line and the JSON that `references()` must return for the source ([ADR 0110](../../docs/adr/0110-lorenzoscript-content-references-and-backlinks.md)). In examples, `␠` stands for a trailing space and `⇥` for a tab.

Every example renders with `locale: 'en-GB'` and a fixture resolver:

- It knows two entities, `ashfang` (which has a picture) and `old-sword`.
- A reference `hint/slug` links to `/hint/slug`, or to `/entity/slug` without a hint. The link is titled with the entity's name.
- A picture is `/pictures/slug.png`.
- It reads the calendar date `harptos 1492-mirtul-12` as "12 Mirtul 1492 DR".

The sections cover three stages:

- the core syntax (RFC 0027 stage 1)
- the standard extensions (stage 2, [ADR 0102](../../docs/adr/0102-lorenzoscript-standard-extensions.md)), from [Strikethrough, subscript, superscript](#strikethrough-subscript-superscript) on
- Lorenzo's own extensions (stage 3, [ADR 0105](../../docs/adr/0105-lorenzoscript-entity-references-and-resolver.md)), from [Entity links and images](#entity-links-and-images) on

## Paragraphs

Lines of text separated by one or more blank lines form paragraphs. Leading spaces and a paragraph's final trailing spaces are dropped.

```````` example
aaa

bbb
.
<p>aaa</p>
<p>bbb</p>
````````

```````` example
aaa
   bbb


ccc␠␠
.
<p>aaa
bbb</p>
<p>ccc</p>
````````

## Line breaks

Two or more spaces at the end of a line, or a backslash, force a line break. A single space doesn't.

```````` example
foo␠␠
bar
.
<p>foo<br>
bar</p>
````````

```````` example
foo\
bar
.
<p>foo<br>
bar</p>
````````

```````` example
foo␠
bar
.
<p>foo
bar</p>
````````

## Headings

One to six `#`, then a space. Closing `#`s are dropped when a space precedes them. Setext headings (text underlined with `===` or `---`) are not part of LorenzoScript.

```````` example
# one
## two
###### six
.
<h1 id="ls-one">one</h1>
<h2 id="ls-two">two</h2>
<h6 id="ls-six">six</h6>
````````

```````` example
####### seven

#no space
.
<p>####### seven</p>
<p>#no space</p>
````````

```````` example
## closing ##
# foo#
.
<h2 id="ls-closing">closing</h2>
<h1 id="ls-foo">foo#</h1>
````````

```````` example
# An *emphasized* title
.
<h1 id="ls-an-emphasized-title">An <em>emphasized</em> title</h1>
````````

```````` example
Not a title
===========
.
<p>Not a title
===========</p>
````````

```````` example
text
# heading
.
<p>text</p>
<h1 id="ls-heading">heading</h1>
````````

Every heading gets an id, for in-document links and `{{TOC}}`: its explicit `{#id}` (see [Attributes](#attributes)), or else its text as a slug (accents dropped, lowercase ASCII, hyphenated), with `-2`, `-3` added to repeats. Text with no ASCII letters or digits becomes `section`. Like every author id, it carries the `ls-` prefix.

```````` example
# Café au lait
## Café au lait
# Über uns {#about .wide}
# 日本
.
<h1 id="ls-cafe-au-lait">Café au lait</h1>
<h2 id="ls-cafe-au-lait-2">Café au lait</h2>
<h1 id="ls-about" class="wide">Über uns</h1>
<h1 id="ls-section">日本</h1>
````````

## Horizontal rules

Three or more `-`, `*`, or `_`, optionally spaced. Text directly above `---` stays a paragraph.

```````` example
---
***
___
- - -
.
<hr>
<hr>
<hr>
<hr>
````````

```````` example
--
.
<p>--</p>
````````

```````` example
text
---
.
<p>text</p>
<hr>
````````

## Code blocks

Fenced with three or more backticks or tildes, closed by a fence of the same character that is at least as long. The first word after the opening fence names the language. An unclosed fence runs to the end of its container.

```````` example
```js
let a = 1 < 2;
```
.
<pre><code class="language-js">let a = 1 &lt; 2;
</code></pre>
````````

```````` example
~~~
```
~~~
.
<pre><code>```
</code></pre>
````````

```````` example
````
```
``````
.
<pre><code>```
</code></pre>
````````

```````` example
```
unclosed
.
<pre><code>unclosed
</code></pre>
````````

A fence's own indentation is removed from its content.

```````` example
  ```
  aaa
    bbb
  ```
.
<pre><code>aaa
  bbb
</code></pre>
````````

A language that isn't made of letters, digits, and `+#.-_` is dropped rather than emitted.

```````` example
```js"onclick
```
.
<pre><code></code></pre>
````````

Four spaces of indentation also make a code block, but they can't interrupt a paragraph. Blank lines inside are kept; trailing ones aren't.

```````` example
    a

    b

.
<pre><code>a

b
</code></pre>
````````

```````` example
text
    more text
.
<p>text
more text</p>
````````

A tab at the start of a line indents to the next multiple of 4 columns.

```````` example
⇥code
-⇥item
.
<pre><code>code
</code></pre>
<ul>
<li>item</li>
</ul>
````````

## Blockquotes

`>` at the start of each line, optionally followed by a space. Blockquotes nest and can hold any other block.

```````` example
> foo
> bar
.
<blockquote>
<p>foo
bar</p>
</blockquote>
````````

```````` example
> a
> > b
.
<blockquote>
<p>a</p>
<blockquote>
<p>b</p>
</blockquote>
</blockquote>
````````

```````` example
> # Title
> - item
>
> ```
> code
> ```
.
<blockquote>
<h1 id="ls-title">Title</h1>
<ul>
<li>item</li>
</ul>
<pre><code>code
</code></pre>
</blockquote>
````````

A blank line ends the blockquote.

```````` example
> foo

> bar
.
<blockquote>
<p>foo</p>
</blockquote>
<blockquote>
<p>bar</p>
</blockquote>
````````

A line without `>` still continues a paragraph inside the quote ("lazy continuation"), at any depth, but never code.

```````` example
> foo
bar
.
<blockquote>
<p>foo
bar</p>
</blockquote>
````````

```````` example
> > foo
bar
.
<blockquote>
<blockquote>
<p>foo
bar</p>
</blockquote>
</blockquote>
````````

```````` example
> ```
> a
b
.
<blockquote>
<pre><code>a
</code></pre>
</blockquote>
<p>b</p>
````````

## Lists

`-`, `*`, or `+` for unordered items; a number followed by `.` or `)` for ordered ones. Changing the marker starts a new list.

```````` example
- a
- b
.
<ul>
<li>a</li>
<li>b</li>
</ul>
````````

```````` example
1. a
2. b
.
<ol>
<li>a</li>
<li>b</li>
</ol>
````````

```````` example
3. a
4. b
.
<ol start="3">
<li>a</li>
<li>b</li>
</ol>
````````

```````` example
- a
* b
.
<ul>
<li>a</li>
</ul>
<ul>
<li>b</li>
</ul>
````````

Indenting by 4 spaces always continues an item, and so does indenting to where its text starts (2 after `-` and a space, 3 after `1.` and a space). That's how nested lists, extra paragraphs, and code get into an item without ending the list.

```````` example
- a
    - b
    - c
- d
.
<ul>
<li>a
<ul>
<li>b</li>
<li>c</li>
</ul>
</li>
<li>d</li>
</ul>
````````

```````` example
- a
  - b
.
<ul>
<li>a
<ul>
<li>b</li>
</ul>
</li>
</ul>
````````

```````` example
- a

    ```
    code
    ```
.
<ul>
<li>
<p>a</p>
<pre><code>code
</code></pre>
</li>
</ul>
````````

A list is loose, with each item's text in a paragraph, when a blank line separates two items or two blocks inside one item. Otherwise it's tight.

```````` example
- a

- b
.
<ul>
<li>
<p>a</p>
</li>
<li>
<p>b</p>
</li>
</ul>
````````

```````` example
1. first

    more about the first
2. second
.
<ol>
<li>
<p>first</p>
<p>more about the first</p>
</li>
<li>
<p>second</p>
</li>
</ol>
````````

A blank line inside a nested list loosens only that list.

```````` example
- a
    - b

    - c
- d
.
<ul>
<li>a
<ul>
<li>
<p>b</p>
</li>
<li>
<p>c</p>
</li>
</ul>
</li>
<li>d</li>
</ul>
````````

Items can hold any block, and continue lazily like blockquotes.

```````` example
- > quoted
- a
b
.
<ul>
<li>
<blockquote>
<p>quoted</p>
</blockquote>
</li>
<li>a
b</li>
</ul>
````````

A list may interrupt a paragraph, but an ordered one only when it starts at 1, so a sentence that happens to break before a number stays a sentence.

```````` example
text
- item
.
<p>text</p>
<ul>
<li>item</li>
</ul>
````````

```````` example
The treaty was signed in
1492. It held.
.
<p>The treaty was signed in
1492. It held.</p>
````````

A horizontal rule ends a list, and an item can be empty.

```````` example
- a
* * *
-
- b
.
<ul>
<li>a</li>
</ul>
<hr>
<ul>
<li></li>
<li>b</li>
</ul>
````````

## Task lists

An item starting with `[ ]` or `[x]` (either case), then a space, is a task. The checkbox is disabled: toggling it from the rendered view isn't supported.

```````` example
- [ ] open
- [x] done
- [X] also done
- [x]not a task
.
<ul>
<li class="ls-task"><input type="checkbox" disabled> open</li>
<li class="ls-task"><input type="checkbox" disabled checked> done</li>
<li class="ls-task"><input type="checkbox" disabled checked> also done</li>
<li>[x]not a task</li>
</ul>
````````

```````` example
1. [ ] first

2. [x] second
.
<ol>
<li class="ls-task">
<p><input type="checkbox" disabled> first</p>
</li>
<li class="ls-task">
<p><input type="checkbox" disabled checked> second</p>
</li>
</ol>
````````

## Emphasis

`*em*` and `**strong**` are semantic emphasis (`<em>`, `<strong>`). `_i_` and `__b__` are stylistic (`<i>`, `<b>`), so themes can style the two pairs differently.

```````` example
*em* **strong** _i_ __b__
.
<p><em>em</em> <strong>strong</strong> <i>i</i> <b>b</b></p>
````````

```````` example
***both*** and **bold *with em* inside** and *_mixed_*
.
<p><em><strong>both</strong></em> and <strong>bold <em>with em</em> inside</strong> and <em><i>mixed</i></em></p>
````````

`*` works inside a word; `_` doesn't, so identifiers stay intact.

```````` example
un*frigging*believable snake_case_name
.
<p>un<em>frigging</em>believable snake_case_name</p>
````````

A delimiter surrounded by spaces, or left unmatched, is just text.

```````` example
a * b * c **open
.
<p>a * b * c **open</p>
````````

Runs pair up by CommonMark's rules, including its "rule of 3".

```````` example
*foo**bar**baz*
.
<p><em>foo<strong>bar</strong>baz</em></p>
````````

## Code spans

Backticks enclose code; a longer run of backticks can enclose shorter ones. One space is trimmed from each end, and line breaks become spaces. Nothing inside a code span is interpreted.

```````` example
`code` and `` a ` b `` and `*not em*` and `<b>`
.
<p><code>code</code> and <code>a ` b</code> and <code>*not em*</code> and <code>&lt;b&gt;</code></p>
````````

```````` example
`a
b` and `unmatched
.
<p><code>a b</code> and `unmatched</p>
````````

## Links

`[text](url "title")`. Only `http`, `https`, `mailto`, and in-document `#fragment` links become links; any other target renders its text alone. Fragments are rewritten to the `ls-` prefix every author id carries. A target that is a slug names an entity instead; see [Entity links and images](#entity-links-and-images).

```````` example
[Lorenzo](https://example.com "The archive")
.
<p><a href="https://example.com" title="The archive">Lorenzo</a></p>
````````

```````` example
[mail](mailto:gm@example.com) and [see below](#notes)
.
<p><a href="mailto:gm@example.com">mail</a> and <a href="#ls-notes">see below</a></p>
````````

```````` example
[click](javascript:alert(1)) [data](data:text/html;base64,AAAA) [file](docs/readme)
.
<p>click data file</p>
.
[
  {"kind": "entity", "hint": "docs", "slug": "readme"}
]
````````

```````` example
[*em* text](HTTPS://EXAMPLE.COM/?a=1&b=2 "say \"hi\"")
.
<p><a href="HTTPS://EXAMPLE.COM/?a=1&amp;b=2" title="say &quot;hi&quot;"><em>em</em> text</a></p>
````````

A destination in `<…>` may contain spaces.

```````` example
[a](<https://example.com/a b>)
.
<p><a href="https://example.com/a%20b">a</a></p>
````````

Links can't contain links, and brackets without a destination are text.

```````` example
[a [b](https://b.example) c](https://a.example) [not a link]
.
<p>[a <a href="https://b.example">b</a> c](https://a.example) [not a link]</p>
````````

## Images

`![alt](url "title")`. Only `https` images render; any other source renders the alt text alone. Emphasis in the alt text becomes plain text.

```````` example
![A *harbor* map](https://example.com/map.png "Harbor")
.
<p><img src="https://example.com/map.png" alt="A harbor map" title="Harbor"></p>
````````

```````` example
![insecure](http://example.com/m.png) ![script](javascript:alert(1))
.
<p>insecure script</p>
````````

```````` example
[![map](https://example.com/m.png)](https://example.com)
.
<p><a href="https://example.com"><img src="https://example.com/m.png" alt="map"></a></p>
````````

## Autolinks

A URL or email address in `<…>` becomes a link, subject to the same scheme rules.

```````` example
<https://example.com> <gm@example.com> <javascript:alert(1)>
.
<p><a href="https://example.com">https://example.com</a> <a href="mailto:gm@example.com">gm@example.com</a> javascript:alert(1)</p>
````````

## Raw HTML

Raw HTML is not part of LorenzoScript: it renders as the text it is.

```````` example
<b onclick="x">bold</b>

<div>
block
</div>
.
<p>&lt;b onclick=&quot;x&quot;&gt;bold&lt;/b&gt;</p>
<p>&lt;div&gt;
block
&lt;/div&gt;</p>
````````

HTML entity references aren't decoded either.

```````` example
&copy; &amp;
.
<p>&amp;copy; &amp;amp;</p>
````````

## Backslash escapes

A backslash before any ASCII punctuation character makes it literal. Before anything else, the backslash is itself literal.

```````` example
\*not em\* \# \[x\] a\\b \a
.
<p>*not em* # [x] a\b \a</p>
````````

```````` example
\# not a heading

\- not a list

1\. not a list either
.
<p># not a heading</p>
<p>- not a list</p>
<p>1. not a list either</p>
````````

## Strikethrough, subscript, superscript

`~~text~~` is struck through, `~text~` is subscript, and `^text^` is superscript. They pair only with a run of the same length, and work inside words.

```````` example
~~gone~~, H~2~O, 2^10^ and E = mc^2^
.
<p><del>gone</del>, H<sub>2</sub>O, 2<sup>10</sup> and E = mc<sup>2</sup></p>
````````

Sub- and superscripts can't contain spaces, and delimiters that aren't pressed against text stay text, so tildes and carets in ordinary writing stay what they are.

```````` example
~5 to ~10, a ~~~ b, x^2 + y^2, ~~a wider strike~~
.
<p>~5 to ~10, a ~~~ b, x^2 + y^2, <del>a wider strike</del></p>
````````

## Tables

GitHub's syntax: a header row, a delimiter row of `-` with optional `:` for alignment, then body rows up to a blank line. Rows with too few cells are padded, and `\|` is a literal pipe.

```````` example
| Item | Cost | Weight |
| :--- | ---: | :----: |
| Rope | 1 gp | 10 lb |
| Torch \| lantern | `2 cp` |
.
<table>
<thead>
<tr>
<th align="left">Item</th>
<th align="right">Cost</th>
<th align="center">Weight</th>
</tr>
</thead>
<tbody>
<tr>
<td align="left">Rope</td>
<td align="right">1 gp</td>
<td align="center">10 lb</td>
</tr>
<tr>
<td align="left">Torch | lantern</td>
<td align="right"><code>2 cp</code></td>
<td align="center"></td>
</tr>
</tbody>
</table>
````````

A table can start right under a paragraph line. The header and delimiter rows must have the same number of cells.

```````` example
Prices:
| a | b |
|---|---|

| a | b |
| --- |
.
<p>Prices:</p>
<table>
<thead>
<tr>
<th>a</th>
<th>b</th>
</tr>
</thead>
</table>
<p>| a | b |
| --- |</p>
````````

## Footnotes

`[^label]` refers to a footnote defined anywhere by `[^label]: text`, continued by lines indented 4 spaces. Labels ignore case. Footnotes are numbered in the order they're first referred to, and listed at the end with a link back. A reference to an undefined label is text, and a footnote nobody refers to isn't listed.

```````` example
Ashfang was forged in Emberdeep.[^forge] It remembers.[^Forge]

[^forge]: By the smith *Oda*,
    who never spoke of it again.
.
<p>Ashfang was forged in Emberdeep.<sup class="ls-fnref"><a href="#ls-fn-1" id="ls-fnref-1">1</a></sup> It remembers.<sup class="ls-fnref"><a href="#ls-fn-1" id="ls-fnref-1-2">1</a></sup></p>
<section class="ls-footnotes">
<ol>
<li id="ls-fn-1">
<p>By the smith <em>Oda</em>,
who never spoke of it again. <a href="#ls-fnref-1" class="ls-backref" aria-label="Back to reference 1">↩</a></p>
</li>
</ol>
</section>
````````

```````` example
First[^b], second[^a], missing[^c].

[^a]: Alpha.
[^b]: Beta.
[^unused]: Never cited.
.
<p>First<sup class="ls-fnref"><a href="#ls-fn-1" id="ls-fnref-1">1</a></sup>, second<sup class="ls-fnref"><a href="#ls-fn-2" id="ls-fnref-2">2</a></sup>, missing[^c].</p>
<section class="ls-footnotes">
<ol>
<li id="ls-fn-1">
<p>Beta. <a href="#ls-fnref-1" class="ls-backref" aria-label="Back to reference 1">↩</a></p>
</li>
<li id="ls-fn-2">
<p>Alpha. <a href="#ls-fnref-2" class="ls-backref" aria-label="Back to reference 2">↩</a></p>
</li>
</ol>
</section>
````````

## Abbreviations

A line `*[term]: explanation`, anywhere in the text, marks every whole-word, same-case use of the term outside code.

```````` example
The HTML spec, not the HTMLX one, nor `HTML` in code.

*[HTML]: Hyper Text Markup Language
.
<p>The <abbr title="Hyper Text Markup Language">HTML</abbr> spec, not the HTMLX one, nor <code>HTML</code> in code.</p>
````````

## Attributes

`{#id .class}` gives an id and classes to the heading it ends, to a fenced code block (after its language), or to the inline element right before it: emphasis, a link, an image, code, or math. Anything else in braces is text, including attributes with values, so no style or event handler can be set.

```````` example
# Ashfang {#sword .relic}

A *flaming*{.fire} blade, see [the forge](#forge){.quiet} and `lit`{#code}.

![Sketch](https://example.com/ashfang.png){.wide}

*unattached {.x}* {#y} *x*{onclick=alert(1)} *y*{.a"b}

```js {.small #listing}
burn();
```
.
<h1 id="ls-sword" class="relic">Ashfang</h1>
<p>A <em class="fire">flaming</em> blade, see <a href="#ls-forge" class="quiet">the forge</a> and <code id="ls-code">lit</code>.</p>
<p><img src="https://example.com/ashfang.png" alt="Sketch" class="wide"></p>
<p><em>unattached {.x}</em> {#y} <em>x</em>{onclick=alert(1)} <em>y</em>{.a&quot;b}</p>
<pre id="ls-listing" class="small"><code class="language-js">burn();
</code></pre>
````````

## Class blocks and spans

A line holding only `{{` and classes or an id opens a block, closed by a line holding only `}}`. Class blocks nest and can contain anything. Inside a paragraph, `{{.class text}}` is a span. Classes only style text, they never hide it: who can read a text is decided by the information it belongs to, not by its markup.

```````` example
{{.monster .frame
## Goblin
Small, green, *cross*.

{{.stats
AC 15
}}
}}
.
<div class="monster frame">
<h2 id="ls-goblin">Goblin</h2>
<p>Small, green, <em>cross</em>.</p>
<div class="stats">
<p>AC 15</p>
</div>
</div>
````````

```````` example
The door is {{.note #door trapped, DC 15}} and {{.x unclosed.
.
<p>The door is <span id="ls-door" class="note">trapped, DC 15</span> and {{.x unclosed.</p>
````````

## Table of contents

`{{TOC}}` on its own line lists every heading in the text, nested by level, linking to each. Any other `{{name …}}` is text.

```````` example
{{TOC}}

# Weapons
## Swords
### Ashfang
## Bows
# Armor

{{unknown thing}}
.
<nav class="ls-toc">
<ul>
<li><a href="#ls-weapons">Weapons</a>
<ul>
<li><a href="#ls-swords">Swords</a>
<ul>
<li><a href="#ls-ashfang">Ashfang</a></li>
</ul>
</li>
<li><a href="#ls-bows">Bows</a></li>
</ul>
</li>
<li><a href="#ls-armor">Armor</a></li>
</ul>
</nav>
<h1 id="ls-weapons">Weapons</h1>
<h2 id="ls-swords">Swords</h2>
<h3 id="ls-ashfang">Ashfang</h3>
<h2 id="ls-bows">Bows</h2>
<h1 id="ls-armor">Armor</h1>
<p>{{unknown thing}}</p>
````````

## Math

`$…$` is inline math and `$$…$$` is display math, written in a subset of TeX and rendered as MathML, which browsers draw natively. Inline math can't start or end with a space or be followed by a digit, so prices stay prices.

```````` example
The area is $\pi r^2$, and $5 and $10 are prices.
.
<p>The area is <math><mi>π</mi><msup><mi>r</mi><mn>2</mn></msup></math>, and $5 and $10 are prices.</p>
````````

A line holding only `$$` opens a math block, closed by the next such line, and `$$…$$` alone on its line is a one-line block. Inside a block, a line starting with `-` is still math, not a list.

```````` example
$$\sum_{i=1}^{n} \frac{1}{i^2} \le \sqrt[3]{x_1}$$

$$
P(\text{hit}) = \left( \frac{21 - AC}{20} \right), \binom{n}{k}, \Delta, \lim_{x \to 0} \sin x
- 1
$$
.
<math display="block"><munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi></munderover><mfrac><mn>1</mn><msup><mi>i</mi><mn>2</mn></msup></mfrac><mo>≤</mo><mroot><msub><mi>x</mi><mn>1</mn></msub><mn>3</mn></mroot></math>
<math display="block"><mi>P</mi><mo>(</mo><mtext>hit</mtext><mo>)</mo><mo>=</mo><mrow><mo>(</mo><mfrac><mrow><mn>21</mn><mo>−</mo><mi>A</mi><mi>C</mi></mrow><mn>20</mn></mfrac><mo>)</mo></mrow><mo>,</mo><mrow><mo>(</mo><mfrac linethickness="0"><mi>n</mi><mi>k</mi></mfrac><mo>)</mo></mrow><mo>,</mo><mi mathvariant="normal">Δ</mi><mo>,</mo><munder><mo movablelimits="true" form="prefix">lim</mo><mrow><mi>x</mi><mo>→</mo><mn>0</mn></mrow></munder><mi>sin</mi><mi>x</mi><mo>−</mo><mn>1</mn></math>
````````

The subset covers letters and numbers, scripts (`^`, `_`, primes), `\frac`, `\binom`, `\sqrt`, `\left…\right`, Greek letters, the common relations, arrows, set and logic symbols, big operators with limits (`\sum`, `\prod`, `\int`, …), function names (`\sin`, `\log`, `\lim`, …), accents (`\hat`, `\bar`, `\vec`, …), spacing, `\text{…}`, and `\operatorname{…}`; see [ADR 0102](../../docs/adr/0102-lorenzoscript-standard-extensions.md) for the full list. A formula using anything else, such as `\\`, `&`, or `\begin`, is shown as its TeX source rather than half-rendered. Everything is escaped either way.

```````` example
Inline display $$x^2$$ works; $\begin{matrix} a \end{matrix}$ and $a \\ b$ don't, and $x < y$ and $\text{<b>}$ are safe.
.
<p>Inline display <math display="block"><msup><mi>x</mi><mn>2</mn></msup></math> works; <code class="ls-math">\begin{matrix} a \end{matrix}</code> and <code class="ls-math">a \\ b</code> don't, and <math><mi>x</mi><mo>&lt;</mo><mi>y</mi></math> and <math><mtext>&lt;b&gt;</mtext></math> are safe.</p>
````````

## Entity links and images

A link whose target is a slug names an entity: `[text](ashfang)`. A view hint can go before the slug, as in `[text](being/ashfang)`. It says how to show the entity, not which one: a sentient sword can be opened as a being or as loot. Slugs here are used exactly as written.

`[[Name]]` links by name. The slug is the name made lowercase, ASCII, and hyphenated, as for heading ids. `[[Name|text]]` changes the text, and `[[hint/Name]]` adds a hint.

The resolver decides where a reference leads, with the viewer's own permissions. A reference it doesn't resolve renders as plain text, however it was written. Something that doesn't exist and something this viewer may not see look exactly alike.

```````` example
Ashfang ([[Ashfang]]) hangs by [the old sword](old-sword "Grandmother's").
As a companion: [[being/Ashfang|the sword]]; as loot: [it](item_instance/ashfang).
.
<p>Ashfang (<a href="/entity/ashfang" title="Ashfang" class="ls-entity">Ashfang</a>) hangs by <a href="/entity/old-sword" title="Grandmother's" class="ls-entity">the old sword</a>.
As a companion: <a href="/being/ashfang" title="Ashfang" class="ls-entity">the sword</a>; as loot: <a href="/item_instance/ashfang" title="Ashfang" class="ls-entity">it</a>.</p>
.
[
  {"kind": "entity", "hint": "", "slug": "ashfang"},
  {"kind": "entity", "hint": "", "slug": "old-sword"},
  {"kind": "entity", "hint": "being", "slug": "ashfang"},
  {"kind": "entity", "hint": "item_instance", "slug": "ashfang"}
]
````````

A name with no letters or digits to slug stays text, brackets included. A relative link is an entity reference too, since Lorenzo text has no relative URLs. `references()` lists each reference once, in order of first use.

```````` example
[[Old Sword]], [[The Lost Crown]], [[日本]], [notes](page-2), and [[old sword]] again.
.
<p><a href="/entity/old-sword" title="Old Sword" class="ls-entity">Old Sword</a>, The Lost Crown, [[日本]], notes, and <a href="/entity/old-sword" title="Old Sword" class="ls-entity">old sword</a> again.</p>
.
[
  {"kind": "entity", "hint": "", "slug": "old-sword"},
  {"kind": "entity", "hint": "", "slug": "the-lost-crown"},
  {"kind": "entity", "hint": "", "slug": "page-2"}
]
````````

An image whose target is a slug shows that entity's picture, whatever `externalImages` says, since the picture isn't external.

```````` example
![Ashfang, drawn](ashfang) ![The crown](the-lost-crown) ![Map](https://example.com/map.png)
.
<p><img src="/pictures/ashfang.png" alt="Ashfang, drawn" title="Ashfang" class="ls-entity"> The crown <img src="https://example.com/map.png" alt="Map"></p>
.
[
  {"kind": "image", "hint": "", "slug": "ashfang"},
  {"kind": "image", "hint": "", "slug": "the-lost-crown"}
]
````````

## Dates

`{{date YYYY-MM-DD}}` is a real-world date, written the one unambiguous way and shown in the reader's own format. Something that isn't a day that exists stays text.

```````` example
The session is on {{date 2026-09-24}}; {{date 2026-02-30}} and {{date tomorrow}} aren't dates.
.
<p>The session is on <time datetime="2026-09-24">24 September 2026</time>; {{date 2026-02-30}} and {{date tomorrow}} aren't dates.</p>
.
[
  {"kind": "date", "date": "2026-09-24"}
]
````````

## Calendar dates

`{{cal …}}` is a date in a world's own calendar. Calendars aren't modelled yet, so it shows as written unless the resolver can read it. A `{{cal}}` with nothing in it is text.

```````` example
The coronation was {{cal harptos 1492-mirtul-12}}, the siege {{cal harptos 1491-ches-3}}, and {{cal}} is text.
.
<p>The coronation was <span class="ls-cal">12 Mirtul 1492 DR</span>, the siege <span class="ls-cal">harptos 1491-ches-3</span>, and {{cal}} is text.</p>
.
[
  {"kind": "calendar", "expression": "harptos 1492-mirtul-12"},
  {"kind": "calendar", "expression": "harptos 1491-ches-3"}
]
````````

References are collected from the whole text, headings and footnotes included.

```````` example
# Session {{date 2026-09-24}}

We met [[Ashfang]].[^1]

[^1]: Or rather, [[being/Ashfang]] met us.
.
<h1 id="ls-session-2026-09-24">Session <time datetime="2026-09-24">24 September 2026</time></h1>
<p>We met <a href="/entity/ashfang" title="Ashfang" class="ls-entity">Ashfang</a>.<sup class="ls-fnref"><a href="#ls-fn-1" id="ls-fnref-1">1</a></sup></p>
<section class="ls-footnotes">
<ol>
<li id="ls-fn-1">
<p>Or rather, <a href="/being/ashfang" title="Ashfang" class="ls-entity">Ashfang</a> met us. <a href="#ls-fnref-1" class="ls-backref" aria-label="Back to reference 1">↩</a></p>
</li>
</ol>
</section>
.
[
  {"kind": "date", "date": "2026-09-24"},
  {"kind": "entity", "hint": "", "slug": "ashfang"},
  {"kind": "entity", "hint": "being", "slug": "ashfang"}
]
````````

Code, math, and escaped brackets hold no references. Every other block does, however deeply it's nested: quotes, lists, tables, and class blocks.

```````` example
`[[Ashfang]]`, $[a](b)$ and \[[Ashfang]] hold no references.

    [[old-sword]] in code

> - [[Old Sword]] in a list in a quote
>
>   | Who | When |
>   | --- | --- |
>   | ![Ashfang](ashfang) | {{date 2026-09-24}} |

{{.note
A [note](item/old-sword) in a class block.
}}
.
<p><code>[[Ashfang]]</code>, <math><mo>[</mo><mi>a</mi><mo>]</mo><mo>(</mo><mi>b</mi><mo>)</mo></math> and [[Ashfang]] hold no references.</p>
<pre><code>[[old-sword]] in code
</code></pre>
<blockquote>
<ul>
<li>
<p><a href="/entity/old-sword" title="Old Sword" class="ls-entity">Old Sword</a> in a list in a quote</p>
<table>
<thead>
<tr>
<th>Who</th>
<th>When</th>
</tr>
</thead>
<tbody>
<tr>
<td><img src="/pictures/ashfang.png" alt="Ashfang" title="Ashfang" class="ls-entity"></td>
<td><time datetime="2026-09-24">24 September 2026</time></td>
</tr>
</tbody>
</table>
</li>
</ul>
</blockquote>
<div class="note">
<p>A <a href="/item/old-sword" title="Old Sword" class="ls-entity">note</a> in a class block.</p>
</div>
.
[
  {"kind": "entity", "hint": "", "slug": "old-sword"},
  {"kind": "image", "hint": "", "slug": "ashfang"},
  {"kind": "date", "date": "2026-09-24"},
  {"kind": "entity", "hint": "item", "slug": "old-sword"}
]
````````

A reference counts once per slug and hint, however it's written. A footnote's text counts even if nothing cites it, but only the first definition of a label is read.

```````` example
[[Ashfang]], [the sword](ashfang), and [[ashfang]] are one reference; [it](being/ashfang) is another.

[^a]: Never cited, but still read: [[Old Sword]].
[^A]: The same label again, so ignored: {{date 2026-01-01}}.
.
<p><a href="/entity/ashfang" title="Ashfang" class="ls-entity">Ashfang</a>, <a href="/entity/ashfang" title="Ashfang" class="ls-entity">the sword</a>, and <a href="/entity/ashfang" title="Ashfang" class="ls-entity">ashfang</a> are one reference; <a href="/being/ashfang" title="Ashfang" class="ls-entity">it</a> is another.</p>
.
[
  {"kind": "entity", "hint": "", "slug": "ashfang"},
  {"kind": "entity", "hint": "being", "slug": "ashfang"},
  {"kind": "entity", "hint": "", "slug": "old-sword"}
]
````````

A link inside a link's text wins, so the outer one stays text. An image may hold a link; the image counts first, then what's inside it.

```````` example
[outer [inner](old-sword) text](ashfang) and ![a [b](the-lost-crown) picture](ashfang)
.
<p>[outer <a href="/entity/old-sword" title="Old Sword" class="ls-entity">inner</a> text](ashfang) and <img src="/pictures/ashfang.png" alt="a b picture" title="Ashfang" class="ls-entity"></p>
.
[
  {"kind": "entity", "hint": "", "slug": "old-sword"},
  {"kind": "image", "hint": "", "slug": "ashfang"},
  {"kind": "entity", "hint": "", "slug": "the-lost-crown"}
]
````````

## Nesting limit

Blockquotes and lists nest at most 32 levels deep, and so do inline elements (emphasis, links, images). Anything deeper renders as text. Real text never gets near this. It exists because text is written by one person and rendered in someone else's browser, so no input may exhaust the renderer. The tests for it live next to the example runner, since 33 levels of nesting don't make a readable example.

## Deviations from CommonMark

- No raw HTML, and no HTML entity references.
- No setext headings.
- No reference-style links (`[text][ref]` with a `[ref]: url` definition).
- `_`/`__` render `<i>`/`<b>` instead of repeating `*`/`**`.
- Only the URL schemes above are rendered as links or images.
- Output is HTML5 (`<br>`, `<hr>`), not XHTML.
- Lazy continuation is decided by the previous line alone (is it paragraph text once its quote and list markers are set aside?), not by a full parse, which keeps it linear.
- The nesting limit above.
- The parser doesn't aim for every corner of CommonMark's list and lazy-continuation rules; this file, not CommonMark's spec, is what LorenzoScript does.
