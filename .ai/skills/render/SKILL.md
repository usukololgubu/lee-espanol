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
- **Layout / composition**: vary across stories. Some single-column centered, some asymmetric, some with side margins of metadata, some with a faux interface (e.g. AI log entries inside a bordered "console" frame).
- **Reading width**: ~640–720px max for body text; never less than 18px font-size; line-height 1.7–1.9 for A1 readers.

Distinctive ≠ chaotic. Each page should feel like a curated print artifact, not a random theme dump. If two consecutive renders feel similar, push harder on differentiation.

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

### Index page (project-wide table of contents)

A single project-wide index lives at `index.html` (project root). It lists every story as a clickable row.

**Aesthetic**: compact "printed-document" / typewriter — explicitly **distinct** from any individual story's design (no parchment, no manuscript ornament, no sci-fi gold-on-navy, no SVG illustrations). The index is a quiet, tight TOC that frames the stories without competing visually.

- Background: warm off-white / paper (`#f5f3ec`)
- Text: typewriter-ink dark (`#1f1d18`) + greys; **no color accent** beyond grayscale
- Font: a single typewriter monospace family — *Courier Prime* (regular + bold + italic)
- Layout: compact single column ~720 px, double-rule masthead at top, brief intro paragraph, TOC heading row with entry count, two-line entries (row 1: number, title in tracked uppercase, leader dots, date; row 2: italic meta + word count), thin colophon at bottom
- No ornaments, no SVG illustrations, no big display numerals, no hero block, no stats strip with huge digits — only typography, dotted leaders, and hairline rules

**Refresh policy**: rebuild the index every time a story is rendered. Enumerate every `stories/NN-slug/` subfolder, read its `story.md` frontmatter, sort by folder name, and regenerate the `<div class="entries">…</div>` block plus the entry-count value in `.toc-head .stat` (e.g. `02 entradas` → `03 entradas`). Each entry's `href` points to `stories/NN-slug/index.html`. Preserve everything else in the file (masthead, intro paragraph, TOC heading label, colophon, CSS). Only the entries list and the entry-count number change.

If `index.html` is missing entirely, create it from scratch following the compact typewriter aesthetic above. Do **not** invent a third aesthetic; the typewriter index template established for this project should remain stable across renders.

Per-entry markup template (the `href` is relative to the project-root `index.html`):

```html
<a class="entry" href="stories/NN-slug/index.html">
  <div class="row1">
    <span class="num">{NN, two-digit}</span>
    <span class="e-title">{Spanish title}</span>
    <span class="leader"></span>
    <span class="date">{YY·MM·DD}</span>
  </div>
  <div class="row2">
    <span class="meta">{protagonist} · {setting}</span>
    <span class="words">{length_words} palabras</span>
  </div>
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
- **`<style data-popup-invariants>…</style>`** at the end of `<head>` — the behavior-critical bits popups break without (`pointer-events`, `.pop::after` hit-area bridge, default `.w` / `.s` cursor + dotted underline). Replaced (not appended to) on each run.
- **`<script data-popup>…</script>`** before `</body>` — the popup show/hide/position logic and the markdown-ish grammar parser (`mdToHtml`). Replaced on each run.

### Re-runnability

Each run **strips prior `.w` / `.s` spans first**, then re-tokenizes. Edit the Spanish text inside `<p>` tags freely between runs — the script picks up your edits. (Keep the body in sync with `story.md` so `enrich` re-runs aren't surprised.)

## Workflow

1. Read `stories/NN-slug/story.md` and `stories/NN-slug/enrichment.toml` (for word coverage, tone cues)
2. Read `profile.md` for tone calibration
3. **Invoke the `frontend-design` skill** to plan the visual approach for this story's tone/setting. Record the chosen palette, font pairing, illustration concept, and layout intuition.
4. **Design the page from scratch** at `stories/NN-slug/index.html`:
   - If starting clean, run `py .ai/skills/render/render.py --bootstrap stories/NN-slug` for a minimal scaffold (plain text in `<p>` tags inside `<article data-story-body>`).
   - Style anything: `body`, `main`, `h1`, `.meta`, `article p`, drop caps, special-paragraph art-direction, inline `<svg>` illustration, custom popup look (`.pop`, `.lemma`, `.pos`, `.tr`, `.g-block`, `.s-label`, `.s-tr`, `.link`).
   - Keep the `data-story-body` attribute on the element wrapping the `<p>` tags. The Spanish text inside should match `story.md` (the script tokenizes whatever's there).
5. **Apply enrichment**: `py .ai/skills/render/render.py stories/NN-slug` — wraps words, pairs sentences, injects popup behavior, refreshes project-wide index. If it reports missed words, extend `enrichment.toml` and re-run.
6. Report to user:
   - Story HTML path
   - Index updated (entry count from the helper's output)
   - Any words flagged as missing from `[words.*]`
   - Thematic summary of the page in one short paragraph (palette, font pair, illustration motif)
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

- The page should look like the cover/interior of a book imagined for this exact story, not a generic "language learning" template
- Hover popups must work on first load with no console errors
- Mouse must travel from any word to its popup (and to the SpanishDict link) without the popup closing
- Grammar block (when present) renders with proper bold/italic/code/highlight styling consistent with the page's design language
- All popup text is Russian (lemma stays Spanish)
- Page must be a valid single HTML file: open it from disk, everything works (modulo the Google Fonts CDN which needs internet)

## Anti-checklist

- No reused design from a prior render in `stories/*/index.html`
- No external JS libraries (no jQuery, no Tailwind CDN, no Bootstrap, no markdown library)
- No tracking scripts, no analytics, no Google Tag Manager
- No emoji used as primary illustration (Unicode dingbats sparingly OK as accents)
- No raster images or external image URLs (illustrations = inline SVG; CSS textures = data URIs or pure CSS)
- No grammar lessons, keyword lists, or full-sentence translations visible on the page
- No English in popups — Russian only (lemma stays Spanish)
- No SpanishDict link on proper-noun popups
- No SpanishDict link, lemma line, POS line, or grammar block in sentence popups
- No generating translations inline at render time — they must come from the `.toml`
- No lorem ipsum / placeholders — every visible string is real story content or real metadata
