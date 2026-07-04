#!/usr/bin/env python3
"""
render.py — apply enrichment.toml to a designer-authored HTML page.

The designer writes stories/NN-slug/index.html freely (any palette,
typography, layout, illustration). The element with the
`data-story-body` attribute holds the Spanish story body in any markup
the designer likes (typically <p> tags, optionally with <em>, <small>,
etc. inside).

This script:
  - Finds the element with data-story-body.
  - Walks its inner HTML; tokenizes text between any tags (preserving
    designer markup verbatim).
  - Wraps each Spanish word with <span class="w" data-tr=… data-pos=…
    data-lemma=… data-grammar=…> using [words.<form>] from enrichment.toml.
  - Wraps each sentence-terminator (.?!) with <span class="s" data-tr=…>
    paired in document order with [[sentences]].tr.
  - Auto-injects (or refreshes) the popup behavior CSS invariants
    (<style data-popup-invariants> at end of head) and the popup JS
    (<script data-popup> before </body>). Designer styles popups,
    .w, .s, .lemma, .pos, .tr, .g-block, .s-label, .s-tr, .link via
    their own CSS — the script only provides the behavior bits.
  - Re-runnable: existing .w / .s spans are stripped first so the
    designer can freely edit text in place.
  - Refreshes the project-wide index.html (between STORIES:START/END
    markers).

Usage (from project root):
  py .ai/skills/render/render.py                            # auto-pick newest unrendered or rerun-able
  py .ai/skills/render/render.py stories/05-pasajero-unico
  py .ai/skills/render/render.py --bootstrap stories/06-foo # write minimal design scaffold
  py .ai/skills/render/render.py --index-only               # only refresh project-wide index

Requires Python 3.11+ (tomllib).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tomllib
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
STORIES_DIR = ROOT / "stories"
INDEX_HTML = ROOT / "index.html"
INDEX_CACHE = ROOT / ".ai" / "stories-index.json"
ARCHETYPES_JSONL = ROOT / ".ai" / "archetypes.jsonl"
VOCABULARIO_HTML = ROOT / "vocabulario.html"
LORE_MD = ROOT / "lore.md"
INDEX_FIELDS = ("title", "logline", "protagonist", "setting", "date_generated", "length_words")
DEFAULT_PALETTE = {"bg": "#f5f3ec", "ink": "#1f1d18", "accent": "#8a877e"}

SP_LETTERS = "A-Za-zÀ-ÖØ-öø-ÿ"
WORD_RE = re.compile(rf"[{SP_LETTERS}]+")
# A consecutive run of sentence terminators ("...", "?!", "…") is ONE sentence mark,
# not N — and only an END mark pairs with a [[sentences]] entry. See term_run_is_end().
TERM_RUN_RE = re.compile(r"[.?!…]+")
# After a terminator run: optional closing quote/paren chars, optional whitespace, then
# a lowercase Spanish letter ⇒ the run is a mid-sentence pause, not a sentence end.
TERM_CLOSING_CHARS = "\"'»”’)]"
ES_LOWER_RE = re.compile(r"[a-záéíóúñü]")
# Match a run of digits with strict 3-digit thousands grouping — dot-grouped (7.012,
# 18.942) or space-grouped (1 234, 18 942; regular space, NBSP, or narrow NBSP as the
# separator) — or a plain digit run. Dot grouping is deliberately strict
# (\d{1,3}(\.\d{3})+ only) so a real sentence dot adjacent to digits ("2.5",
# "…el año 100. 5 naves…") is never swallowed into a number token.
NUM_RE = re.compile(r"\d{1,3}(?:\.\d{3})+|\d{1,3}(?:[   ]\d{3})+|\d+")
NUM_SEP_RE = re.compile(r"[.   ]")
WORDISH_RE = re.compile(rf"[{SP_LETTERS}0-9]")


def term_run_is_end(text: str, run_end: int) -> bool:
    """Classify the terminator run ending at `run_end`: True = sentence END (one
    <span class="s"> around the whole run, pairs with one [[sentences]] entry),
    False = mid-sentence pause ("Bip... bip") — plain text, no entry consumed.

    A run is a pause iff it is followed — within the same text segment — by optional
    closing quote/paren chars, optional whitespace, then a lowercase Spanish letter.
    A run at the very end of a segment counts as an end. This is the single shared
    classifier for both rendering and --lint, so their counts can never disagree."""
    k = run_end
    while k < len(text) and text[k] in TERM_CLOSING_CHARS:
        k += 1
    while k < len(text) and text[k].isspace():
        k += 1
    return not (k < len(text) and ES_LOWER_RE.match(text[k]))


# ─── number → words (Spanish cardinal + Russian gloss + grammar) ────────────
# Numbers in the body get the same popup treatment as words, but their entries
# are generated here at render time (deterministic) rather than authored in
# enrichment.toml. A [numbers."<digits>"] table in enrichment.toml can override
# or extend any auto-generated field for a specific token.

_ES_UNITS = [
    "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete",
    "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés",
    "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve",
]
_ES_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta",
            70: "setenta", 80: "ochenta", 90: "noventa"}
_ES_HUNDREDS = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos",
                5: "quinientos", 6: "seiscientos", 7: "setecientos", 8: "ochocientos",
                9: "novecientos"}


def _es_below_thousand(n: int) -> str:
    if n == 0:
        return ""
    if n < 30:
        return _ES_UNITS[n]
    if n < 100:
        t, u = (n // 10) * 10, n % 10
        return _ES_TENS[t] + (" y " + _ES_UNITS[u] if u else "")
    if n == 100:
        return "cien"
    h, rest = n // 100, n % 100
    return _ES_HUNDREDS[h] + (" " + _es_below_thousand(rest) if rest else "")


def _es_apocope(s: str) -> str:
    """uno → un, veintiuno → veintiún, treinta y uno → treinta y un."""
    if s.endswith("veintiuno"):
        return s[:-len("veintiuno")] + "veintiún"
    if s.endswith("uno"):
        return s[:-3] + "un"
    return s


def _es_feminine(s: str) -> str:
    """…cientos → …cientas, trailing uno → una."""
    s = s.replace("cientos", "cientas").replace("quinientos", "quinientas")
    if s.endswith("veintiuno"):
        return s[:-len("veintiuno")] + "veintiuna"
    if s.endswith("uno"):
        return s[:-3] + "una"
    return s


def spanish_cardinal(n: int) -> str:
    if n == 0:
        return "cero"
    parts: list[str] = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        parts.append("un millón" if millions == 1
                     else _es_apocope(_es_below_thousand(millions)) + " millones")
    thousands, rest2 = divmod(rest, 1000)
    if thousands:
        parts.append("mil" if thousands == 1
                     else _es_apocope(_es_below_thousand(thousands)) + " mil")
    if rest2:
        parts.append(_es_below_thousand(rest2))
    return " ".join(parts)


_RU_UNITS = [
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать",
]
_RU_TENS = {20: "двадцать", 30: "тридцать", 40: "сорок", 50: "пятьдесят", 60: "шестьдесят",
            70: "семьдесят", 80: "восемьдесят", 90: "девяносто"}
_RU_HUNDREDS = {1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот",
                6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}


def _ru_below_thousand(n: int) -> str:
    out: list[str] = []
    h, r = n // 100, n % 100
    if h:
        out.append(_RU_HUNDREDS[h])
    if r:
        if r < 20:
            out.append(_RU_UNITS[r])
        else:
            out.append(_RU_TENS[(r // 10) * 10])
            if r % 10:
                out.append(_RU_UNITS[r % 10])
    return " ".join(out)


def _ru_plural(n: int, one: str, few: str, many: str) -> str:
    if n % 100 in range(11, 15):
        return many
    d = n % 10
    if d == 1:
        return one
    if d in (2, 3, 4):
        return few
    return many


def russian_cardinal(n: int) -> str:
    """Nominative reading, masculine baseline (citation form for the gloss)."""
    if n == 0:
        return "ноль"
    parts: list[str] = []
    millions, rest = divmod(n, 1_000_000)
    if millions:
        parts.append(_ru_below_thousand(millions) + " "
                     + _ru_plural(millions, "миллион", "миллиона", "миллионов"))
    thousands, rest2 = divmod(rest, 1000)
    if thousands:
        tw = _ru_below_thousand(thousands)
        # тысяча is feminine: один→одна, два→две (last unit word only)
        if tw.endswith("один"):
            tw = tw[:-len("один")] + "одна"
        elif tw.endswith("два"):
            tw = tw[:-len("два")] + "две"
        parts.append(tw + " " + _ru_plural(thousands, "тысяча", "тысячи", "тысяч"))
    if rest2:
        parts.append(_ru_below_thousand(rest2))
    return " ".join(p for p in parts if p)


def number_grammar(n: int, es: str) -> str:
    """Generate an A1 grammar note for the classic number gotchas, else ''."""
    blocks: list[str] = []
    if n % 10 == 1 and n % 100 != 11:
        apoc, fem = _es_apocope(es), _es_feminine(es)
        blocks.append(
            f"**{es}** → **{apoc}** перед сущ. м. р.: `{apoc} libro`.\n\n"
            f"Ж. р.: **{fem}**: `{fem} casa`."
        )
    if n == 100:
        blocks.append(
            "**cien / ciento** — `cien` перед существительным и перед `mil`/`millones`; "
            "`ciento` в составе 101–199 (`ciento uno`)."
        )
    hundreds = (n % 1000) // 100
    if 2 <= hundreds <= 9:
        masc = _ES_HUNDREDS[hundreds]
        blocks.append(
            f"*-cientos / -cientas* согласуется в роде: **{masc}** (м. р.) → "
            f"**{masc.replace('cientos', 'cientas')}** (ж. р.)."
        )
    return "\n\n".join(blocks)


def number_entry(num_str: str, overrides: dict) -> dict | None:
    try:
        n = int(NUM_SEP_RE.sub("", num_str))
    except ValueError:
        return None
    es = spanish_cardinal(n)
    entry = {"tr": russian_cardinal(n), "pos": "числ.", "lemma": es}
    g = number_grammar(n, es)
    if g:
        entry["grammar"] = g
    ov = overrides.get(num_str)
    if ov:
        entry = {**entry, **ov}
    return entry


# ─── parsers ────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    fm_raw, body = m.groups()
    fm: dict = {}
    for line in fm_raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, body


def load_enrichment(path: Path) -> tuple[dict, list, list, dict]:
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        hint = _toml_error_hint(text, exc)
        sys.exit(f"error: {path} — TOML parse failed: {exc}\n{hint}" if hint else f"error: {path} — TOML parse failed: {exc}")
    return (
        data.get("words", {}),
        data.get("phrases", []) or [],
        data.get("sentences", []) or [],
        data.get("numbers", {}) or {},
    )


def _toml_error_hint(text: str, exc: tomllib.TOMLDecodeError) -> str:
    """Detect the common 'unquoted non-ASCII bare key' failure and suggest the fix."""
    msg = str(exc)
    m = re.search(r"at line (\d+), column (\d+)", msg)
    if not m:
        return ""
    lineno = int(m.group(1))
    lines = text.splitlines()
    if not (1 <= lineno <= len(lines)):
        return ""
    line = lines[lineno - 1]
    th = re.match(r"\s*\[\s*([^\]]*)\s*\]?", line)
    if not th:
        return ""
    header = th.group(1)
    if not header.startswith("words."):
        return ""
    bare_key = header[len("words."):].strip()
    if bare_key.startswith('"'):
        return ""
    if re.search(r"[^A-Za-z0-9_-]", bare_key):
        return (
            f"  hint: line {lineno} table key contains non-ASCII characters. "
            f"TOML bare keys must be [A-Za-z0-9_-]; quote the form instead.\n"
            f"        change  [words.{bare_key}]  →  [words.\"{bare_key}\"]"
        )
    return ""


def split_paragraphs(body: str) -> list[str]:
    body = re.sub(r"^\s*#[^\n]*\n", "", body, count=1).strip()
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


# ─── tokenizer ──────────────────────────────────────────────────────────────

def build_phrase_index(words: dict, phrases: list) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for p in phrases:
        if "form" in p:
            entry = {k: v for k, v in p.items() if k != "form"}
            out.append((p["form"], entry))
    for key, entry in words.items():
        if re.search(rf"[^{SP_LETTERS}]", key):
            out.append((key, entry))
    out.sort(key=lambda x: -len(x[0]))
    return out


def is_wordish(c: str) -> bool:
    return bool(WORDISH_RE.match(c))


def matches_phrase_at(s: str, i: int, form: str) -> bool:
    end = i + len(form)
    if s[i:end].lower() != form.lower():
        return False
    if i > 0 and is_wordish(s[i - 1]):
        return False
    if end < len(s) and is_wordish(s[end]):
        return False
    return True


def esc_attr(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def esc_text(s: str) -> str:
    """Escape for HTML *text* content — leaves quotes alone, so a literal " in the
    prose stays a " (not &quot;) and re-tokenization stays idempotent."""
    return html.escape(s, quote=False)


def unescape_stable(s: str) -> str:
    """Fully decode HTML entities (tolerating accidental multi-level escaping like
    &amp;quot;) so the tokenizer always sees plain text and re-renders are idempotent."""
    for _ in range(6):
        u = html.unescape(s)
        if u == s:
            return s
        s = u
    return s


def word_span(form: str, entry: dict, si: int) -> str:
    extra = ""
    parts = entry.get("parts")
    if parts:
        extra += f' data-parts="{esc_attr(json.dumps(parts, ensure_ascii=False))}"'
    literal = entry.get("literal")
    if literal:
        extra += f' data-literal="{esc_attr(literal)}"'
    return (
        '<span class="w"'
        f' data-tr="{esc_attr(entry.get("tr", ""))}"'
        f' data-pos="{esc_attr(entry.get("pos", ""))}"'
        f' data-lemma="{esc_attr(entry.get("lemma", ""))}"'
        f' data-grammar="{esc_attr(entry.get("grammar", ""))}"'
        f' data-si="{si}"'
        f"{extra}>{esc_text(form)}</span>"
    )


def sentence_span(ch: str, entry: dict, si: int) -> str:
    note = entry.get("note", "")
    extra = f' data-note="{esc_attr(note)}"' if note else ""
    return f'<span class="s" data-tr="{esc_attr(entry.get("tr", ""))}" data-si="{si}"{extra}>{esc_text(ch)}</span>'


def detokenize(content: str) -> str:
    """Strip prior <span class="w"…> and <span class="s"…> wrappers, recovering plain text."""
    while True:
        new = re.sub(r'<span class="w"[^>]*>([^<]*)</span>', r'\1', content)
        new = re.sub(r'<span class="s"[^>]*>([^<]*)</span>', r'\1', new)
        if new == content:
            return content
        content = new


def tokenize_text_segment(
    text: str,
    words: dict,
    phrase_idx: list[tuple[str, dict]],
    take_sent,
    cur_si,
    numbers: dict,
    used_keys: set[str] | None = None,
    stats: dict | None = None,
) -> tuple[str, list[str]]:
    """Tokenize a plain-text fragment (no HTML inside).

    `used_keys`, when passed, collects the lowercased surface form of every
    [words.*] / [[phrases]] entry actually matched — used by `--lint` to find
    orphan entries (authored but never matched in the body) without a second
    tokenizer implementation.

    `stats`, when passed, accumulates "ends" / "pauses" counts of terminator runs
    (classified by term_run_is_end) — again so --lint counts exactly what rendering
    does, through the very same code path.
    """
    text = unescape_stable(text)
    out: list[str] = []
    missed: list[str] = []
    i = 0
    while i < len(text):
        phrase_hit = next(((f, e) for f, e in phrase_idx if matches_phrase_at(text, i, f)), None)
        if phrase_hit:
            form, entry = phrase_hit
            out.append(word_span(text[i:i + len(form)], entry, cur_si()))
            if used_keys is not None:
                used_keys.add(form.lower())
            i += len(form)
            continue
        wm = WORD_RE.match(text, i)
        if wm:
            w = wm.group()
            entry = words.get(w.lower())
            if entry:
                out.append(word_span(w, entry, cur_si()))
                if used_keys is not None:
                    used_keys.add(w.lower())
            else:
                out.append(esc_text(w))
                missed.append(w)
            i = wm.end()
            continue
        nm = NUM_RE.match(text, i)
        if nm:
            num = nm.group()
            entry = number_entry(num, numbers)
            out.append(word_span(num, entry, cur_si()) if entry else esc_text(num))
            i = nm.end()
            continue
        tm = TERM_RUN_RE.match(text, i)
        if tm:
            run = tm.group()
            if term_run_is_end(text, tm.end()):
                si = cur_si()
                out.append(sentence_span(run, take_sent(), si))
                if stats is not None:
                    stats["ends"] = stats.get("ends", 0) + 1
            else:
                out.append(esc_text(run))
                if stats is not None:
                    stats["pauses"] = stats.get("pauses", 0) + 1
            i = tm.end()
            continue
        out.append(esc_text(text[i]))
        i += 1
    return "".join(out), missed


def walk_html_body(
    content: str,
    words: dict,
    phrase_idx: list[tuple[str, dict]],
    sentences: list,
    numbers: dict,
) -> tuple[str, list[str], int]:
    """Walk content, leaving HTML tags untouched and tokenizing text between them.

    Sentence pairing is global (across all paragraphs) in document order.
    """
    s_used = [0]

    def take_sent() -> dict:
        if s_used[0] < len(sentences):
            entry = sentences[s_used[0]]
            s_used[0] += 1
            return entry
        return {}

    def cur_si() -> int:
        return s_used[0]

    out: list[str] = []
    missed: list[str] = []
    i, n = 0, len(content)
    while i < n:
        if content[i] == "<":
            end = content.find(">", i)
            if end == -1:
                out.append(content[i:])
                break
            out.append(content[i:end + 1])
            i = end + 1
        else:
            end = content.find("<", i)
            if end == -1:
                end = n
            seg = content[i:end]
            toked, miss = tokenize_text_segment(seg, words, phrase_idx, take_sent, cur_si, numbers)
            out.append(toked)
            missed.extend(miss)
            i = end
    return "".join(out), missed, s_used[0]


# ─── HTML manipulation ──────────────────────────────────────────────────────

def find_body_region(html_text: str) -> tuple[int, int, str] | None:
    """Locate the element with data-story-body. Returns (content_start, content_end, tag)."""
    m = re.search(r"<(\w+)\b[^>]*?\bdata-story-body\b[^>]*>", html_text)
    if not m:
        return None
    tag = m.group(1)
    open_end = m.end()
    pat = re.compile(rf"<(/?){re.escape(tag)}\b[^>]*>", re.IGNORECASE)
    depth = 1
    for tm in pat.finditer(html_text, open_end):
        if tm.group(1) == "/":
            depth -= 1
            if depth == 0:
                return (open_end, tm.start(), tag)
        else:
            if not tm.group(0).endswith("/>"):
                depth += 1
    return None


def upsert_block(html_text: str, tag: str, attr_token: str, content: str, before_close: str) -> str:
    """Replace existing <tag … attr_token …>…</tag> block, or insert before `before_close`."""
    pat = re.compile(rf"<{tag}\s[^>]*\b{re.escape(attr_token)}\b[^>]*>.*?</{tag}>", re.DOTALL)
    block = f"<{tag} {attr_token}>\n{content}\n</{tag}>"
    if pat.search(html_text):
        return pat.sub(lambda _: block, html_text)
    if before_close in html_text:
        return html_text.replace(before_close, f"{block}\n{before_close}", 1)
    return html_text + "\n" + block + "\n"


# ─── popup invariants (locked) ──────────────────────────────────────────────

POPUP_CSS_INV = """\
/* Behavior-critical — designer styles override visuals via higher specificity. */
.w, .s { cursor: help; border-bottom: 1px dotted currentColor; }
.s { border-bottom-style: dashed; }
/* Scope highlight: the whole sentence (when a sentence popup is open) or the whole
   idiom span. Themed via --accent, falling back to the page's ink color. Designers may
   override with higher specificity. */
.w.hl, .s.hl { background: color-mix(in srgb, var(--accent, currentColor) 16%, transparent); border-radius: 2px; }
.pop {
  position: absolute; z-index: 1000;
  opacity: 0; pointer-events: none;
  transition: opacity 0.18s, transform 0.18s;
}
.pop.show { opacity: 1; pointer-events: auto; }
/* invisible bridge so the cursor can travel from word into popup */
.pop::after {
  content: ''; position: absolute;
  left: -12px; right: -12px;
  height: 12px; bottom: -12px;
}
.pop.below::after { bottom: auto; top: -12px; }

/* Reading progress hairline (auto-managed). Theme via --accent on :root or body;
   hide entirely per-page with .reading-progress{display:none} if it doesn't fit the design. */
.reading-progress {
  position: fixed; top: 0; left: 0; height: 2px;
  width: 0; max-width: 100%;
  background: var(--accent, currentColor);
  z-index: 1001; pointer-events: none;
  transition: width 0.08s linear;
  will-change: width;
}

/* Respect users who prefer reduced motion. Disables decorative animation/transition
   across the page; the progress hairline is also hidden. Popups still appear (no transform
   reliance) — only their fade is shortened. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
  .reading-progress { display: none; }
}

/* "Palabras nuevas" block (auto-injected right after the story body; a designer may
   instead pre-place an element with [data-new-words] anywhere to control the slot).
   Structural only — colors/fonts inherit the page's own vars, overridable per story. */
.nw { margin: 1.6em 0 0; }
.nw summary { cursor: pointer; font-weight: 600; }
.nw ol { margin: 0.6em 0 0; padding-left: 1.3em; }
.nw-item { margin: 0.2em 0; }
.nw-item a { color: inherit; text-decoration: none; }
.nw-lemma { font-style: italic; }
.nw-pos { font-size: 0.75em; opacity: 0.65; margin: 0 0.35em; }
.nw-tr { opacity: 0.85; }
.nw-item a:hover .nw-lemma { color: var(--accent, currentColor); }\
"""

POPUP_JS = r"""(function(){
  var pop = null, active = null, hovered = null, isTouch = false, hlEls = [];
  var sentences = window.__leeSentences || [];
  function ensurePop(){
    if (pop) return pop;
    pop = document.createElement('div');
    pop.className = 'pop';
    document.body.appendChild(pop);
    return pop;
  }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, function(c){
      return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function dictKey(lemma){
    return lemma.replace(/^(el |la |los |las |un |una |unos |unas )/i,'').trim();
  }
  function mdToHtml(md){
    if(!md) return '';
    var s = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    return s.split(/\n\n+/).map(function(p){
      p = p.replace(/`([^`]+)`/g, function(_, c){
        return '<code>' + c.replace(/\[\[([^\]]+)\]\]/g, '<u>$1</u>') + '</code>';
      });
      p = p.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
      p = p.replace(/\*([^*]+)\*/g, '<i>$1</i>');
      p = p.replace(/\[\[([^\]]+)\]\]/g, '<u>$1</u>');
      return '<p>' + p + '</p>';
    }).join('');
  }
  function sentenceHtml(tr, note){
    return '<div class="s-label">traducción</div>' +
      '<div class="s-tr">'+escapeHtml(tr)+'</div>' +
      (note ? '<div class="g-block s-note">'+mdToHtml(note)+'</div>' : '');
  }
  function clearHl(){
    for (var i=0;i<hlEls.length;i++) hlEls[i].classList.remove('hl');
    hlEls = [];
  }
  function setHl(els){
    clearHl();
    for (var i=0;i<els.length;i++) els[i].classList.add('hl');
    hlEls = els;
  }
  // forceSentence: true when Shift is held — render any word as its full-sentence popup.
  function show(el, forceSentence){
    var p = ensurePop();
    var asSentence = el.classList.contains('s') || (forceSentence && el.classList.contains('w'));
    if (asSentence){
      var str = '', snote = '';
      if (el.classList.contains('s')){ str = el.dataset.tr || ''; snote = el.dataset.note || ''; }
      else { var s = sentences[+el.dataset.si] || {}; str = s.tr || ''; snote = s.note || ''; }
      p.classList.add('sentence');
      p.classList.remove('idiom');
      p.classList.toggle('has-grammar', !!snote);
      p.innerHTML = sentenceHtml(str, snote);
    } else {
      p.classList.remove('sentence');
      var tr = el.dataset.tr || '', pos = el.dataset.pos || '', lemma = el.dataset.lemma || '', grammar = el.dataset.grammar || '';
      var rawParts = el.dataset.parts || '', literal = el.dataset.literal || '';
      var isIdiom = !!rawParts || !!literal || pos === 'идиома';
      var displayLemma = lemma || el.textContent;
      var linkHtml = lemma
        ? '<a class="link" href="https://www.spanishdict.com/translate/' + encodeURIComponent(dictKey(lemma)) + '" target="_blank" rel="noopener">SpanishDict ↗</a>'
        : '';
      var breakdownHtml = '';
      if (rawParts){
        try {
          var arr = JSON.parse(rawParts);
          if (arr && arr.length){
            breakdownHtml = '<div class="breakdown">' + arr.map(function(it){
              return '<div class="bd-row"><span class="bd-w">'+escapeHtml(it.w)+'</span>'+
                     '<span class="bd-tr">'+escapeHtml(it.tr)+'</span></div>';
            }).join('') + '</div>';
          }
        } catch(_){}
      }
      var literalHtml = literal ? '<div class="literal"><span class="lit-label">досл.</span> '+escapeHtml(literal)+'</div>' : '';
      var grammarHtml = grammar ? '<div class="g-block">'+mdToHtml(grammar)+'</div>' : '';
      p.classList.toggle('has-grammar', !!grammar || !!breakdownHtml || !!literal);
      p.classList.toggle('idiom', isIdiom);
      p.innerHTML =
        '<div class="lemma">'+escapeHtml(displayLemma)+'</div>' +
        (pos ? '<div class="pos">'+escapeHtml(pos)+'</div>' : '') +
        '<div class="tr">'+escapeHtml(tr)+'</div>' +
        breakdownHtml + literalHtml + grammarHtml + linkHtml;
    }
    p.classList.add('show');
    position(p, el);
    if (active && active!==el) active.classList.remove('active');
    el.classList.add('active');
    active = el;
    // Scope highlight: whole sentence (all spans sharing data-si) or whole idiom span.
    if (asSentence){
      var si = el.dataset.si;
      var set = si != null
        ? Array.prototype.slice.call(document.querySelectorAll('.w[data-si="'+si+'"], .s[data-si="'+si+'"]'))
        : [];
      setHl(set.length ? set : [el]);
    } else if (isIdiom){
      setHl([el]);
    } else {
      clearHl();
    }
  }
  function hide(){
    hovered = null;
    clearHl();
    if (!pop) return;
    pop.classList.remove('show');
    if (active){ active.classList.remove('active'); active = null; }
  }
  function position(p, el){
    var r = el.getBoundingClientRect();
    var ph = p.offsetHeight || 120, pw = p.offsetWidth || 220;
    var top = window.scrollY + r.top - ph - 12, below = false;
    if (top < window.scrollY + 8){ top = window.scrollY + r.bottom + 12; below = true; }
    var left = window.scrollX + r.left - 10;
    if (left + pw > window.scrollX + window.innerWidth - 12) left = window.scrollX + window.innerWidth - pw - 12;
    if (left < window.scrollX + 8) left = window.scrollX + 8;
    // top/left are document coordinates. The popup is positioned relative to its
    // offsetParent (e.g. a position:relative <body> shifted down by a child's
    // margin), whose origin may differ from the document origin — subtract it so
    // the popup lands on the correct side of the word instead of over it.
    var host = p.offsetParent;
    if (host){
      var hr = host.getBoundingClientRect(), cs = getComputedStyle(host);
      top -= hr.top + window.scrollY + (parseFloat(cs.borderTopWidth) || 0);
      left -= hr.left + window.scrollX + (parseFloat(cs.borderLeftWidth) || 0);
    }
    p.style.top = top + 'px';
    p.style.left = left + 'px';
    p.classList.toggle('below', below);
  }
  document.addEventListener('mouseover', function(e){
    if (isTouch) return;
    var el = e.target.closest('.w, .s');
    if (el){ hovered = el; show(el, e.shiftKey); }
  });
  document.addEventListener('mouseout', function(e){
    if (isTouch) return;
    var el = e.target.closest('.w, .s');
    if (!el) return;
    var to = e.relatedTarget;
    if (to && to.closest && (to.closest('.w, .s') === el || to.closest('.pop'))) return;
    hide();
  });
  // Holding Shift turns any word popup into its full-sentence popup; releasing reverts.
  function onShift(e){
    if (e.key !== 'Shift' || !hovered) return;
    if (hovered.classList.contains('w')) show(hovered, e.shiftKey);
  }
  document.addEventListener('keydown', onShift);
  document.addEventListener('keyup', onShift);
  document.addEventListener('click', function(e){
    var el = e.target.closest('.w, .s'), onPop = e.target.closest('.pop');
    if (el){ if (active === el) hide(); else { hovered = el; show(el, e.shiftKey); } }
    else if (!onPop) hide();
  });
  document.addEventListener('touchstart', function(){ isTouch = true; }, {passive:true});
  window.addEventListener('scroll', function(){ if (active && pop) position(pop, active); }, {passive:true});
  window.addEventListener('resize', function(){ if (active && pop) position(pop, active); });

  // Reading progress hairline — appended to body, width tracks scroll percentage.
  var bar = document.createElement('div');
  bar.className = 'reading-progress';
  document.body.appendChild(bar);
  function updateProgress(){
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var pct = max > 0 ? (h.scrollTop / max) * 100 : 0;
    bar.style.width = pct + '%';
  }
  window.addEventListener('scroll', updateProgress, {passive:true});
  window.addEventListener('resize', updateProgress);
  updateProgress();

  // Vocabulario deep-link: #hl=<urlencoded lemma> highlights and scrolls to the first
  // matching word/expression span. Matches data-lemma case-insensitively; when a span
  // carries no data-lemma (proper nouns and lemma-less idioms render it empty on
  // purpose — see render SKILL.md), falls back to comparing its visible text instead.
  try {
    if (location.hash.indexOf('#hl=') === 0) {
      var hlTarget = decodeURIComponent(location.hash.slice(4)).toLowerCase();
      if (hlTarget) {
        var hlAll = document.querySelectorAll('.w');
        var hlMatches = [];
        for (var hi = 0; hi < hlAll.length; hi++) {
          var hlEl = hlAll[hi];
          var hlLemma = (hlEl.dataset.lemma || '').toLowerCase();
          var hlHit = hlLemma ? hlLemma === hlTarget : (hlEl.textContent || '').trim().toLowerCase() === hlTarget;
          if (hlHit) hlMatches.push(hlEl);
        }
        if (hlMatches.length) {
          for (var hj = 0; hj < hlMatches.length; hj++) hlMatches[hj].classList.add('hl');
          hlMatches[0].scrollIntoView({block: 'center'});
        }
      }
    }
  } catch (_) {}
})();"""


# ─── bootstrap scaffold (when designer wants a starting point) ─────────────

BOOTSTRAP_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>

<!-- TODO: design freely from here. The script only edits text inside [data-story-body]
     and the auto-managed <style data-popup-invariants> / <script data-popup> blocks. -->
<style>
:root {{ --accent: #8a6a2b; }}
body {{
  font-family: Georgia, 'Times New Roman', serif;
  max-width: 660px;
  margin: 4rem auto;
  padding: 0 1.5rem;
  line-height: 1.85;
  color: #1a1a1a;
  background: #f6f3ec;
}}
h1 {{ font-size: 2.4rem; margin: 0 0 0.6rem; }}
.meta {{ font-size: 0.78rem; letter-spacing: 0.18em; text-transform: uppercase; color: #6f6b62; margin-bottom: 2rem; }}
a.back {{ position: absolute; top: 1.4rem; left: 1.4rem; font-size: 0.78rem; color: #6f6b62; text-decoration: none; letter-spacing: 0.1em; text-transform: uppercase; }}
article p {{ margin: 0 0 1.2rem; }}

/* Default popup look — designer should restyle to match the page. */
.pop {{
  background: #1a1a1a; color: #f3f3f3;
  padding: 0.85rem 1rem; border-radius: 4px;
  max-width: 320px;
  font-size: 0.92rem; line-height: 1.5;
}}
.pop.has-grammar {{ max-width: 380px; }}
.pop.idiom {{ max-width: 400px; }}
.pop.sentence {{ max-width: 340px; }}
.pop .lemma {{ font-style: italic; font-size: 1.1rem; margin-bottom: 0.2rem; }}
.pop .pos {{ font-size: 0.65rem; letter-spacing: 0.25em; text-transform: uppercase; opacity: 0.6; margin-bottom: 0.45rem; }}
.pop .tr {{ margin-bottom: 0.5rem; }}
.pop .g-block {{ border-top: 1px solid rgba(255,255,255,0.18); padding-top: 0.5rem; margin-top: 0.4rem; font-size: 0.86rem; line-height: 1.55; }}
.pop .g-block p {{ margin: 0 0 0.45rem; }}
.pop .g-block p:last-child {{ margin-bottom: 0; }}
.pop .g-block b {{ font-weight: 600; font-style: italic; }}
.pop .g-block i {{ font-size: 0.78rem; letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.85; font-style: normal; }}
.pop .g-block code {{ font-family: monospace; padding: 0 0.3em; background: rgba(255,255,255,0.08); border-radius: 2px; }}
.pop .g-block u {{ text-decoration: none; background: rgba(255,255,255,0.18); padding: 0 0.2em; border-radius: 2px; font-weight: 600; }}
/* Idiom word-by-word breakdown (one row per part). */
.pop .breakdown {{ border-top: 1px solid rgba(255,255,255,0.18); margin-top: 0.45rem; padding-top: 0.45rem; display: grid; gap: 0.18rem; }}
.pop .bd-row {{ display: flex; justify-content: space-between; gap: 1.2rem; font-size: 0.85rem; }}
.pop .bd-w {{ font-style: italic; }}
.pop .bd-tr {{ opacity: 0.7; text-align: right; }}
.pop .literal {{ margin-top: 0.4rem; font-size: 0.82rem; opacity: 0.82; }}
.pop .literal .lit-label {{ font-size: 0.6rem; letter-spacing: 0.25em; text-transform: uppercase; opacity: 0.6; margin-right: 0.35em; }}
.pop .link {{ display: inline-block; margin-top: 0.3rem; font-size: 0.78rem; opacity: 0.7; color: inherit; }}
.pop.sentence .s-label {{ font-size: 0.6rem; letter-spacing: 0.3em; text-transform: uppercase; opacity: 0.55; margin-bottom: 0.3rem; }}
.pop.sentence .s-tr {{ font-style: italic; font-size: 1rem; }}
.pop.sentence .s-note {{ font-style: normal; }}
</style>
</head>
<body>

<a class="back" href="../../index.html">← Índice</a>

<main>
<h1>{title}</h1>
<div class="meta">{meta}</div>

<article data-story-body>
{paragraphs}
</article>
</main>

</body>
</html>
"""


def render_bootstrap(fm: dict, paragraphs: list[str]) -> str:
    title = fm.get("title", "")
    meta_parts = [fm.get("protagonist", ""), fm.get("setting", "")]
    extras = []
    if fm.get("length_words"):
        extras.append(f'{fm["length_words"]} palabras')
    if fm.get("date_generated"):
        extras.append(fm["date_generated"])
    meta = " · ".join([p for p in meta_parts + extras if p])
    body_html = "\n".join(f"  <p>{html.escape(p)}</p>" for p in paragraphs)
    return BOOTSTRAP_TEMPLATE.format(
        title=html.escape(title),
        meta=html.escape(meta),
        paragraphs=body_html,
    )


# ─── project-wide index refresh ─────────────────────────────────────────────

def disk_slugs() -> list[str]:
    if not STORIES_DIR.is_dir():
        return []
    return [
        sub.name for sub in sorted(STORIES_DIR.iterdir())
        if sub.is_dir() and re.match(r"\d{2}-", sub.name) and (sub / "story.md").exists()
    ]


def slug_fm(slug: str) -> dict:
    fm, _ = parse_frontmatter((STORIES_DIR / slug / "story.md").read_text(encoding="utf-8"))
    return {k: fm.get(k, "") for k in INDEX_FIELDS}


def load_index_cache() -> dict | None:
    if not INDEX_CACHE.exists():
        return None
    try:
        return json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_index_cache(cache: dict) -> None:
    INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_cache_from_disk() -> dict:
    return {slug: slug_fm(slug) for slug in disk_slugs()}


def get_or_rebuild_cache() -> dict:
    """Return a cache that matches the on-disk slug set. Rebuild if missing or stale."""
    cache = load_index_cache()
    if cache is None or set(cache.keys()) != set(disk_slugs()):
        cache = build_cache_from_disk()
        save_index_cache(cache)
    return cache


def fmt_date(d: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", d or "")
    return f"{m.group(1)[2:]}·{m.group(2)}·{m.group(3)}" if m else (d or "")


def load_palettes() -> dict[str, dict]:
    """Read .ai/archetypes.jsonl and return {slug: {bg, ink, accent}}.
    Missing slugs fall back to DEFAULT_PALETTE; missing colors keys are filled from the default."""
    out: dict[str, dict] = {}
    if not ARCHETYPES_JSONL.exists():
        return out
    for line in ARCHETYPES_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        slug = obj.get("slug")
        colors = obj.get("colors") or {}
        if slug:
            out[slug] = {**DEFAULT_PALETTE, **{k: v for k, v in colors.items() if k in DEFAULT_PALETTE}}
    return out


def render_entry(slug: str, fm: dict, palette: dict | None = None) -> str:
    num = slug[:2]
    title = fm.get("title", slug)
    logline = fm.get("logline", "")
    if not logline:
        # fall back to the old protagonist · setting line so nothing renders blank
        parts = [fm.get("protagonist", ""), fm.get("setting", "")]
        logline = " · ".join(p for p in parts if p)
    p = palette or DEFAULT_PALETTE
    style = f'--card-accent:{p["accent"]}'
    return (
        f'    <a class="entry" data-slug="{html.escape(slug, quote=True)}" href="stories/{slug}/index.html" style="{html.escape(style, quote=True)}">\n'
        f'      <span class="num">{html.escape(num)}</span>\n'
        '      <div class="body">\n'
        f'        <div class="e-title">{html.escape(title)}</div>\n'
        f'        <div class="logline">{html.escape(logline)}</div>\n'
        '      </div>\n'
        '      <div class="aside">\n'
        f'        <span class="date">{html.escape(fmt_date(fm.get("date_generated", "")))}</span>\n'
        f'        <span class="words">{html.escape(str(fm.get("length_words", "")))} palabras</span>\n'
        '      </div>\n'
        '    </a>'
    )


def ordered_slugs(slugs: list[str]) -> list[str]:
    """Newest-first by slug number (e.g. 20, 19, … 01). The index is a single-column
    ledger, so the freshest story sits at the top with no extra scrolling."""
    return sorted(slugs, reverse=True)


def write_index_html(cache: dict) -> int:
    """Render the entries block from cache. Returns entry count."""
    if not INDEX_HTML.exists():
        sys.exit(f"error: {INDEX_HTML} missing — bootstrap by hand once, then this script keeps it in sync")
    text = INDEX_HTML.read_text(encoding="utf-8")
    if "<!-- STORIES:START -->" not in text or "<!-- STORIES:END -->" not in text:
        sys.exit("error: index.html lacks <!-- STORIES:START --> / <!-- STORIES:END --> markers")
    slugs = ordered_slugs(list(cache.keys()))
    palettes = load_palettes()
    entries = "\n\n".join(render_entry(slug, cache[slug], palettes.get(slug)) for slug in slugs)
    new_block = f"<!-- STORIES:START -->\n\n{entries}\n\n<!-- STORIES:END -->"
    text = re.sub(r"<!-- STORIES:START -->.*?<!-- STORIES:END -->", lambda _: new_block, text, flags=re.DOTALL)
    text = re.sub(r'<span class="stat">[^<]*</span>', f'<span class="stat">{len(slugs):02d} entradas</span>', text, count=1)
    INDEX_HTML.write_text(text, encoding="utf-8")
    return len(slugs)


def refresh_index_incremental(slug: str) -> int:
    """Update only `slug`'s entry in the cache, then rewrite the index HTML. Falls back to full rebuild on slug-set mismatch."""
    cache = load_index_cache()
    on_disk = set(disk_slugs())
    if cache is None or set(cache.keys()) | {slug} != on_disk:
        cache = build_cache_from_disk()
    else:
        cache[slug] = slug_fm(slug)
    save_index_cache(cache)
    count = write_index_html(cache)
    vocab_count = write_vocabulario(cache)
    print(f"vocabulario.html refreshed — {vocab_count} entries")
    return count


def refresh_index_full() -> int:
    """Force a full rebuild from disk; used by --index-only."""
    cache = build_cache_from_disk()
    save_index_cache(cache)
    count = write_index_html(cache)
    vocab_count = write_vocabulario(cache)
    print(f"vocabulario.html refreshed — {vocab_count} entries")
    return count


# ─── vocabulary aggregation (vocabulario.html) ──────────────────────────────
# Aggregates every story's [words.*] / [[phrases]] tables into a single
# cross-story reference page. Regenerated on every render (single-story or
# full) so it can never go stale — see write_vocabulario() and its two call
# sites in refresh_index_incremental / refresh_index_full above.

_LEADING_ARTICLES = ("el ", "la ", "los ", "las ", "un ", "una ")


def _strip_accents(s: str) -> str:
    n = unicodedata.normalize("NFKD", s)
    return "".join(c for c in n if not unicodedata.combining(c))


def es_sort_key(lemma: str) -> tuple:
    """Spanish-alphabetical sort key: leading article and accents stripped (sort key only)."""
    low = lemma.lower()
    for art in _LEADING_ARTICLES:
        if low.startswith(art):
            low = low[len(art):]
            break
    return (_strip_accents(low), lemma.lower())


def slugify_lemma(s: str) -> str:
    """Stable HTML-id-safe anchor for a lemma/expression (accent-stripped, lowercased)."""
    base = _strip_accents(s).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "x"


def collect_story_vocab_rows(words: dict, phrases: list) -> list[tuple[str, str, str, str, str, str]]:
    """Flatten one story's [words.*] and [[phrases]] tables into aggregation rows:
    (group_key, display_lemma, pos, tr, match_target, origin).

    `group_key` is the identity used to merge the same word/expression across stories:
    lemma.lower() (fallback: surface form) for [words.*], form.lower() for [[phrases]].
    `match_target` is the value that ends up in the rendered <span data-lemma=…> for
    *this* story's own occurrence (or, when the entry carries no lemma, the surface
    form) — used to build vocabulario.html's #hl=… deep links and matched by the popup
    JS's data-lemma / text-content fallback. `origin` is "word" or "phrase" (phrases
    always classify as Expresiones regardless of their `pos`, per the vocab-page spec).
    Numbers are never present here — they are generated at render time, not authored.
    """
    rows: list[tuple[str, str, str, str, str, str]] = []
    for form, entry in words.items():
        pos = entry.get("pos", "")
        if pos == "числ.":
            continue
        raw_lemma = entry.get("lemma", "")
        lemma = raw_lemma or form
        rows.append((lemma.lower(), lemma, pos, entry.get("tr", ""), raw_lemma or form, "word"))
    for p in phrases:
        form = p.get("form")
        if not form:
            continue
        raw_lemma = p.get("lemma", "")
        rows.append((form.lower(), form, p.get("pos", ""), p.get("tr", ""), raw_lemma or form, "phrase"))
    return rows


def _vocab_section(origin: str, pos: str) -> str:
    if origin == "phrase":
        return "expresiones"
    if pos == "имя":
        return "nombres"
    if pos == "идиома":
        return "expresiones"
    return "palabras"


def aggregate_vocabulary(slugs: list[str], cache: dict) -> dict[str, list[dict]]:
    """Aggregate [words.*] / [[phrases]] across `slugs` (expected in ascending seq order)
    into {"palabras": […], "expresiones": […], "nombres": […]}, each entry carrying
    lemma/pos/tr (from first appearance) and an ordered, per-slug-deduped appearances list."""
    buckets: dict[tuple[str, str], dict] = {}
    for slug in slugs:
        toml_path = STORIES_DIR / slug / "enrichment.toml"
        if not toml_path.exists():
            continue
        try:
            words, phrases, _, _ = load_enrichment(toml_path)
        except SystemExit:
            continue
        seq = int(slug[:2]) if slug[:2].isdigit() else 0
        title = cache.get(slug, {}).get("title", slug)
        for key, lemma, pos, tr, match_target, origin in collect_story_vocab_rows(words, phrases):
            section = _vocab_section(origin, pos)
            bucket_key = (section, key)
            b = buckets.get(bucket_key)
            if b is None:
                b = {"lemma": lemma, "pos": pos, "tr": tr, "appearances": [], "seen": set()}
                buckets[bucket_key] = b
            if slug not in b["seen"]:
                b["seen"].add(slug)
                b["appearances"].append((seq, slug, title, match_target))

    out: dict[str, list[dict]] = {"palabras": [], "expresiones": [], "nombres": []}
    for (section, _key), b in buckets.items():
        out[section].append({
            "lemma": b["lemma"],
            "pos": b["pos"],
            "tr": b["tr"],
            "appearances": b["appearances"],
            "count": len(b["appearances"]),
        })
    for section in out:
        out[section].sort(key=lambda e: es_sort_key(e["lemma"]))
    return out


def assign_anchors(sections: dict[str, list[dict]]) -> None:
    """Give every entry a stable, collision-free HTML id, in sorted (display) order."""
    used: set[str] = set()
    for section in ("palabras", "expresiones", "nombres"):
        for entry in sections[section]:
            base = slugify_lemma(entry["lemma"])
            anchor = base
            n = 2
            while anchor in used:
                anchor = f"{base}-{n}"
                n += 1
            used.add(anchor)
            entry["anchor"] = anchor


VOCAB_CSS = """
:root{
  --bg:#f5f3ec;
  --bg-soft:#ede9da;
  --ink:#1f1d18;
  --ink-soft:#4a4740;
  --muted:#8a877e;
  --hair:#c8c2b3;
  --hair-soft:#dcd6c5;
}
*{box-sizing:border-box}
html{background:var(--bg)}
body{
  margin:0;
  font-family:'Courier Prime','Courier New',Courier,monospace;
  font-size:15px;
  line-height:1.6;
  color:var(--ink);
  background:var(--bg);
  min-height:100vh;
  -webkit-font-smoothing:antialiased;
}
.page{max-width:880px;margin:0 auto;padding:3rem 2rem 3.5rem;position:relative}
.head{border-top:2px solid var(--ink);border-bottom:1px solid var(--ink);padding:0.55rem 0;font-weight:700;font-size:0.78rem;letter-spacing:0.18em;text-transform:uppercase;text-align:center}
.head .sep{color:var(--muted);margin:0 0.45em;font-weight:400}
.intro{margin:1.7rem auto 1.4rem;max-width:640px;font-size:0.92rem;line-height:1.7;color:var(--ink-soft)}
.stats{display:flex;gap:1.4rem;flex-wrap:wrap;font-size:0.78rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--ink);padding-bottom:0.6rem;margin-bottom:1rem}
.stats b{color:var(--ink);font-weight:700}
.filter-row{margin:0 0 1.6rem}
.filter-row input{width:100%;font:inherit;font-size:0.92rem;padding:0.55rem 0.7rem;border:1px solid var(--hair);border-radius:2px;background:var(--bg-soft);color:var(--ink)}
.filter-row input::placeholder{color:var(--muted)}
.filter-row input:focus{outline:none;border-color:var(--muted)}
.v-section{margin-top:2.2rem}
.v-section h2{font-size:0.8rem;letter-spacing:0.2em;text-transform:uppercase;font-weight:700;border-bottom:1px solid var(--ink);padding-bottom:0.4rem;margin:0 0 0.2rem}
.v-sec-count{font-weight:400;letter-spacing:0.1em;color:var(--muted)}
.v-list{border-top:1px solid var(--hair)}
.v-entry{display:grid;grid-template-columns:1fr auto auto;column-gap:1rem;row-gap:0.15rem;align-items:baseline;padding:0.6rem 0.2rem;border-bottom:1px solid var(--hair)}
.v-entry.is-hidden{display:none}
.v-lemma{font-weight:700;grid-column:1}
.v-pos{font-size:0.68rem;letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);grid-column:2}
.v-count{font-size:0.72rem;color:var(--muted);grid-column:3;text-align:right}
.v-tr{grid-column:1/3;font-style:italic;color:var(--ink-soft);font-size:0.88rem}
.v-refs{grid-column:3;text-align:right;font-size:0.78rem;white-space:nowrap}
.v-refs a{color:var(--muted);text-decoration:none;border-bottom:1px dotted var(--hair);margin-left:0.35em}
.v-refs a:hover{color:var(--ink);border-bottom-color:var(--ink)}
.v-section.is-hidden{display:none}
.empty-note{color:var(--muted);font-style:italic;padding:0.6rem 0.2rem}
footer.colophon{margin-top:2.2rem;padding-top:0.7rem;border-top:1px solid var(--ink);display:flex;justify-content:space-between;flex-wrap:wrap;font-size:0.72rem;letter-spacing:0.12em;color:var(--ink-soft);gap:0.8rem}
footer.colophon a{color:inherit;text-decoration:none;border-bottom:1px dotted var(--hair)}
footer.colophon a:hover{color:var(--ink);border-bottom-color:var(--ink)}
@media(max-width:640px){
  .page{padding:2.2rem 1.1rem 2.8rem;max-width:none}
  body{font-size:14px}
  .v-entry{grid-template-columns:1fr auto}
  .v-refs{grid-column:1/3;text-align:left}
  .v-count{grid-column:2}
}
""".strip()

VOCAB_JS = r"""
(function(){
  var input = document.getElementById('filter');
  if (!input) return;
  var entries = Array.prototype.slice.call(document.querySelectorAll('.v-entry'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.v-section'));
  function apply(){
    var q = input.value.trim().toLowerCase();
    entries.forEach(function(el){
      var hit = !q || (el.dataset.search || '').indexOf(q) !== -1;
      el.classList.toggle('is-hidden', !hit);
    });
    sections.forEach(function(sec){
      var visible = sec.querySelectorAll('.v-entry:not(.is-hidden)').length;
      sec.classList.toggle('is-hidden', !!q && visible === 0);
    });
  }
  input.addEventListener('input', apply);
})();
""".strip()


def render_vocabulario_html(sections: dict[str, list[dict]], story_count: int) -> str:
    assign_anchors(sections)
    counts = {k: len(v) for k, v in sections.items()}

    def entry_html(e: dict) -> str:
        refs = " ".join(
            f'<a href="stories/{slug}/index.html#hl={quote(match_target)}">#{seq}</a>'
            for seq, slug, _title, match_target in e["appearances"]
        )
        search = html.escape((e["lemma"] + " " + e["tr"]).lower(), quote=True)
        return (
            f'    <div class="v-entry" id="{e["anchor"]}" data-search="{search}">\n'
            f'      <span class="v-lemma">{html.escape(e["lemma"])}</span>\n'
            f'      <span class="v-pos">{html.escape(e["pos"])}</span>\n'
            f'      <span class="v-count">×{e["count"]}</span>\n'
            f'      <span class="v-tr">{html.escape(e["tr"])}</span>\n'
            f'      <span class="v-refs">{refs}</span>\n'
            f'    </div>'
        )

    def section_html(key: str, title: str) -> str:
        items = sections[key]
        body = "\n\n".join(entry_html(e) for e in items) if items else '    <p class="empty-note">(vacío)</p>'
        return (
            f'  <section class="v-section" data-section="{key}">\n'
            f'    <h2>{title} <span class="v-sec-count">({len(items)})</span></h2>\n'
            f'    <div class="v-list">\n{body}\n    </div>\n'
            f'  </section>'
        )

    body_sections = "\n\n".join([
        section_html("palabras", "Palabras"),
        section_html("expresiones", "Expresiones"),
        section_html("nombres", "Nombres"),
    ])

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Spanish Reader · Vocabulario</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Courier+Prime:ital,wght@0,400;0,700;1,400;1,700&display=swap" rel="stylesheet">
<style>
{VOCAB_CSS}
</style>
</head>
<body>

<div class="page">

  <header class="head">
    Spanish Reader<span class="sep">·</span>Vocabulario acumulado<span class="sep">·</span>2026
  </header>

  <p class="intro">
    Todo el vocabulario visto a lo largo de los relatos, en un solo lugar.
    Cada entrada enlaza a las historias donde aparece.
  </p>

  <div class="stats">
    <span><b>{counts['palabras']}</b> palabras</span>
    <span><b>{counts['expresiones']}</b> expresiones</span>
    <span><b>{counts['nombres']}</b> nombres</span>
    <span><b>{story_count}</b> historias</span>
  </div>

  <div class="filter-row">
    <input id="filter" type="text" placeholder="Filtrar por palabra o traducción…" autocomplete="off">
  </div>

{body_sections}

  <footer class="colophon">
    <span class="motto">generado automáticamente por render.py</span>
    <a href="index.html">Índice</a>
  </footer>

</div>

<script>
{VOCAB_JS}
</script>
</body>
</html>
"""


def write_vocabulario(cache: dict) -> int:
    """Rebuild vocabulario.html from every story that has an enrichment.toml. Returns total entries."""
    slugs = sorted(
        (s for s in cache.keys() if (STORIES_DIR / s / "enrichment.toml").exists()),
        key=lambda s: int(s[:2]) if s[:2].isdigit() else 0,
    )
    sections = aggregate_vocabulary(slugs, cache)
    VOCABULARIO_HTML.write_text(render_vocabulario_html(sections, len(slugs)), encoding="utf-8")
    return sum(len(v) for v in sections.values())


# ─── orchestration ──────────────────────────────────────────────────────────

def resolve_story_path(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.is_absolute():
            cand = (Path.cwd() / arg).resolve()
            p = cand if cand.is_dir() else (ROOT / arg).resolve()
        if not p.is_dir():
            sys.exit(f"error: {p} is not a directory")
        return p
    candidates = [
        s for s in sorted(STORIES_DIR.iterdir())
        if s.is_dir() and (s / "story.md").exists() and (s / "enrichment.toml").exists()
    ]
    if not candidates:
        sys.exit("error: no stories with story.md + enrichment.toml found; pass a path explicitly")
    return candidates[-1]


def region_close_end(html_text: str, tag: str, content_end: int) -> int:
    """Position right after the closing `</tag …>` located at `content_end` (as returned by
    find_body_region), so callers can insert a sibling element immediately following it."""
    m = re.match(rf"</{re.escape(tag)}\b[^>]*>", html_text[content_end:], re.IGNORECASE)
    return content_end + m.end() if m else content_end


def new_words_for_story(words: dict, phrases: list, earlier_keys: set[str]) -> list[dict]:
    """This story's [words.*] / [[phrases]] group-keys minus every EARLIER story's
    (lower seq) group-keys = first appearances in the corpus, Spanish-alphabetically sorted."""
    seen: dict[str, dict] = {}
    for key, lemma, pos, tr, _match_target, _origin in collect_story_vocab_rows(words, phrases):
        if key not in seen:
            seen[key] = {"lemma": lemma, "pos": pos, "tr": tr}
    items = [v for k, v in seen.items() if k not in earlier_keys]
    items.sort(key=lambda e: es_sort_key(e["lemma"]))
    return items


def upsert_new_words_block(html_text: str, body_tag: str, content_end: int, items: list[dict]) -> str:
    """Fill an existing [data-new-words] element in place (designer-placed or previously
    injected), or auto-insert a fresh <details> immediately after the story-body element."""
    lis = "\n".join(
        '      <li class="nw-item"><a href="../../vocabulario.html#{anchor}">'
        '<span class="nw-lemma">{lemma}</span> <span class="nw-pos">{pos}</span> '
        '<span class="nw-tr">{tr}</span></a></li>'.format(
            anchor=slugify_lemma(e["lemma"]),
            lemma=html.escape(e["lemma"]),
            pos=html.escape(e["pos"]),
            tr=html.escape(e["tr"]),
        )
        for e in items
    )
    inner = f'  <summary>Palabras nuevas ({len(items)})</summary>\n  <ol>\n{lis}\n  </ol>' if items else \
        f'  <summary>Palabras nuevas (0)</summary>'

    existing_re = re.compile(r"<(\w+)([^>]*\bdata-new-words\b[^>]*)>.*?</\1>", re.DOTALL)
    m = existing_re.search(html_text)
    if m:
        tag, attrs = m.group(1), m.group(2)
        if "class=" not in attrs:
            attrs += ' class="nw"'
        block = f"<{tag}{attrs}>\n{inner}\n</{tag}>"
        return html_text[:m.start()] + block + html_text[m.end():]

    close_end = region_close_end(html_text, body_tag, content_end)
    block = f"\n<details data-new-words class=\"nw\">\n{inner}\n</details>\n"
    return html_text[:close_end] + block + html_text[close_end:]


def apply_enrichment(story_dir: Path) -> None:
    md_path = story_dir / "story.md"
    toml_path = story_dir / "enrichment.toml"
    out_path = story_dir / "index.html"

    if not md_path.exists():
        sys.exit(f"error: {md_path} not found")
    if not toml_path.exists():
        sys.exit(f"error: {toml_path} not found — run /enrich first")
    if not out_path.exists():
        sys.exit(
            f"error: {out_path} not found — design the page first, "
            f"or run with --bootstrap stories/{story_dir.name} for a starter scaffold"
        )

    fm, body = parse_frontmatter(md_path.read_text(encoding="utf-8"))
    words, phrases, sentences, numbers = load_enrichment(toml_path)
    phrase_idx = build_phrase_index(words, phrases)

    html_text = out_path.read_text(encoding="utf-8")
    region = find_body_region(html_text)
    if region is None:
        sys.exit(
            f"error: {out_path} has no element with [data-story-body]. "
            f"Add data-story-body to the element wrapping your <p> tags."
        )
    content_start, content_end, body_tag = region
    body_region = html_text[content_start:content_end]
    body_region = detokenize(body_region)
    new_body, missed, used = walk_html_body(body_region, words, phrase_idx, sentences, numbers)

    html_text = html_text[:content_start] + new_body + html_text[content_end:]

    # "Palabras nuevas": this story's lemma-keys minus the union of every earlier (lower
    # seq) story's lemma-keys. Earlier stories with unreadable enrichment.toml are skipped
    # (best-effort — a broken sibling file must not block this story's own render).
    seq = int(story_dir.name[:2]) if story_dir.name[:2].isdigit() else 0
    earlier_keys: set[str] = set()
    for other in disk_slugs():
        if other == story_dir.name or not other[:2].isdigit() or int(other[:2]) >= seq:
            continue
        other_toml = STORIES_DIR / other / "enrichment.toml"
        if not other_toml.exists():
            continue
        try:
            other_words, other_phrases, _, _ = load_enrichment(other_toml)
        except SystemExit as exc:
            print(f"  warning: skipping {other} for new-words comparison — {exc}")
            continue
        earlier_keys.update(k for k, *_ in collect_story_vocab_rows(other_words, other_phrases))
    new_words = new_words_for_story(words, phrases, earlier_keys)

    region2 = find_body_region(html_text)
    body_tag, new_content_end = (region2[2], region2[1]) if region2 else (body_tag, content_end)
    html_text = upsert_new_words_block(html_text, body_tag, new_content_end, new_words)

    html_text = upsert_block(html_text, "style", "data-popup-invariants", POPUP_CSS_INV.strip(), "</head>")
    sent_payload = [{"tr": s.get("tr", ""), "note": s.get("note", "")} for s in sentences]
    popup_js = "window.__leeSentences = " + json.dumps(sent_payload, ensure_ascii=False) + ";\n" + POPUP_JS.strip()
    html_text = upsert_block(html_text, "script", "data-popup", popup_js, "</body>")

    out_path.write_text(html_text, encoding="utf-8")

    print(f"{out_path.relative_to(ROOT)} — enrichment applied")
    print(f"  sentences: {used}/{len(sentences)} paired" + ("" if used == len(sentences) else "  ⚠ MISMATCH"))
    if missed:
        seen = sorted(set(missed))
        more = "" if len(seen) <= 30 else f" (+{len(seen) - 30} more)"
        print(f"  missed words ({len(seen)}): {', '.join(seen[:30])}{more}")
    print(f"  new words: {len(new_words)}")


def bootstrap(story_dir: Path, force: bool) -> None:
    md_path = story_dir / "story.md"
    out_path = story_dir / "index.html"
    if not md_path.exists():
        sys.exit(f"error: {md_path} not found")
    if out_path.exists() and not force:
        sys.exit(f"error: {out_path} already exists; pass --force to overwrite")
    fm, body = parse_frontmatter(md_path.read_text(encoding="utf-8"))
    paragraphs = split_paragraphs(body)
    out_path.write_text(render_bootstrap(fm, paragraphs), encoding="utf-8")
    print(f"{out_path.relative_to(ROOT)} — bootstrap scaffold written ({len(paragraphs)} paragraphs)")
    print("  next: design the page freely, then re-run without --bootstrap to apply enrichment")


# ─── --refresh-all ──────────────────────────────────────────────────────────

def refresh_all() -> None:
    """Re-apply enrichment to every story that has story.md + enrichment.toml + index.html.
    Skip-and-report (never abort) on a per-story failure, then do one full index + vocab
    refresh. Safe/idempotent: detokenize + upsert_block make re-runs byte-identical."""
    ok, failed = [], []
    for slug in disk_slugs():
        story_dir = STORIES_DIR / slug
        if not (story_dir / "story.md").exists():
            continue
        if not (story_dir / "enrichment.toml").exists() or not (story_dir / "index.html").exists():
            print(f"{slug}: skipped (missing enrichment.toml or index.html)")
            continue
        try:
            apply_enrichment(story_dir)
            ok.append(slug)
        except SystemExit as exc:
            print(f"{slug}: FAILED — {exc}")
            failed.append(slug)

    count = refresh_index_full()
    print(f"index.html refreshed (full rebuild) — {count} entries")
    summary = f"--refresh-all: {len(ok)} ok, {len(failed)} failed"
    if failed:
        summary += f" ({', '.join(failed)})"
    print(summary)


# ─── --lint ──────────────────────────────────────────────────────────────────

def lint_story(slug: str) -> tuple[list[str], list[str], list[str]]:
    """Dry-run coverage check for one story against its own story.md / enrichment.toml.
    Returns (errors, warnings, infos) — plain ASCII strings, no slug prefix."""
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []
    story_dir = STORIES_DIR / slug
    md_path = story_dir / "story.md"
    toml_path = story_dir / "enrichment.toml"

    if not md_path.exists():
        errors.append("missing story.md")
    if not toml_path.exists():
        errors.append("missing enrichment.toml")
    if errors:
        return errors, warnings, infos

    fm, body = parse_frontmatter(md_path.read_text(encoding="utf-8"))
    missing_fm = [k for k in INDEX_FIELDS if not fm.get(k)]
    if missing_fm:
        errors.append(f"frontmatter missing field(s): {', '.join(missing_fm)}")

    raw_toml = toml_path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        hint = _toml_error_hint(raw_toml, exc)
        msg = f"TOML parse failed: {exc}"
        if hint:
            msg += " -- " + " ".join(hint.strip().splitlines())
        errors.append(msg)
        return errors, warnings, infos

    words = data.get("words", {}) or {}
    phrases = data.get("phrases", []) or []
    sentences = data.get("sentences", []) or []
    numbers = data.get("numbers", {}) or {}

    phrase_idx = build_phrase_index(words, phrases)
    full_text = "\n\n".join(split_paragraphs(body))

    s_used = [0]

    def take_sent():
        if s_used[0] < len(sentences):
            entry = sentences[s_used[0]]
            s_used[0] += 1
            return entry
        s_used[0] += 1
        return {}

    def cur_si():
        return s_used[0]

    used_keys: set[str] = set()
    stats: dict = {}
    _rendered, missed = tokenize_text_segment(
        full_text, words, phrase_idx, take_sent, cur_si, numbers, used_keys, stats)

    if missed:
        seen = sorted(set(missed))
        more = "" if len(seen) <= 30 else f" (+{len(seen) - 30} more)"
        errors.append(f"missed words ({len(seen)}): {', '.join(seen[:30])}{more}")

    # End marks come from the same tokenizer pass rendering uses (terminator runs
    # collapse to one mark; runs followed by a lowercase letter are pauses).
    term_count = stats.get("ends", 0)
    if term_count != len(sentences):
        errors.append(
            f"sentence count mismatch: {term_count} end mark(s) in body vs "
            f"{len(sentences)} [[sentences]] entries"
        )
    pause_count = stats.get("pauses", 0)
    if pause_count:
        infos.append(f"{pause_count} mid-sentence pause mark(s) (no [[sentences]] entry consumed)")

    orphan_words = sorted(f for f in words if f.lower() not in used_keys)
    if orphan_words:
        more = "" if len(orphan_words) <= 30 else f" (+{len(orphan_words) - 30} more)"
        warnings.append(f"orphan word entries ({len(orphan_words)}): {', '.join(orphan_words[:30])}{more}")

    orphan_phrases = sorted(p.get("form", "") for p in phrases if p.get("form", "").lower() not in used_keys)
    if orphan_phrases:
        warnings.append(f"orphan phrase entries ({len(orphan_phrases)}): {', '.join(orphan_phrases[:30])}")

    return errors, warnings, infos


def lint_cross_story(slugs: list[str]) -> list[str]:
    """Corpus-wide, informational-only warnings: same lemma tagged with different pos
    across stories, or the same surface form mapped to different lemmas (e.g. `la` as
    article vs. object pronoun is an expected, legitimate case of the latter)."""
    lemma_pos: dict[str, dict[str, set[str]]] = {}
    form_lemma: dict[str, dict[str, set[str]]] = {}
    for slug in slugs:
        toml_path = STORIES_DIR / slug / "enrichment.toml"
        if not toml_path.exists():
            continue
        try:
            words, _phrases, _sentences, _numbers = load_enrichment(toml_path)
        except SystemExit:
            continue
        for form, entry in words.items():
            lemma = (entry.get("lemma") or form).lower()
            pos = entry.get("pos", "")
            lemma_pos.setdefault(lemma, {}).setdefault(pos, set()).add(slug)
            form_lemma.setdefault(form.lower(), {}).setdefault(lemma, set()).add(slug)

    out: list[str] = []
    for lemma, by_pos in sorted(lemma_pos.items()):
        if len(by_pos) > 1:
            detail = "; ".join(f"{pos or '(none)'}: {','.join(sorted(s))}" for pos, s in sorted(by_pos.items()))
            out.append(f'lemma "{lemma}" has inconsistent pos across stories -- {detail}')
    for form, by_lemma in sorted(form_lemma.items()):
        if len(by_lemma) > 1:
            detail = "; ".join(f"{lemma}: {','.join(sorted(s))}" for lemma, s in sorted(by_lemma.items()))
            out.append(f'surface form "{form}" maps to different lemmas -- {detail}')
    return out


def lint_cmd(story_arg: str | None) -> bool:
    """Run --lint. Prints one line per story ("NN-slug: OK" or itemized findings), then a
    cross-story consistency block and a summary line. Returns True iff no errors (exit 0)."""
    if story_arg:
        story_dir = resolve_story_path(story_arg)
        target_slugs = [story_dir.name]
    else:
        target_slugs = disk_slugs()

    all_ok = True
    for slug in target_slugs:
        errors, warnings, infos = lint_story(slug)
        if errors:
            all_ok = False
            print(f"{slug}: FAIL")
        elif warnings:
            print(f"{slug}: OK (with warnings)")
        else:
            print(f"{slug}: OK")
        for e in errors:
            print(f"  error: {e}")
        for w in warnings:
            print(f"  warning: {w}")
        for note in infos:
            print(f"  info: {note}")

    cross = lint_cross_story(disk_slugs())
    if cross:
        print("cross-story consistency:")
        for w in cross:
            print(f"  warning: {w}")

    print(f"lint summary: {len(target_slugs)} story(ies) checked -- {'OK' if all_ok else 'ERRORS found'}")
    return all_ok


# ─── --atlas-check ───────────────────────────────────────────────────────────

_ATLAS_STOP_RE = re.compile(r"^## Per-story deltas", re.MULTILINE)
_ATLAS_ENTRY_RE = re.compile(r"^- \*\*([^*]+)\*\*\s*[—-]\s*(.*)$", re.MULTILINE)
_ATLAS_LINKED_REF_RE = re.compile(r"\[#(\d+)\]\(([^)]+)\)")
_ATLAS_PLAIN_REF_RE = re.compile(r"#(\d+)")


def atlas_check() -> None:
    """Warning-only (exit 0) cross-check of lore.md against stories/*/story.md:
    - an entity's bolded top-list entry appears in a story body without that
      story's #N in its ref list;
    - a markdown link in lore.md points at a story.md path that doesn't exist.

    Parses BOTH the plain `(#N)` ref form and the linked `[#N](path)` form (lore.md is
    being restructured to the latter independently of this feature), so the check works
    regardless of which lands first."""
    if not LORE_MD.exists():
        print("atlas-check: lore.md not found -- skipping")
        return

    text = LORE_MD.read_text(encoding="utf-8")
    stop = _ATLAS_STOP_RE.search(text)
    scope = text[:stop.start()] if stop else text

    story_bodies: dict[str, str] = {}
    for slug in disk_slugs():
        try:
            _fm, body = parse_frontmatter((STORIES_DIR / slug / "story.md").read_text(encoding="utf-8"))
        except OSError:
            continue
        story_bodies[slug] = body

    warn_count = 0
    dead_links: list[str] = []
    seen_paths: set[str] = set()

    for m in _ATLAS_ENTRY_RE.finditer(scope):
        name, rest = m.group(1).strip(), m.group(2)
        linked = list(_ATLAS_LINKED_REF_RE.finditer(rest))
        nums = {lm.group(1) for lm in linked}
        for lm in linked:
            path = lm.group(2)
            if path in seen_paths:
                continue
            seen_paths.add(path)
            if not (ROOT / path).exists():
                dead_links.append(f"[#{lm.group(1)}]({path})")
        rest_stripped = _ATLAS_LINKED_REF_RE.sub("", rest)
        nums |= set(_ATLAS_PLAIN_REF_RE.findall(rest_stripped))

        for slug, body in story_bodies.items():
            if name and name in body:
                n = str(int(slug[:2])) if slug[:2].isdigit() else slug[:2]
                if n not in nums:
                    print(f'warning: "{name}" appears in {slug} but #{n} is missing from its lore.md ref list')
                    warn_count += 1

    for dl in dead_links:
        print(f"warning: dead link in lore.md -- {dl} does not exist")
        warn_count += 1

    print(f"atlas-check: {warn_count} warning(s)")


def main() -> None:
    ap = argparse.ArgumentParser(description="lee-espanol render — apply enrichment to a designer-authored HTML")
    ap.add_argument("story", nargs="?", help="path to stories/NN-slug/ (auto-picks newest if omitted)")
    ap.add_argument("--bootstrap", action="store_true", help="write a minimal design scaffold (use when starting a new story)")
    ap.add_argument("--force", action="store_true", help="with --bootstrap: overwrite existing index.html")
    ap.add_argument("--index-only", action="store_true", help="only refresh the project-wide index.html")
    ap.add_argument("--refresh-all", action="store_true",
                     help="re-apply enrichment to every story with story.md+enrichment.toml+index.html, "
                          "skip-and-report per-story failures, then a full index+vocab refresh")
    ap.add_argument("--lint", action="store_true",
                     help="validate story.md/enrichment.toml coverage (optional story arg = one story, "
                          "default = all); prints findings, exits 1 on errors")
    ap.add_argument("--atlas-check", action="store_true",
                     help="cross-check lore.md entity refs against stories/*/story.md (warning-only)")
    args = ap.parse_args()

    if args.atlas_check:
        atlas_check()
        return

    if args.lint:
        sys.exit(0 if lint_cmd(args.story) else 1)

    if args.refresh_all:
        refresh_all()
        return

    if args.index_only:
        count = refresh_index_full()
        print(f"index.html refreshed (full rebuild) — {count} entries")
        return

    story_dir = resolve_story_path(args.story)

    if args.bootstrap:
        bootstrap(story_dir, force=args.force)
    else:
        apply_enrichment(story_dir)

    count = refresh_index_incremental(story_dir.name)
    print(f"index.html refreshed (incremental: {story_dir.name}) — {count} entries")


if __name__ == "__main__":
    main()
