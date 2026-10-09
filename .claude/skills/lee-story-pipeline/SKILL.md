---
name: lee-story-pipeline
description: Make a new lee-espanol story end to end (concept, story, enrichment, page design, preview, publish), with parallel subagents. Use when the user asks for a new story ("новый рассказ", "next story", /lee-story-pipeline) or a scheduled run fires.
---

# lee-story-pipeline

The one entry point for adding a story. You (the main session) are the orchestrator
and the author: you pick the concept and write the Spanish text yourself, then hand
the two heavy, independent jobs to parallel subagents and do the bookkeeping while
they run.

`.ai/skills/{story,enrich,render}/SKILL.md` are **reference docs** for formats and
rules. Subagents read the one they need; you don't need to read them in full.

Talk to the user in Russian, short and plain. Repo text (commits, docs) stays English.

## Shape of the run

```
main ── concept ── story.md ──┬── [design agent: opus]  index.html (design only) ──┐
                              ├── [enrich agent: sonnet] enrichment.toml ──────────┼── apply + checks ── preview ── publish
                              └── main: lore.md + archetype bookkeeping ───────────┘
```

| Step | Who | Model / effort | Why |
|------|-----|----------------|-----|
| Concept + story text | main | session model, high | Taste and Spanish quality decide whether the story works at all. Short output, so high effort is cheap here. |
| Page design | subagent | `opus`, effort `medium` | The longest job (~1000+ lines of HTML/CSS/SVG) and the visible half of the project. Needs a strong model; medium effort keeps it fast. |
| Enrichment | subagent | `sonnet`, effort `medium` | `--prefill` already copies ~80% from earlier stories. What's left (new words, sentence translations, grammar notes) is careful but routine. |
| Lore delta, ref lists | main, while agents run | (n/a) | You already know which entities you used. Costs nothing extra. |
| Apply, lint, tests, screenshots | main | (n/a) | Mechanical scripts. |
| Fix-ups after lint | main | (n/a) | Usually a few lines; not worth a new agent. |

Design is the critical path. Start it first, in the same message as the enrich agent.

## Modes

- **Interactive** (default): the user picks the concept and OKs the preview.
- **Unattended** (scheduled run, or the user said "сам выбери" / "без вопросов"): you
  pick the concept yourself. Still stop at the preview: **never publish without the
  user's OK.**

## Python

Docs say `py` (Windows). On Linux/macOS use `python3`. Below, `PY` = whichever exists.

## Steps

### 0. Sync

```bash
git fetch origin main && git checkout main && git pull --ff-only origin main
```

### 1. Concept (main)

Read only: `profile.md`, the top-level lists of `lore.md` plus its last 3 per-story
deltas, titles + loglines in `.ai/stories-index.json`, and the last 3 lines of
`.ai/archetypes.jsonl`. Don't read old story bodies unless a concept directly extends
one (then read just that one).

Write **3 concepts**, one line each in Russian: protagonist, setting, dilemma, lore it
reuses (if any). Vary protagonist type and sub-vibe (see `profile.md`); at least one
in a brand-new setting.

- Interactive: send them as a numbered list with your pick marked; wait. If the user
  offers their own idea, use it.
- Unattended: take your pick; one line on why.

### 2. Story (main, high effort)

Next `NN` = highest existing `stories/NN-*` + 1. Write `stories/NN-slug/story.md`
following `.ai/skills/story/SKILL.md` (frontmatter fields, 150–300 words, A1 grammar,
no subjunctive, structural segmentation where it fits, no cliffhanger).

Before handing off, reread the text once as an A1 reader: anything above A1 grammar,
any word that needs more than a short gloss, any sentence over ~20 words? Fix now:
every later step depends on this text, and changing it after enrichment means redoing
work.

### 3. Fan out (two subagents in one message, then bookkeeping)

Launch both in the **same** message, with `run_in_background: true`, so they run in
parallel. Give each the full story path and tell it not to touch any file but its own.

**Design agent** (`model: "opus"`, `effort: "medium"`):

> Design the page for `stories/NN-slug/` in the lee-espanol repo. Read
> `.ai/skills/render/SKILL.md` (sections: Design contract, Layout philosophy,
> Found-document framing, Format archetypes, Popup styling conventions, Quality bar,
> Anti-checklist) and `stories/NN-slug/story.md`. Avoid the archetypes, palettes and
> font pairs in the last 3 lines of `.ai/archetypes.jsonl`. Start from
> `PY .ai/skills/render/render.py --bootstrap stories/NN-slug` and write
> `stories/NN-slug/index.html` with the story text inside `[data-story-body]`. Do NOT
> run render.py without `--bootstrap` (enrichment isn't ready), and edit no other file.
> Use the `frontend-design` skill if it's available. Reply with: the artifact framing,
> the archetype, palette, font pair, and the bg/ink/accent hex colors.

**Enrich agent** (`model: "sonnet"`, `effort: "medium"`):

> Write `stories/NN-slug/enrichment.toml` in the lee-espanol repo. Read
> `.ai/skills/enrich/SKILL.md` and follow its Workflow: start with
> `PY .ai/skills/render/render.py --prefill stories/NN-slug`, fill every stub, check
> prefilled glosses against this story's context, add new phrases/idioms, translate
> every sentence, and finish when `PY .ai/skills/render/render.py --lint stories/NN-slug`
> reports no errors. Edit no other file. Reply with: counts (prefilled / new words /
> sentences) and any word whose grammar is above A1 (subjunctive, rare tenses).

**While they run (main):**

- Append the per-story delta to `lore.md` and the `[#NN](stories/NN-slug/story.md)`
  refs to the top-level lists (rules in `.ai/skills/story/SKILL.md` step 7).
- Draft the commit message (step 6).

When the design agent returns, append its line to `.ai/archetypes.jsonl`:
`{"slug":"NN-slug","archetype":"…","palette":"…","font_pair":"…","colors":{"bg":"#…","ink":"#…","accent":"#…"}}`

If the enrich agent flags above-A1 grammar, decide: either accept it (the popup
explains it) or change the sentence in `story.md` **and** in the page's
`[data-story-body]`, then re-run `--lint` and fix the affected entries yourself.

### 4. Apply + checks (main)

```bash
PY .ai/skills/render/render.py stories/NN-slug   # wire popups; refresh index.html + vocabulario.html
PY .ai/skills/render/render.py --lint            # all stories; must exit 0
PY .ai/skills/render/render.py --atlas-check     # fix any warning about this story's lore refs
PY -m unittest discover tests                    # must pass
```

Fix whatever is red yourself. Missed words → add entries to `enrichment.toml`, re-run.

Look at the page if Playwright is available:

```bash
npx playwright screenshot --full-page --viewport-size=1280,900 "file://$PWD/stories/NN-slug/index.html" /tmp/NN-desk.png
npx playwright screenshot --full-page --viewport-size=390,844  "file://$PWD/stories/NN-slug/index.html" /tmp/NN-phone.png
```

Check: text readable, nothing overlapping, no horizontal scroll on the phone shot,
decoration quieter than the prose. Fix small things yourself; for a broken layout,
send the design agent back with the screenshot and what's wrong.

### 5. Branch + push

```bash
git checkout -b story/NN-slug
git add -A && git commit
git push -u origin story/NN-slug
```

### 6. Commit message

```
Add story NN: <Spanish title>

<2–5 lines: setting, protagonist, the dilemma, lore it reuses.>

Rendered as <the in-universe artifact>: <archetype, font pair, palette in a few words>.
```

### 7. Preview

- Cloud session with the Artifact tool: publish `stories/NN-slug/index.html` as an
  artifact (icon `book`) and give its link.
- Always also give the branch link (works on the phone, no login):
  `https://raw.githack.com/usukololgubu/lee-espanol/story/NN-slug/stories/NN-slug/index.html`
- On the user's Windows machine: `start "" "stories/NN-slug/index.html"`.

Send 2–3 lines in Russian: title, logline, the artifact framing. Ask for OK.

### 8. Publish (only after the user's OK)

```bash
git checkout main && git pull --ff-only origin main
git rebase main story/NN-slug && git checkout main   # only if main moved
git merge --ff-only story/NN-slug && git push origin main
git push origin --delete story/NN-slug
```

If main moved, re-run step 4 on the rebased branch before merging: index.html and
vocabulario.html are generated and must be rebuilt, not hand-merged.

GitHub Pages deploys by itself. Reply with the live link:
`https://usukololgubu.github.io/lee-espanol/stories/NN-slug/`

Changes requested instead: make them on the branch, re-run step 4, commit, push, new
preview.
