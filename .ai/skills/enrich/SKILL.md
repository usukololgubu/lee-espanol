---
name: enrich
description: Step 2 of the lee-espanol pipeline. Read a Spanish story at D:\localai\lee-espanol\stories\NN-slug\story.md and produce the enrichment data at D:\localai\lee-espanol\stories\NN-slug\enrichment.toml (same folder, sibling file) — per-word Russian translation + POS + lemma + grammar explanation, and per-sentence Russian translation. The renderer consumes this file to generate the popup popups. Use when the user asks to enrich a story or invokes /enrich.
---

# enrich

Step **2** of the 3-step lee-espanol pipeline. Reads a pure-Spanish `.md` story and writes a sibling `.toml` file with everything the renderer needs to build popups.

## Inputs

- **Source story**: `D:\localai\lee-espanol\stories\NN-slug\story.md` (frontmatter + Spanish body)
- **Reader profile**: `D:\localai\lee-espanol\profile.md` (for A1 vocabulary calibration)

If the user does not specify which story, scan all `stories/NN-slug/` subfolders, find those containing `story.md` but **no `enrichment.toml`** yet, and pick the most recent one; confirm with the user before generating.

## Output

A single TOML file: `D:\localai\lee-espanol\stories\NN-slug\enrichment.toml` — co-located with `story.md` in the same `stories/NN-slug/` folder.

UTF-8, no BOM. Always overwrite cleanly — do not append.

## File format

Two top-level sections: `[words.*]` (one entry per surface form) and `[[sentences]]` (one array entry per sentence-terminator in story order).

### `[words.<form>]` — vocabulary lookup

Keyed by **lowercased surface form** (the word as it appears in the text). The renderer matches case-insensitively, so `[words.elena]` covers `Elena` at the start of a sentence.

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

### `[[sentences]]` — sentence translations

Ordered array. The renderer pairs each sentence-terminator (`.`, `?`, `!`) in the story body with the next entry from this array, in document order.

```toml
[[sentences]]
text = "Elena escribe en su cuaderno: \"Día 78.\""
tr = "Elena пишет в своей тетради: «День 78»."

[[sentences]]
text = "La plaza está llena de gente."
tr = "Площадь полна людей."
```

- `text` is the **full Spanish sentence** as it appears in the story. Not used by the renderer at runtime — it is for human sanity-checking and lets the user spot drift if the .md is edited but the .toml is not.
- `tr` is the **Russian translation** of that sentence.
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
5. **Build the sentences array**:
   - One `[[sentences]]` entry per terminator, in story order
   - `text` is the full Spanish sentence, `tr` is the Russian translation
6. **Write the file** to `D:\localai\lee-espanol\stories\NN-slug\enrichment.toml` (overwrite if exists)
7. **Report to user**:
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
