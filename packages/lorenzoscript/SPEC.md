# LorenzoScript

LorenzoScript is Lorenzo's Markdown dialect, used for every description text ([RFC 0027](../../docs/rfcs/0027-lorenzoscript.md)). It follows [CommonMark](https://spec.commonmark.org/)'s structure, with the deviations listed at the end of this file.

This file is both the definition and the test suite ([ADR 0100](../../docs/adr/0100-lorenzoscript-core-parser-and-renderer.md)). Every `example` block below is run as a test: the LorenzoScript source, a line holding only `.`, then the HTML it must render to. In examples, `␠` stands for a trailing space and `→` for a tab.

This file currently covers the core syntax (RFC 0027 stage 1). Extensions get their own sections as later stages land.

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
<h1>one</h1>
<h2>two</h2>
<h6>six</h6>
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
<h2>closing</h2>
<h1>foo#</h1>
````````

```````` example
# An *emphasized* title
.
<h1>An <em>emphasized</em> title</h1>
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
<h1>heading</h1>
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
<h1>Title</h1>
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

`[text](url "title")`. Only `http`, `https`, `mailto`, and in-document `#fragment` links become links; any other target renders its text alone. Fragments are rewritten to the `ls-` prefix every author id carries.

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
