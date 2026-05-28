---
name: enrich
description: Step 2 of the lee-espanol pipeline. Read a Spanish story at stories/NN-slug/story.md and produce the enrichment data at stories/NN-slug/enrichment.toml (same folder, sibling file) — per-word Russian translation + POS + lemma + grammar explanation, and per-sentence Russian translation. The renderer consumes this file to generate the popup popups. Use when the user asks to enrich a story or invokes /enrich.
---

# enrich

Step **2** of the 3-step lee-espanol pipeline. Reads a pure-Spanish `.md` story and writes a sibling `.toml` file with everything the renderer needs to build popups.

## Inputs

- **Source story**: `stories/NN-slug/story.md` (frontmatter + Spanish body)
- **Reader profile**: `profile.md` (for A1 vocabulary calibration)

If the user does not specify which story, scan all `stories/NN-slug/` subfolders, find those containing `story.md` but **no `enrichment.toml`** yet, and pick the most recent one; confirm with the user before generating.

## Output

A single TOML file: `stories/NN-slug/enrichment.toml` — co-located with `story.md` in the same `stories/NN-slug/` folder.

UTF-8, no BOM. Always overwrite cleanly — do not append.

## File format

Top-level sections: `[words.*]` (one entry per single-word surface form), `[[phrases]]` (multi-word expressions & idioms, optional), and `[[sentences]]` (one array entry per sentence-terminator in story order).

### `[words.<form>]` — vocabulary lookup

Keyed by **lowercased surface form** (the word as it appears in the text). The renderer matches case-insensitively, so `[words.elena]` covers `Elena` at the start of a sentence.

**TOML key quoting — mandatory for non-ASCII forms.** TOML bare keys allow only `A-Z a-z 0-9 _ -`. Any Spanish surface form containing `á é í ó ú ñ ü` (or any other non-ASCII character) **must** be wrapped in double quotes in the table header, or `tomllib` will refuse to parse the file with `Expected ']' at the end of a table declaration`.

```toml
# ✗ wrong — will fail at parse time
[words.señal]
[words.plutón]
[words.según]

# ✓ correct — quoted keys
[words."señal"]
[words."plutón"]
[words."según"]
```

ASCII-only forms (`mariela`, `radio`, `viven`) take the bare form. The quoted vs. unquoted forms are equivalent to the parser — the key value is the same string either way — so the renderer's lookup (`words.get(w.lower())`) works for both. The quoting is purely a TOML-syntax requirement.

Quick mental check while writing entries: every accented vowel, every `ñ`, every `ü` in a `[words.X]` header means quotes go around `X`.

Required fields:

```toml
[words.observa]
tr = "(она) наблюдает"        # concise Russian gloss (1–5 words; full def goes to SpanishDict)
pos = "глаг."                 # Russian POS abbreviation
lemma = "observar"            # dictionary form (for nouns include the article: "la tripulación")

# optional — present for any word where grammar adds value
grammar = """
**observa** — *presente indicativo*, 3 л. ед. ч.

Правильный глагол на `-ar`: окончание для 3 л. ед. — [[-a]].

`observ·[[ar]]` → `observ·[[a]]`
"""
```

POS abbreviations (Russian):

| Code | Meaning |
|------|---------|
| `сущ.` | noun |
| `глаг.` | verb |
| `прил.` | adjective |
| `нар.` | adverb |
| `мест.` | pronoun |
| `арт.` | article |
| `опр.` | determiner |
| `предл.` | preposition |
| `союз` | conjunction |
| `числ.` | numeral |
| `имя` | proper noun |

### Proper nouns / names / fictional acronyms

Wrap them like ordinary entries but **omit `lemma`** and use `pos = "имя"`. The renderer detects missing lemma and suppresses the SpanishDict link. The popup `tr` becomes the explanation.

```toml
[words.ares]
tr = "ARES — имя бортового ИИ"
pos = "имя"
# no lemma — no SpanishDict link in the popup
```

### `grammar` field — markup spec

Optional. Add it to any word where the grammar is non-obvious for an A1 reader. The renderer's JS parses a minimal markdown-ish syntax at popup-show time and turns it into HTML inside the popup's grammar block.

**Recognised markers**:

| Markup | Renders as | Use for |
|--------|------------|---------|
| `**text**` | `<b>` — Spanish forms, highlighted | the conjugated form, infinitive, alternative forms |
| `*text*` | `<i>` — small-caps grammar term | *presente*, *pretérito*, *futuro próximo*, *infinitivo* |
| `` `text` `` | `<code>` — monospace inline | verb form breakdowns: `observ·ar`, `t·iene` |
| `[[text]]` | `<u>` — colored "highlight" | suffix, stem change, irregular morpheme — works **inside** `` `code` `` too |
| blank line | new `<p>` paragraph | structure the explanation |

**Order of operations** (the renderer must respect this — see render skill): process `[[...]]` inside `` `...` `` first, then the rest.

**Patterns to use consistently**:

```text
# Regular -ar verb, 3p sg presente
**mira** — *presente*, 3 л. ед. ч.

`mir·[[ar]]` → `mir·[[a]]`

# Stem-changing verb (o → ue, e → ie)
**recuerda** — *presente*, 3 л. ед. ч., от **recordar**.

*Чередование в корне:* `rec[[o]]rdar → rec[[ue]]rda` (o → ue под ударением).

# Irregular pretérito (venir → vino)
**vino** — *pretérito indefinido*, 3 л. ед. ч., от **venir**.

*Неправильный.* Корень меняется на [[vin-]]. Спряж.: `vine · viniste · vino · vinimos · vinisteis · vinieron`.

# Periphrastic future (futuro próximo)
**va a volver** — *futuro próximo* ("собирается вернуться").

Структура: `ir` (в наст. вр.) + `a` + инфинитив. Здесь `va` (3 л. ед. ч. от **ir**) + `a` + `volver`.

# Reflexive
**se apagó** — *pretérito* от **apagarse** ("погаснуть"), 3 л. ед. ч.

*Возвратный.* Частица **se** показывает, что субъект сам "гасит себя".

# Noun with non-obvious gender
**el día** — сущ. *м. р.*, ед. ч.

*Исключение:* оканчивается на `-a`, но мужского рода (как **el problema**, **el planeta**).

# Idiomatic construction
**hace** + время — идиома "… назад".

*Дословно:* "делает шесть месяцев" = "шесть месяцев назад".
```

**Coverage policy**: do not add `grammar` to articles, basic prepositions, common pronouns (*yo, tú, él, ella*), or basic conjunctions — clutter without value. Do add it to:

- All conjugated verbs (every form, even repeated ones)
- Periphrastic future every time it appears (`va a + inf`, `van a + inf`)
- Contractions (`del`, `al`) — short explanation
- Reflexive constructions
- Stem-changing or irregular forms
- Nouns with non-obvious gender (`el día`, `el problema`, `el planeta`, `la radio`, `la mano`, `la gente`)
- Idioms (`hace + time`, `dejar de + inf`)
- Anything else where a learner would benefit

### `[[phrases]]` — multi-word expressions & idioms

Ordered array. Each entry is a run of text spanning **more than one word** that should be treated as a single popup target instead of being tokenized word-by-word. The renderer matches phrases greedily (longest first) and case-insensitively against the body, so list the full surface form in `form`.

Use it for two kinds of run:

**1. Fixed multi-word lexemes** — set phrases that translate as a unit (`por favor`, `por fin`, `tal vez`, `otra vez`), and multi-word proper nouns (`Colonia Verde`). These take the same fields as a `[words.*]` entry:

```toml
[[phrases]]
form = "por fin"
tr = "наконец"
pos = "нар."

[[phrases]]
form = "Colonia Verde"
tr = "«Зелёная Колония» — название колонии"
pos = "имя"            # no lemma → no SpanishDict link
```

**2. Idioms** — expressions whose meaning isn't the sum of their words. Show **both** the whole-idiom meaning **and** a per-word breakdown in one popup by adding `parts` (and usually `literal`):

```toml
[[phrases]]
form = "tomar el pelo"
tr = "разыгрывать, подшучивать (над кем-то)"   # whole-idiom meaning
pos = "идиома"                                   # use the literal POS "идиома" for idioms
lemma = "tomar el pelo"                          # keeps the SpanishDict link
literal = "брать за волосы"                       # word-for-word reading (optional but recommended)
parts = [
  { w = "tomar", tr = "брать" },
  { w = "el",    tr = "(артикль м. р.)" },
  { w = "pelo",  tr = "волосы" },
]
grammar = """
**tomar el pelo** — устойчивое выражение.

Спрягается обычный глагол **tomar**: `te toma el pelo` («он тебя разыгрывает»).
"""
```

- `tr` — the **idiom's overall meaning** (this is the headline translation).
- `pos = "идиома"` — flags it as an idiom (the renderer also auto-detects via `parts`/`literal`).
- `parts` — an array of `{ w, tr }`, one per component word, in order. The renderer renders these as a small `form → Russian` list under the headline translation. Keep glosses short; this is the literal value of each word, not its contextual sense.
- `literal` (optional, recommended when it differs usefully) — the word-for-word reading of the whole expression.
- `grammar` (optional) — extra context: how it inflects, register, typical usage. Same markdown-ish markup as the word `grammar` field.
- `lemma` (optional) — include the idiom form to keep the SpanishDict link; omit for non-dictionary set phrases.

**When to make something an idiom (with `parts`) vs. a plain phrase:** if a learner who knew every individual word would still misread the meaning, it's an idiom — give it `parts` + `literal` so the popup shows both layers. If the phrase is just a fixed collocation that means roughly what its words say (`por favor`), a plain `tr` is enough.

A still-stronger alternative for one-off idioms that are *not* a contiguous fixed string: leave the words tokenized individually and put the idiom explanation in the terminating sentence's `note` (see `[[sentences]]`). Prefer `[[phrases]]` + `parts` when the idiom is a clean contiguous run.

### `[[sentences]]` — sentence translations

Ordered array. The renderer pairs each sentence-terminator (`.`, `?`, `!`) in the story body with the next entry from this array, in document order.

```toml
[[sentences]]
text = "Elena escribe en su cuaderno: \"Día 78.\""
tr = "Elena пишет в своей тетради: «День 78»."

[[sentences]]
text = "La plaza está llena de gente."
tr = "Площадь полна людей."

[[sentences]]
text = "Si el faro se apaga, la colonia muere."
tr = "Если маяк погаснет, колония погибнет."
note = """
*Условное предложение (1-й тип):* `si` + *presente* в придаточном, *presente/futuro* в главном — реальное условие.

Порядок гибкий: придаточное с `si` может стоять в начале или в конце.
"""
```

- `text` is the **full Spanish sentence** as it appears in the story. Not used by the renderer at runtime — it is for human sanity-checking and lets the user spot drift if the .md is edited but the .toml is not.
- `tr` is the **Russian translation** of that sentence.
- `note` (**optional**) — a sentence-level explanation shown in the dot popup *beneath* the translation, written in the **same markdown-ish markup** as the word `grammar` field (`**form**`, `*term*`, `` `code` ``, `[[suffix]]`, blank line = new paragraph). Use it for things a per-word grammar block can't capture: word order, why two tenses sit together, the shape of a *si*-clause, the meaning of the whole clause as a turn of phrase, or brief cultural context. Add it only where it genuinely helps an A1 reader — most sentences need no note. Keep it short. This same `note` is also what surfaces when the reader holds **Shift** and hovers any word in the sentence (Shift-to-sentence), so it should read as useful context for the whole sentence.
- **One entry per sentence-terminator**, in story order. A period inside quotes (`"Día 78."`) counts as one terminator and gets its own entry if it is the only one on the line; otherwise it gets the inner-sentence translation and the outer sentence gets a separate entry on its own terminator.
- If a paragraph contains multiple short sentences (`Saturno gira. Los anillos brillan. El comandante duerme.`), each gets its own entry.

## Workflow

1. **Read the story `.md`** — parse frontmatter and Spanish body.
2. **Read the profile** — calibrate the vocabulary level (don't over-explain at A1).
3. **Tokenize the body**:
   - Identify each word (skip digits, punctuation, whitespace)
   - Identify sentence-terminators in order (`.`, `?`, `!`), including those inside quotes
4. **Build the words table**:
   - For each unique lowercased form, emit `[words.<form>]` with `tr`, `pos`, `lemma`, and `grammar` (where useful)
   - Disambiguate by sense across the whole story if the same form means different things (rare at A1; if it happens, pick the dominant sense and note the alternative in `grammar`)
   - Proper nouns get `pos = "имя"` and no `lemma`
5. **Build the phrases array** (`[[phrases]]`):
   - Scan for multi-word expressions: fixed collocations (`por fin`, `tal vez`), multi-word proper nouns (`Colonia Verde`), and **idioms**
   - For idioms, add `pos = "идиома"`, a whole-meaning `tr`, a per-word `parts` breakdown, and (where useful) a `literal` reading + `grammar` context — so the popup shows both the idiom and its words
   - List longer phrases first conceptually; the renderer matches longest-first regardless
6. **Build the sentences array**:
   - One `[[sentences]]` entry per terminator, in story order
   - `text` is the full Spanish sentence, `tr` is the Russian translation
   - Add an optional `note` where a sentence-level explanation helps (word order, *si*-clauses, tense interplay, an idiomatic whole clause, cultural context) — this also powers Shift-to-sentence on every word in the sentence
7. **Write the file** to `stories/NN-slug/enrichment.toml` (overwrite if exists)
8. **Report to user**:
   - Path
   - Word count and sentence count enriched
   - Any forms you flagged as ambiguous or where grammar was particularly tricky
   - Suggest next step: `/render` to build the HTML page

## Quality bar

- Every meaningful word in the story has an entry. The renderer should never hit "unknown form".
- Russian translations are concise glosses, not full dictionary entries (1–5 words; SpanishDict link in the popup carries the heavier lookup).
- Grammar explanations are A1-appropriate: short, focused on the specific form in question, no detours into adjacent grammar topics.
- Sentence translations match the sentence count exactly. Off-by-one breaks the renderer's pairing.

## Anti-checklist

- No HTML in the TOML — the renderer turns the markdown-ish markup into HTML at popup-show time
- No English. Russian only for translations and grammar explanations
- No academic-essay grammar. Stay focused on the form in the popup
- No SpanishDict links inline — the renderer adds those
- No skipped words. If a word is in the body, it should be in `[words.*]` (proper nouns included)
