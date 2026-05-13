---
name: render
description: Step 3 of the lee-espanol pipeline. Read the Spanish story at stories/NN-slug/story.md and its enrichment data at stories/NN-slug/enrichment.toml (sibling files in the same NN-slug folder), then produce a fully self-contained, thematically unique HTML page at stories/NN-slug/index.html in the same folder, and refresh the project-wide table-of-contents at index.html. Each render is bespoke design (palette, typography, inline SVG, CSS textures) reflecting the story's tone; every Spanish word is wrapped with a Russian-language popup carrying translation + POS + lemma + optional grammar block + SpanishDict link (proper nouns get explanation popups without the link). Use when the user asks to "render the story", "make HTML", "build page", or invokes /render.
---

# render

Step **3** of the 3-step lee-espanol pipeline. Turns a `.md` story + its `.toml` enrichment into a hand-designed, self-contained HTML page. Each render is **fully unique** in design — no shared base template — but follows the same functional contract for the hover-popup vocabulary system. The reader's L1 is **Russian**, so popup translations, POS labels, and grammar explanations are all in Russian.

## Inputs

- **Source story**: `stories/NN-slug/story.md` (frontmatter + Spanish body)
- **Enrichment**: `stories/NN-slug/enrichment.toml` (vocabulary + sentence translations, produced by the `enrich` skill)
- **Reader profile**: `profile.md` (for tone calibration)

If the user does not specify which story, scan all `stories/NN-slug/` subfolders, find those that contain both `story.md` and `enrichment.toml` but **no `index.html`** yet, and pick the most recent one; confirm with the user before generating.

If `enrichment.toml` is missing, **stop and tell the user to run `/enrich` first**. Do not attempt to inline-generate translations during render — that defeats the pipeline separation.

## Output

A single self-contained file: `stories/NN-slug/index.html` — written into the same `stories/NN-slug/` folder that already contains `story.md` and `enrichment.toml`. No separate CSS/JS files; everything inlined. External dependencies allowed: Google Fonts CDN only (no other CDNs, no analytics, no trackers).

## Design contract — fully unique per story

**Always invoke the `frontend-design` skill before designing the page.** Use its guidance to push past generic AI design defaults; then apply the result to the story's specific tone, setting, protagonist, and ending. The goal is a curated print-quality artifact, not a templated learner page.

Each render must invent, from scratch, design choices driven by the story's frontmatter and content:

- **Color palette**: derive 3–6 colors from the story's setting and tone. Examples:
  - AI on Saturn (cold, contemplative) → deep navy, silver-ice, faint gold accents on the rings
  - Nueva Andalucía (religious archaic colony) → terracotta, ochre, gold leaf, dark wine
  - Kuiper Belt (icy, ironic, lonely) → near-black void, harsh cyan, dirty white, single hazard-orange accent
- **Typography**: pair two Google Fonts — one for display (title, headings) and one for body. Choose to evoke the story's mood (e.g. *Cinzel* + *EB Garamond* for medieval; *Space Grotesk* + *JetBrains Mono* for hard sci-fi; *Cormorant Garamond* + *Inter* for contemplative). Never reuse the same pairing across stories.
- **Inline SVG illustration**: hand-coded SVG (50–300 lines) thematic to the story — abstract or representational, stylized, never photorealistic. Place as hero, marginalia, or section break. Must be original to this render.
- **CSS background texture / decoration**: subtle gradients, blur, noise (via SVG filter), conic patterns, scanlines, vignettes — whatever fits the mood. Layered, atmospheric, not loud.
- **Layout / composition**: vary aggressively across stories. **Avoid defaulting to a single narrow horizontally centered text column** — that is the AI-design comfort zone and reads as generic across stories. Reserve the centered-column choice for stories that explicitly benefit from minimalism (intimate monologue, brief confessional letter, museum-placard quiet). Otherwise, reach for editorial, cinematic, atmospheric, spatially expressive compositions. See "Layout philosophy — editorial, cinematic, spatial" below for the full toolkit and constraints.
- **Reading width**: ~640–720px max for body text; never less than 18px font-size; line-height 1.7–1.9 for A1 readers.
- **Ambient background motion** (optional, encouraged): a subtle, slow CSS-only or SMIL-driven layer behind the text that reinforces the story's mood — drifting starfield for cold sci-fi, slow conic-gradient drift for manuscript-warm, faint flicker / scanlines for hard sci-fi, ink-bleed wash for contemplative. Keep it at low opacity, slow (multi-second cycles), and behind text. Never animate the body text itself, and never use motion that competes with reading. Always pure CSS keyframes or inline animated SVG — **no raster GIFs**, no external image URLs.
- **Refined popup entrance** (optional): override the default `.pop` / `.pop.show` transition in the page's own design language — e.g. add `filter: blur(6px) → 0`, a small `translateY`, or a soft `scale(0.96) → 1` to give the popup a story-themed reveal. The behavior invariants (`opacity`, `pointer-events`, the `::after` bridge) must stay intact — only enrich, don't replace. Similarly, the `.w:hover` underline can animate (e.g. a `linear-gradient` background-size growing from 0 to 100% on hover) instead of the static dotted line.

Distinctive ≠ chaotic. Each page should feel like a curated print artifact, not a random theme dump. If two consecutive renders feel similar, push harder on differentiation. Motion is decorative — every animation must remain readable, slow, and quiet.

## Layout philosophy — editorial, cinematic, spatial

Treat the page as a designed spread, not a text dump piped into a column. The renderer should compose space deliberately — text, illustration, framing chrome, and ambient layers arranged like an editorial print spread or a sci-fi publication, while remaining fully static HTML/CSS. The narrow-centered-column default is the path of least resistance and the easiest tell of generic AI design; only choose it when minimalism is the right answer for *this* story.

### Permitted and encouraged techniques

- **Asymmetrical layouts** — text weighted off-axis, grids that break neatly, alignment shifted left or right rather than centered around the page midline
- **Offset or floating text regions** — paragraph blocks at varied indents, callout blocks pulled into the margin, hanging headings, prose that wraps around illustration or framing chrome
- **Side annotations or contextual panels** — protagonist's marginalia, parallel-column footnotes, paratextual stamps and labels along an edge, datasheet metadata in a sidebar
- **Pull quotes and highlighted fragments** — a single sentence enlarged in a contrasting face, framed by hairlines, color blocks, or generous negative space
- **Split-screen compositions** — two-pane layouts where one side carries prose and the other carries inline SVG, telemetry, a portrait, or contrasting type
- **Layered gradients and atmospheric backgrounds** — multiple gradient stops, conic + radial + linear combined, behind faint SVG noise, vignettes, or filter blurs
- **Modular sections with distinct visual tone** — different blocks of the story styled differently (e.g. a journal section vs. a console section vs. a flashback section on the same page), each with its own micro-treatment
- **Controlled whitespace and experimental spacing** — generous gutters between blocks, unconventional line-lengths per region, intentional "negative space" passages between scenes
- **Multi-column excerpts** — newspaper-style or manuscript-style multi-column passages for specific blocks (not necessarily the whole story)
- **Embedded "terminal", "transmission", or "log" blocks** — monospace box-drawn frames, timestamped lines, signal-trace panels, console output dropped inline among the prose
- **Visual framing inspired by futuristic interfaces or sci-fi publications** — HUD chrome, dashboard panels, magazine masthead, editorial drop caps, datasheet headers, signal-trace strips

These techniques **compose**. A page can be a split-screen with a side-annotation column on the prose pane and an embedded transmission log on the other; or an asymmetric editorial spread with a pull quote, multi-column lower section, and a layered gradient under everything. Lean into the story's content (see "Structural variety" notes in the `story` skill — if the source `.md` already segments into logs, journal entries, or scene fragments, distribute those across the page rather than concatenating them into one column).

### Constraints — non-negotiable

- **Readability has priority.** Body text never drops below 18 px, line-height 1.7–1.9, contrast ratio ≥ 4.5:1 against its background. Every decorative pass must improve the page; if a flourish hurts reading, cut it.
- **Layouts must remain responsive.** Use fluid units (`clamp()`, `minmax()`, percentages, `vw/vh`), CSS Grid and Flexbox. Multi-column, split-screen, and floating regions must collapse to a clean single column on narrow viewports — no horizontal scroll, no overlapping text, no truncated panels on mobile.
- **Semantic HTML stays intact.** Story body still lives inside `<article data-story-body>` with real `<p>`, `<h1>`, `<h2>`, `<blockquote>`, `<aside>`, `<figure>` tags. Don't replace paragraphs with `<div>` salad to hit a visual; don't strip headings for compactness; don't break the structure the popup tokenizer depends on (paragraphs of text inside the `data-story-body` element).
- **Contrast and typography stay accessible.** Real font sizes, real line-height, real color contrast — including inside framed panels, marginalia, and split panes. Decorative scripts or display faces belong on titles, pull quotes, and metadata strips — never on the body prose.
- **Decorative effects never overpower the story text.** Ambient gradients, framing chrome, marginalia, and split-pane visuals stay quieter than the prose. If the eye lands on the decoration before the words, dial it back. Pull quotes and highlights are the one allowed exception, and only because they *are* story text.
- **Motion is avoided unless explicitly requested.** Default to fully static. The "ambient background motion" and "refined popup entrance" options earlier in this contract are opt-in, not default; they apply when the story or the user clearly calls for atmosphere. When motion is used, follow the existing motion rules (slow, low-opacity, behind text, `prefers-reduced-motion` respected, no raster GIFs).

## Found-document framing

Every render is treated as **a specific in-universe artifact**, not "a story page about X". The page IS the document the protagonist would produce, receive, or be cataloged into — a found object the reader has stumbled on. This is the primary discipline that forces real variety; without it, even careful palette/font work drifts toward "yet another centered serif column on a dark bg".

Each story has at least one natural artifact to pick from. Examples:

| Protagonist | Natural artifact |
|-------------|-----------------|
| AI / station observatory | terminal log, telemetry readout, system console output |
| Anthropologist | field journal, ethnographic notes, expedition diary |
| Navigator / captain | ship's bridge log, course-correction sheet, bridge HUD |
| Biologist | lab notebook, specimen plate, sample-jar label sheet |
| Linguist / translator | translation worksheet, gloss table, parallel-column manuscript |
| Old colonist | handwritten letter, memorial placard, parish chronicle entry |
| Maintenance engineer | maintenance log, parts diagram, ship's wiring schematic |
| Astronomer | observation log, signal trace plot, deep-survey night sheet |
| Cargo captain | bill of lading, customs declaration, dock-side manifest |
| Programmer | source file with comments, ticket queue, on-call runbook |

The framing shapes **every** decision: title becomes a document header (e.g. *"OBSERVATION LOG · ESTACIÓN CASIOPEA · TURNO 02:00"*), metadata becomes the document's metadata (file number, paper stock, redactions, stamps), the prose lives where it would live on that artifact (numbered log entries, journal pages, form fields, gridded notebook), and decorations are the artifact's natural marks (timestamps, signatures, perforations, ink bleeds, registration crosses, censor bars). The Spanish body text still reads as continuous prose to the reader, but is *housed* inside the artifact's structure.

Anti-pattern: the protagonist's profession leaks into a few decorative SVGs but the underlying page is still "centered serif column". That fails this discipline.

## Format archetypes — variety rule

Pick the artifact's format from the named-archetype list below. The list is illustrative, not exhaustive — invent new archetypes when the story warrants. **Anti-repeat rule**: no archetype reused within 3 consecutive stories. After three stories away, an archetype may return, but the second take must be a visibly fresh interpretation (different palette, different layout primitive, different motion family) — never a re-skin of the first.

Named archetypes (mix freely with new ones):

- **Terminal / system log** — monospace amber-on-black or green-on-black, timestamped lines, blinking cursor, ANSI box-drawing chrome
- **Manuscript folio** — parchment, two-column with marginalia, illuminated drop cap, calligraphic display, rubricated initials
- **Observation log / lab notebook** — gridded or ruled paper, handwriting body, monospace headers, plotted traces, marginal scribbles
- **Customs form / port manifest** — bureaucratic grid, stamped fields, typewriter monospace, carbon-copy ink, official seal corner
- **Telegram tape** — narrow column, perforation strip, ALL CAPS, STOP between sentences, ribbon-typewriter ink
- **Magazine / newsprint spread** — multi-column halftone, era-specific display face, byline strip, pull-quote
- **Museum placard / wall text** — gallery serif, paired columns, generous whitespace, brass-plaque header, plain background
- **Bridge HUD / instrument readout** — vector lines, faux-radar, scanlines, sci-fi sans, telemetry numerals
- **Handwritten letter** — paper texture, handwriting body, return-address block, postmark, signature flourish
- **Field journal** — leather-board frame, pressed-plant illustrations, dated entries, ink-bleed, weathered paper
- **Index card / library catalog card** — 3×5 ruled card, monospace, hand-stamped accession number
- **Postcard** — illustration top, prose-on-the-back layout, stamp + postmark
- **Parish chronicle / annal** — heavy display caps for the year, single-column with rubricated marks, ecclesiastical serif
- **Engineering schematic** — line-art, callouts, parts list along the margin, drafting-style sans

The archetype determines: page chrome and "edges" (paper, console frame, card border), typography family, palette discipline (paper inks vs. console phosphors vs. plate-printed CMYK), layout primitive (single column / two-column / framed / gridded / freeform marginalia), motion sensibility (paper rustle vs. scanline drift vs. ink bleed vs. dial sway), and **what the metadata strip becomes** (file number, accession, dispatch number, frequency band, postal stamp).

**Archetype log**: read the last 3 lines of `.ai/archetypes.jsonl` (one JSON object per line: `{"seq", "slug", "archetype", "palette", "font_pair"}`). Do not reuse any of those three archetypes (or their dominant palette / font pair) for the new render. After picking, append a one-line JSON entry for this story to the end of the file. This replaces the older "scan all prior `stories/*/index.html`" rule — that scan is no longer needed.

## Functional contract — same across all stories

### Tokenizing the body using the .toml

Walk the Spanish body of the .md, paragraph by paragraph. For each token:

| Token type | What to emit |
|------------|--------------|
| Word (Spanish letters incl. accents and `ñ`) | `<span class="w" data-tr="…" data-pos="…" data-lemma="…" data-grammar="…">word</span>` — values pulled from `[words.<lowercase(form)>]` in the .toml |
| Sentence-terminator (`.`, `?`, `!`) | `<span class="s" data-tr="…">.</span>` — `data-tr` is the next entry from the `[[sentences]]` array in the .toml |
| Digits (`412`, `78`) | plain text, no span |
| Other punctuation (`,`, `…`, `¿`, `¡`, opening/closing quotes) | plain text |
| Whitespace | preserved |

**Attribute escaping**: HTML-escape `<`, `>`, `&`, `"`, `'` inside attribute values. The grammar markup (`**`, `*`, `` ` ``, `[[…]]`) is **not** HTML — it stays as-is in the attribute and is parsed by the popup JS at show time.

**Lookup miss**: if a word is in the body but not in `[words.*]`, log a warning and skip wrapping that word (render as plain text). Surface the list of missed words to the user at the end.

**Proper nouns**: when `pos = "имя"` and no `lemma`, emit `data-lemma=""` so the JS knows to hide the SpanishDict link.

### Inline JS — popup behavior

Vanilla JS (~100–150 lines), no frameworks. Behavior:

- **Desktop**: hover shows the popup; mouseleave hides it
- **Mobile/touch**: tap shows; tap elsewhere hides
- Popup contents (in order):
  1. **Lemma line**: dictionary form (or the word itself for proper nouns), display font italic
  2. **POS**: small caps / tracked, muted
  3. **Translation**: Russian gloss
  4. **Grammar block** (only if `data-grammar` is non-empty): parsed at show time from the markdown-ish markup — see below
  5. **SpanishDict link**: only when `data-lemma` is present and non-empty. URL: `https://www.spanishdict.com/translate/<encoded-lemma>` — strip leading articles (`el `, `la `, `los `, `las `, `un `, `una `, `unos `, `unas `) before encoding.
- Sentence popups (`.s`) show **only** the Russian translation. No lemma line, no POS, no grammar, no link.

### Grammar block — markup parser (JS)

The popup JS must turn the `data-grammar` string into HTML. Recognised markers:

| Markup | Renders as | CSS-styled as |
|--------|------------|---------------|
| `**text**` | `<b>` | Spanish form, highlighted in accent color |
| `*text*` | `<i>` | small-caps grammar term (use display font / Cinzel-equivalent) |
| `` `text` `` | `<code>` | monospace inline, light contrasting background |
| `[[text]]` | `<u>` | "suffix highlight" — distinct accent, bold; works **inside** `<code>` too |
| blank line | new `<p>` | paragraph break |

**Parse order** (mandatory):

1. HTML-escape `&`, `<`, `>` in the source string
2. Split into paragraphs on `\n\n+`
3. For each paragraph, in this order:
   a. Replace `` `([^`]+)` `` with `<code>$1</code>` — **but first** replace `[[(...)]]` inside the captured group with `<u>$1</u>`
   b. Replace `\*\*([^*]+)\*\*` with `<b>$1</b>`
   c. Replace `\*([^*]+)\*` with `<i>$1</i>`
   d. Replace remaining `\[\[([^\]]+)\]\]` (outside code) with `<u>$1</u>`
4. Wrap each paragraph in `<p>…</p>` and join

Reference implementation (place inside the popup show function):

```js
function mdToHtml(md){
  if(!md) return '';
  md = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return md.split(/\n\n+/).map(function(p){
    p = p.replace(/`([^`]+)`/g, function(_, c){
      return '<code>' + c.replace(/\[\[([^\]]+)\]\]/g, '<u>$1</u>') + '</code>';
    });
    p = p.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    p = p.replace(/\*([^*]+)\*/g, '<i>$1</i>');
    p = p.replace(/\[\[([^\]]+)\]\]/g, '<u>$1</u>');
    return '<p>' + p + '</p>';
  }).join('');
}
```

### Grammar block — CSS spec

The grammar block lives inside the popup, between the translation line and the SpanishDict link. Mark it up as `<div class="g-block">…</div>`. Apply CSS in the story's own design language but respect these structural rules:

- A visible divider (border-top or hairline) separates `.tr` from `.g-block`
- `.g-block p` has tight vertical rhythm (small margins between paragraphs)
- `.g-block b` — Spanish form: italic + bold weight, accent color (e.g. oxblood / gold / ice)
- `.g-block i` — grammar term: small caps, display font, tracked, muted
- `.g-block code` — monospace, subtle contrasting background (faint paper / panel tint), thin border or radius
- `.g-block u` — no underline; instead a colored chip-style highlight (background tint + bold weight) so the suffix/morpheme stands out; the same style works whether `<u>` is nested inside `<code>` or stands alone

When `data-grammar` is non-empty, also add a `has-grammar` class to the popup so its `max-width` can grow (350–400px) to fit the extra content.

### Popup CSS — critical invariants

**Pointer-events while hidden**: do **not** set `pointer-events:auto` on the base `.pop` rule — the hidden popup must not capture mouse events, or it blocks `mouseover` on every word it visually covers.

```css
.pop{
  /* ...visual styling... */
  opacity:0;
  pointer-events:none;
  transition:opacity 0.15s,transform 0.15s;
}
.pop.show{
  opacity:1;
  pointer-events:auto;
}
```

**Hit-area continuity** (cursor must travel from word into popup without the popup closing): bridge the visual gap with an invisible `.pop::after` whose height matches the JS positioning offset (12 px).

```css
.pop::after{
  content:'';
  position:absolute;
  left:-12px;
  right:-12px;
  height:12px;
  bottom:-12px;
}
.pop.below::after{
  bottom:auto;
  top:-12px;
}
```

A taller bridge (e.g. 18 px) overlaps the line of words below the popup and creates a dead zone — hovering the top of those words lands on the bridge instead of the word, and no popup appears.

In the JS, the `mouseout` close check must test `relatedTarget.closest('.pop')` so that moving onto the bridge counts as staying in the popup.

### Motion contract — auto-injected

Two motion bits are auto-managed by `render.py` (alongside the popup invariants). Designers don't write them; they style or hide them.

- **Reading-progress hairline** — a `<div class="reading-progress">` is appended to `<body>` by the popup script. Its width tracks `scrollTop / (scrollHeight − clientHeight)`. CSS lives in `<style data-popup-invariants>`. The bar's color reads from the CSS variable `--accent` on `:root` or `body` (fallback `currentColor`). Each story should declare `:root { --accent: <story-color>; }` so the bar matches the palette. If the bar doesn't fit the design at all, hide it per-page with `.reading-progress { display: none; }` — but prefer themed over hidden.
- **`prefers-reduced-motion` guard** — a media query in `<style data-popup-invariants>` short-circuits all animations and transitions, and hides the reading bar entirely, when the user has opted out. Designer-authored motion (ambient backgrounds, popup entrance, hover-underline draws, SVG keyframes) must rely on the same global guard — that means doing your motion via standard `animation:` / `transition:` declarations rather than JS-driven `requestAnimationFrame` loops, so the global override takes effect. If you must use JS for motion, gate it on `window.matchMedia('(prefers-reduced-motion: reduce)').matches`.

### Story content rendering

- Title from frontmatter, set in the display font
- Story body: paragraphs separated cleanly, no inline learning sidebars, no keyword tables, no full-sentence translations visible on the page
- Optional unobtrusive metadata strip (date, length, level) at top or bottom — decorative strings, leave un-wrapped
- Pure Spanish in the visible body; Russian appears only inside popup DOM at hover time

### Back-link to the index

Every story page must include a discrete back-link to the project-wide table of contents. The story lives at `stories/NN-slug/index.html`, so the back-link climbs two levels:

```html
<a class="back" href="../../index.html">← Índice</a>
```

- Placed top-left, absolute-positioned outside the main column so it doesn't interfere with the layout
- Styled in the **page's own design language** (match typography, palette, weight). On a dark sci-fi page → tracked sans caps in muted gold; on a manuscript page → small caps Cinzel in ochre with dotted underline; etc.
- Hover state brightens to the page's main accent color
- Mobile: shrinks and tucks closer to the corner

### Index page (project-wide landing)

A single project-wide index lives at `index.html` (project root). It is a 2-column card grid, newest-first, so the most recent story sits at the top-left and is visible without scrolling.

**Aesthetic**: compact typewriter — explicitly **distinct** from any individual story's design (no parchment, no manuscript ornament, no sci-fi gold-on-navy, no SVG illustrations). Quiet, tight, hairline-bordered cards that frame the stories without competing visually.

- Background: warm off-white / paper (`#f5f3ec`)
- Text: typewriter-ink dark (`#1f1d18`) + greys; **no color accent** beyond grayscale
- Font: a single typewriter monospace family — *Courier Prime* (regular + bold + italic)
- Layout: double-rule masthead, brief intro paragraph, `Índice · N entradas` heading row, then a 2-column grid of hairline-bordered cards; thin colophon. Each card shows: top row `NN · YY·MM·DD`, the Spanish title in tracked uppercase, italic `protagonist · setting`, and `N palabras` at the bottom.
- No rounded corners, no shadows, no SVG illustrations, no big display numerals. Hairline rules only.
- Mobile: single column.

**Refresh policy**: rebuild the entries block every time a story is rendered. The helper script (`render.py`) maintains `.ai/stories-index.json` as a per-slug cache; rendering one story updates only that slug's entry and rewrites the entries block from the cache (incremental). `--index-only` and a missing/stale cache force a full disk rescan. Stories are sorted by folder name **descending** so seq 12 appears first.

Per-entry markup template (the `href` is relative to the project-root `index.html`):

```html
<a class="entry" href="stories/NN-slug/index.html">
  <div class="row1">
    <span class="num">{NN, two-digit}</span>
    <span class="date">{YY·MM·DD}</span>
  </div>
  <div class="e-title">{Spanish title}</div>
  <div class="meta">{protagonist} · {setting}</div>
  <div class="words">{length_words} palabras</div>
</a>
```

The back-link on each rendered story page must use `../../index.html` (two levels up from `stories/NN-slug/index.html`):

```html
<a class="back" href="../../index.html">← Índice</a>
```

## Helper script — design-first, then apply

A Python helper at `.ai/skills/render/render.py` separates **design** (your job) from **mechanical wiring** (its job). You write `index.html` freely — any palette, typography, layout, illustration. The script then walks the element marked `data-story-body`, wraps each word and sentence-terminator with the popup spans from `enrichment.toml`, and auto-injects the popup behavior CSS/JS.

There are **no locked sections inside your CSS or markup**. Style anything you want, anywhere. The only contract is the `data-story-body` attribute on the element wrapping your `<p>` tags.

```bash
# from project root
py .ai/skills/render/render.py                                    # auto-pick newest story; apply enrichment to existing index.html
py .ai/skills/render/render.py stories/05-pasajero-unico
py .ai/skills/render/render.py --bootstrap stories/06-foo         # write a minimal design scaffold to start from
py .ai/skills/render/render.py --bootstrap stories/05 --force     # overwrite an existing index.html with a scaffold (destructive!)
py .ai/skills/render/render.py --index-only                       # only refresh the project-wide index.html
```

Requires Python 3.11+ (`tomllib`). Reports sentences paired and any words missing from `[words.*]` so you can extend `enrich` and re-run.

### What the script writes (auto-managed; do not hand-edit)

- **Inside `[data-story-body]`** — every text node is tokenized:
  - Each Spanish word becomes `<span class="w" data-tr=… data-pos=… data-lemma=… data-grammar=…>word</span>`
  - Each sentence-terminator (`.?!`) becomes `<span class="s" data-tr=…>.</span>`
  - HTML inside `<p>` is preserved (you can use `<em>`, `<small>`, etc. — only text between tags is tokenized)
- **`<style data-popup-invariants>…</style>`** at the end of `<head>` — the behavior-critical bits popups break without (`pointer-events`, `.pop::after` hit-area bridge, default `.w` / `.s` cursor + dotted underline), plus the reading-progress hairline styling and the `prefers-reduced-motion` guard. Replaced (not appended to) on each run.
- **`<script data-popup>…</script>`** before `</body>` — the popup show/hide/position logic, the markdown-ish grammar parser (`mdToHtml`), and the reading-progress scroll listener (which appends a `<div class="reading-progress">` to body on load). Replaced on each run.

### Re-runnability

Each run **strips prior `.w` / `.s` spans first**, then re-tokenizes. Edit the Spanish text inside `<p>` tags freely between runs — the script picks up your edits. (Keep the body in sync with `story.md` so `enrich` re-runs aren't surprised.)

## Workflow

The workflow has a **design** phase (steps 1–6, produces an enrichment-free HTML) and an **apply** phase (step 7, runs `render.py`). The pipeline orchestrator (`/lee-story-pipeline`) runs `enrich` in parallel with the design phase, and only step 7 needs both upstream outputs — so do not call `render.py` before `enrichment.toml` exists. When invoked standalone (no orchestrator), just run the steps top to bottom.

1. Read `stories/NN-slug/story.md` (frontmatter + body). If `stories/NN-slug/enrichment.toml` already exists, skim its `[sentences]` / `[words.*]` for tone cues; otherwise carry on — apply-enrichment (step 7) is what actually needs it.
2. Read `profile.md` for tone calibration.
3. **Pick the found-document framing first.** Identify what in-universe artifact this story should *be* (see the Found-document framing section): the protagonist's log, a letter, a customs form, an observation sheet, a manuscript page, a system console dump, etc. Lock the artifact before any visual decisions.
4. **Pick the format archetype** from the named list (or invent a fresh one). Read the last 3 lines of `.ai/archetypes.jsonl` and do not reuse any of those archetypes (or their dominant palette / font pair). After deciding, append a one-line JSON entry `{"seq":"NN","slug":"slug","archetype":"…","palette":"…","font_pair":"…"}` to `.ai/archetypes.jsonl`.
5. **Invoke the `frontend-design` skill** to plan the visual approach *within the chosen archetype's idiom* — palette, font pairing, page chrome, marginalia, motion family. The skill's output should serve the artifact, not generic "story page" aesthetics.
6. **Design the page from scratch** at `stories/NN-slug/index.html`:
   - If starting clean, run `py .ai/skills/render/render.py --bootstrap stories/NN-slug` for a minimal scaffold (plain text in `<p>` tags inside `<article data-story-body>`).
   - Style anything: `body`, `main`, `h1`, `.meta`, `article p`, drop caps, special-paragraph art-direction, inline `<svg>` illustration, custom popup look (`.pop`, `.lemma`, `.pos`, `.tr`, `.g-block`, `.s-label`, `.s-tr`, `.link`).
   - Keep the `data-story-body` attribute on the element wrapping the `<p>` tags. The Spanish text inside should match `story.md` (the script tokenizes whatever's there).
7. **Apply enrichment**: `py .ai/skills/render/render.py stories/NN-slug` — wraps words, pairs sentences, injects popup behavior, refreshes project-wide index (incremental — the script maintains `.ai/stories-index.json` and only updates this story's entry). If it reports missed words, extend `enrichment.toml` and re-run.
8. Report to user:
   - Story HTML path
   - Index updated (entry count from the helper's output)
   - Any words flagged as missing from `[words.*]`
   - **Artifact framing** chosen (e.g. "Mariela's observation log") and **archetype** picked (e.g. "Observation log / lab notebook")
   - Thematic summary of the page in one short paragraph (palette, font pair, illustration motif, motion family)
   - Optional command to open in browser: `start "" "stories/NN-slug/index.html"` and `start "" "index.html"`

### Popup styling conventions

The `data-popup-invariants` block sets only behavior. To style the popup visually, target these classes in your own `<style>` (declared above the auto-managed block in source order — they win because of the cascade):

- `.pop` — the floating tooltip container (background, color, padding, border-radius, font, max-width)
- `.pop.has-grammar` — wider variant when a grammar block is present
- `.pop.sentence` — variant for sentence-terminator hover
- `.pop .lemma` — dictionary form line (italic by convention)
- `.pop .pos` — part-of-speech label (small caps + tracking by convention)
- `.pop .tr` — Russian translation
- `.pop .g-block` — grammar explanation block
- `.pop .g-block b` / `i` / `code` / `u` — markdown-ish markup tokens (Spanish form / grammar term / monospace inline / suffix highlight)
- `.pop .link` — SpanishDict link
- `.pop.sentence .s-label` / `.s-tr` — sentence popup parts

To re-color word/sentence underlines on hover, use higher specificity than `.w` / `.s` (e.g. `article .w:hover`) since the auto-managed block's defaults use `currentColor`.

## Quality bar

- The page should look like the specific in-universe artifact chosen for this story (a found log, letter, form, manuscript page, terminal dump — see "Found-document framing"), not a generic "language learning" template and not a generic "story page" template
- Two random samples from `stories/*/index.html` opened side-by-side should feel like *different documents from different worlds*, not "two variations on a centered-column page". If you can't tell them apart at a glance with text blurred out, the framing has failed
- Hover popups must work on first load with no console errors
- Mouse must travel from any word to its popup (and to the SpanishDict link) without the popup closing
- Grammar block (when present) renders with proper bold/italic/code/highlight styling consistent with the page's design language
- All popup text is Russian (lemma stays Spanish)
- Page must be a valid single HTML file: open it from disk, everything works (modulo the Google Fonts CDN which needs internet)

## Anti-checklist

- No reused design from a prior render in `stories/*/index.html`
- No reused format archetype within the prior 3 stories (see "Format archetypes — variety rule"); after the gap, a returning archetype must be a visibly fresh interpretation, never a re-skin
- No "generic story page" output — every render must commit to a specific in-universe artifact (see "Found-document framing"). If the design could be lifted onto any other story by swapping color and font, it has failed this rule
- No protagonist-profession-as-decorative-veneer (e.g. a few thematic SVGs glued onto an otherwise-generic centered serif column). The artifact framing must shape page chrome, metadata, layout, and motion — not just illustration
- No defaulting to a narrow horizontally centered single-column body. That layout is allowed only when the story explicitly benefits from minimalism (intimate monologue, brief confessional, museum-placard quiet); otherwise the page must use the editorial / cinematic / spatial toolkit in "Layout philosophy"
- No decorative pass that pulls the reader's eye before the prose does, and no body text below 18 px or contrast ratio 4.5:1, even inside framed panels, marginalia, or split panes
- No layout that breaks on narrow viewports — split-screen, multi-column, and floating regions must collapse to a clean single column on mobile with no horizontal scroll and no overlapping text
- No external JS libraries (no jQuery, no Tailwind CDN, no Bootstrap, no markdown library)
- No tracking scripts, no analytics, no Google Tag Manager
- No emoji used as primary illustration (Unicode dingbats sparingly OK as accents)
- No raster images or external image URLs (illustrations = inline SVG; CSS textures = data URIs or pure CSS)
- No raster GIFs anywhere (inline data URIs included) — motion must come from inline animated SVG (CSS keyframes or SMIL) or pure CSS animations
- No fast, loud, or attention-grabbing motion — ambient layers must be slow (multi-second cycles), low-opacity, and behind text; the body text itself never moves once loaded
- No JS-driven motion that ignores `prefers-reduced-motion` — gate it on `matchMedia` or use CSS `animation` / `transition` so the auto-injected guard applies
- No grammar lessons, keyword lists, or full-sentence translations visible on the page
- No English in popups — Russian only (lemma stays Spanish)
- No SpanishDict link on proper-noun popups
- No SpanishDict link, lemma line, POS line, or grammar block in sentence popups
- No generating translations inline at render time — they must come from the `.toml`
- No lorem ipsum / placeholders — every visible string is real story content or real metadata
