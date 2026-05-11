---
name: story
description: Step 1 of the lee-espanol pipeline. Generate the next pure-Spanish A1 short story for the "Space Expansion" universe. Reads profile.md and prior stories, writes pure Spanish (no inline translations, no keywords, no grammar sidebars) to stories/NN-slug/story.md. The downstream skills `enrich` and `render` consume this file. Use when the user asks for a new story, the next pilot, or invokes /story.
---

# story

Step **1** of the 3-step lee-espanol pipeline:

1. **story** (this skill) — write Spanish text to `stories/NN-slug/story.md`
2. **enrich** — produce `stories/NN-slug/enrichment.toml` with translations, POS, lemma, grammar, sentence translations
3. **render** — produce `stories/NN-slug/index.html` from the .md + .toml pair

All three files live **together in a single `stories/NN-slug/` folder**. Each story is a self-contained folder under `stories/`.

This skill is concerned **only** with step 1. It outputs pure Spanish. No translations, no glossary, no grammar notes — those live in step 2.

## Project paths (relative to project root)

- **Profile** (load first, every run): `profile.md`
- **Story output**: `stories/NN-slug/story.md` (create the folder if absent)
- **Prior stories** (for lore continuity): `stories/<NN-slug>/story.md` — one per story folder under `stories/`

## Workflow

1. **Read `profile.md`** — load reader spec (level, vocab control, tone, anti-vibe, format).
2. **List `stories/`** — find existing `NN-slug/` subfolders (those starting with two digits and a hyphen). Determine the next sequential `NN`. Skim each `stories/<NN-slug>/story.md` for lore continuity (recurring universe terms, factions, places, dates).
3. **Pick the concept**:
   - If the user named a specific pilot or concept, use it.
   - Otherwise, propose a next concept consistent with established lore and tone, and confirm before writing.
4. **Write the Spanish text** to spec:
   - 150–300 words (target ~270 for pilots)
   - A1 grammar: present indicative, `ir + a + infinitivo`, basic *pretérito perfecto* / *indefinido*. Avoid *subjuntivo*.
   - ~80% top-1500 frequency vocab, ~20% new/thematic words
   - Neutral Latin American Spanish — no *vosotros*, no strong regionalisms
   - Self-contained: closed mini-story, **no cliffhangers**
   - Tone follows profile (Strugatsky × Matt Haig — observer in alien-to-them setting, single unresolved moral dilemma, slow contemplative pace, occasional dry irony)
5. **Save the file** as `stories/NN-slug/story.md` (create the `stories/NN-slug/` folder first if it does not exist) with this structure:
   ```
   ---
   pilot: <number or null>
   title: "<Spanish title>"
   universe: Space Expansion
   protagonist: <role + name>
   setting: <where>
   length_words: <count>
   level: A1
   tone: <e.g. "contemplative, mild irony">
   ending: <open | twist | closed>
   date_generated: <YYYY-MM-DD>
   ---

   # <Spanish title>

   <story body>
   ```
6. **Report to user**: file path + a one-line hook (e.g. "AI logs first sensor failure on day 412 — wakes the commander or stays silent?"). Do not paste the full story into chat.
7. **Suggest next step**: remind the user that `enrich` is the next step before rendering, e.g. "Next: run /enrich to generate translation data, then /render for the HTML page."

## Anti-checklist (forbidden in the .md output)

- Inline keyword tables, vocabulary lists, glossaries
- English or Russian translations side-by-side with Spanish
- Grammar notes / "learner" sidebars
- Heavy-handed moralizing or explicit "lessons"
- Romance subplots
- Childish / naive register
- Cliffhangers (each story closes itself; the universe accumulates lore, not unresolved plot threads)
- HTML, popup spans, or anything that belongs in `enrich`/`render`

## Quality bar

- The story should work as fiction first, learning material second. If a fluent reader would find it inert, it fails.
- Strugatsky × Matt Haig is the reference: outsider observing humans / civilization, moral dilemma without a clean answer, occasional dry irony.
- Lore consistency across stories matters: reuse names of factions, ships, places, technologies established in earlier files in `stories/`.
