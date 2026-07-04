# lee-espanol

A personal reading-practice project for Russian-native, A1-level Spanish
learners. Short, atmospheric sci-fi stories in a shared "Space Expansion"
universe — slow contemplative pace, observer-protagonists, moral dilemmas, no
moralizing.

Each story is a single HTML page with hover popups on every meaningful word:
Russian translation, part of speech, lemma, and (when non-obvious) a short
grammar note. Click any word to open it in spanishdict.com.

## Read online

GitHub Pages: <https://usukololgubu.github.io/lee-espanol/>

## What's inside

```
lee-espanol/
├── index.html           ← project table of contents (Pages landing page)
├── profile.md           ← reader profile (taste, level, format choices)
├── .ai/skills/          ← the three pipeline skills (story → enrich → render)
└── stories/
    ├── 01-saturn-ai/
    ├── 02-nueva-andalucia/
    └── 03-zumbido-deriva/
        ├── story.md         ← pure Spanish text + frontmatter
        ├── enrichment.toml  ← per-word data, sentence translations
        └── index.html       ← bespoke render with hover popups
```

## How this was made

Built from the [language-reader-blueprint](https://github.com/usukololgubu/language-reader-blueprint)
recipe — a single-file instruction set for spinning up a similar reader for any
(native, target) language pair. An AI agent reads the blueprint, runs an
interview, scaffolds the project, and generates stories on demand.

## Status

Personal project. Stories are written for one reader's taste; I publish them in
case they're useful to other RU→ES A1 learners, but this is not a curated
product.

## Development

Run the stdlib-only test suite (unittest, no pip deps) from the project root:
`py -m unittest discover tests -v`. Its centerpiece re-renders a copy of every
story and checks the result is byte-identical to the on-disk page. Before
committing story changes, also run `render.py --lint` (coverage/consistency
checks) and, after re-enriching, `render.py --refresh-all` (re-applies
enrichment to every story, then rebuilds index.html/vocabulario.html).
