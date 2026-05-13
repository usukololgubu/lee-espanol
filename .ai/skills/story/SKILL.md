---
name: story
description: Step 1 of the lee-espanol pipeline. Generate the next pure-Spanish A1 short story for the "Space Expansion" universe. Reads profile.md and lore.md, writes pure Spanish (no inline translations, no keywords, no grammar sidebars) to stories/NN-slug/story.md. The downstream skills `enrich` and `render` consume this file. Use when the user asks for a new story or invokes /story.
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
- **Lore reference** (load every run): `lore.md` — compact continuity record (characters, locations, ships, terms, timeline, per-story deltas)
- **Story output**: `stories/NN-slug/story.md` (create the folder if absent)

## Workflow

1. **Read `profile.md`** — load reader spec (level, vocab control, tone, anti-vibe, format).
2. **Read `lore.md`** — load established universe state. Only open a specific prior `stories/<NN-slug>/story.md` if the new concept directly extends one of its threads; do **not** skim all prior stories.
3. **List `stories/`** — find existing `NN-slug/` subfolders (those starting with two digits and a hyphen). Determine the next sequential `NN`.
4. **Pick the concept**:
   - If the user named a specific concept, use it.
   - Otherwise, propose a next concept consistent with `lore.md` and tone, and confirm before writing.
5. **Write the Spanish text** to spec:
   - 150–300 words (target ~270)
   - A1 grammar: present indicative, `ir + a + infinitivo`, basic *pretérito perfecto* / *indefinido*. Avoid *subjuntivo*.
   - ~80% top-1500 frequency vocab, ~20% new/thematic words
   - Neutral Latin American Spanish — no *vosotros*, no strong regionalisms
   - Self-contained: closed mini-story, **no cliffhangers**
   - Tone follows profile (Strugatsky × Matt Haig — observer in alien-to-them setting, single unresolved moral dilemma, slow contemplative pace, occasional dry irony)
6. **Save the file** as `stories/NN-slug/story.md` (create the `stories/NN-slug/` folder first if it does not exist) with this structure:
   ```
   ---
   seq: <number>
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
7. **Update `lore.md`** — append a per-story delta block at the bottom of `lore.md`:
   ```markdown
   ### #NN — <slug>
   - Characters: <new names introduced by this story, with role>
   - Locations: <new places>
   - Ships: <new ships>
   - Terms: <new terms / tech / cult words>
   - Timeline: <new anchors, e.g. "Año 198 / 800 Caracol">
   ```
   Include only categories with new entries; omit empty ones. Do **not** restate elements already in earlier deltas or top-level lists. The top-level lists are touched up by hand from these deltas — leave them alone in the automated step.
8. **Report to user**: file path + a one-line hook (e.g. "AI logs first sensor failure on day 412 — wakes the commander or stays silent?"). Do not paste the full story into chat. Mention that the `lore.md` delta has been appended.
9. **Suggest next step**: remind the user that `enrich` is the next step before rendering, e.g. "Next: run /enrich to generate translation data, then /render for the HTML page."

## Structural variety — give the renderer compositional material

A continuous wall of prose pushes the downstream `render` skill toward a single centered column, because there is nothing else for it to lay out. Where the story's content naturally allows it, **break the body into structurally separable content blocks** so the renderer can distribute them across the page as side panels, pull quotes, split-screen segments, framed inserts, or marginalia.

This is **optional, not mandatory**. A tightly braided contemplative monologue or a single confessional letter should stay continuous — segmentation imposed on the wrong story damages it. But when the structure permits, prefer outputs with naturally segmentable sections. Examples (mix freely; the right two or three per story, not all of them):

- **Transmission logs** — timestamped signal entries, frequency or channel headers, sender/receiver fields, short bursts of dispatcher voice
- **Journal fragments** — dated diary or notebook entries, each self-contained, written in the protagonist's first-person register
- **Dialogue snippets** — short exchanges set apart from the surrounding narration (e.g. an interrogation, a radio call, an overheard scrap)
- **System messages** — terminal output, error codes, machine prompts, automated status lines in a flat machine voice
- **Flashback inserts** — short past-tense passages set off from the present-tense frame, marking a memory or earlier scene
- **Parallel scene fragments** — two or more scenes alternating in short blocks (e.g. ship + station, observer + observed, surface + orbit)
- **Observational side notes** — brief asides from the protagonist that read as marginalia or footnote-style commentary on the main action
- **Location/time jump separators** — labeled breaks between scenes (e.g. *— Día 412, 03:00, sala de control —*) that signal the renderer to start a fresh visual section

### How to mark segmentation in the .md

Use conventional Markdown structure so the renderer can pick up the cues without bespoke parsing:

- `>` blockquote for transmissions, log entries, system messages, and quoted snippets
- A short level-2 heading (`## …`) or a labeled separator line (e.g. `*— Día 412, 03:00 —*`) for scene / location / time jumps
- `***` or `---` horizontal rule for major structural breaks between modular sections
- Plain paragraphs for the continuous narrative spine

Still pure Spanish. Still A1 grammar and vocab control. Still no inline glossary, no Russian, no English, no learner sidebars — **segmentation is a structural choice, not a learner-aid leak**. Translations for every word and every sentence terminator are produced later by `enrich`; the `.md` stays prose-only.

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
- Lore consistency across stories matters: reuse names of factions, ships, places, technologies listed in `lore.md`. Any new element introduced must be recorded in the per-story delta appended to `lore.md` (workflow step 7).
