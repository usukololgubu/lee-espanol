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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORIES_DIR = ROOT / "stories"
INDEX_HTML = ROOT / "index.html"
INDEX_CACHE = ROOT / ".ai" / "stories-index.json"
ARCHETYPES_JSONL = ROOT / ".ai" / "archetypes.jsonl"
INDEX_FIELDS = ("title", "protagonist", "setting", "date_generated", "length_words")
DEFAULT_PALETTE = {"bg": "#f5f3ec", "ink": "#1f1d18", "accent": "#8a877e"}

SP_LETTERS = "A-Za-zÀ-ÖØ-öø-ÿ"
WORD_RE = re.compile(rf"[{SP_LETTERS}]+")
SENT_RE = re.compile(r"[.?!]")
WORDISH_RE = re.compile(rf"[{SP_LETTERS}0-9]")


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


def load_enrichment(path: Path) -> tuple[dict, list, list]:
    text = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        hint = _toml_error_hint(text, exc)
        sys.exit(f"error: {path} — TOML parse failed: {exc}\n{hint}" if hint else f"error: {path} — TOML parse failed: {exc}")
    return data.get("words", {}), data.get("phrases", []) or [], data.get("sentences", []) or []


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
) -> tuple[str, list[str]]:
    """Tokenize a plain-text fragment (no HTML inside)."""
    text = unescape_stable(text)
    out: list[str] = []
    missed: list[str] = []
    i = 0
    while i < len(text):
        phrase_hit = next(((f, e) for f, e in phrase_idx if matches_phrase_at(text, i, f)), None)
        if phrase_hit:
            form, entry = phrase_hit
            out.append(word_span(text[i:i + len(form)], entry, cur_si()))
            i += len(form)
            continue
        wm = WORD_RE.match(text, i)
        if wm:
            w = wm.group()
            entry = words.get(w.lower())
            if entry:
                out.append(word_span(w, entry, cur_si()))
            else:
                out.append(esc_text(w))
                missed.append(w)
            i = wm.end()
            continue
        ch = text[i]
        if SENT_RE.match(ch):
            si = cur_si()
            out.append(sentence_span(ch, take_sent(), si))
            i += 1
            continue
        out.append(esc_text(ch))
        i += 1
    return "".join(out), missed


def walk_html_body(
    content: str,
    words: dict,
    phrase_idx: list[tuple[str, dict]],
    sentences: list,
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
            toked, miss = tokenize_text_segment(seg, words, phrase_idx, take_sent, cur_si)
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
}\
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
    meta_parts = [fm.get("protagonist", ""), fm.get("setting", "")]
    meta = " · ".join(p for p in meta_parts if p)
    p = palette or DEFAULT_PALETTE
    style = (
        f'--card-bg:{p["bg"]};'
        f'--card-ink:{p["ink"]};'
        f'--card-accent:{p["accent"]}'
    )
    return (
        f'    <a class="entry" href="stories/{slug}/index.html" style="{html.escape(style, quote=True)}">\n'
        '      <div class="row1">\n'
        f'        <span class="num">{html.escape(num)}</span>\n'
        f'        <span class="date">{html.escape(fmt_date(fm.get("date_generated", "")))}</span>\n'
        '      </div>\n'
        f'      <div class="e-title">{html.escape(title)}</div>\n'
        f'      <div class="meta">{html.escape(meta)}</div>\n'
        f'      <div class="words">{html.escape(str(fm.get("length_words", "")))} palabras</div>\n'
        '    </a>'
    )


def ordered_slugs(slugs: list[str]) -> list[str]:
    """Newest-first overall, but within each 2-slot row place the older slug on the
    left and the newer on the right. So the visual grid reads (per row, top→bottom):
       11 | 12
       09 | 10
       …
       01 | 02
    For odd counts the lone oldest slug ends up in the final row's left cell.
    """
    desc = sorted(slugs, reverse=True)
    out: list[str] = []
    for i in range(0, len(desc), 2):
        pair = desc[i:i + 2]
        out.extend(reversed(pair))
    return out


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
    return write_index_html(cache)


def refresh_index_full() -> int:
    """Force a full rebuild from disk; used by --index-only."""
    cache = build_cache_from_disk()
    save_index_cache(cache)
    return write_index_html(cache)


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
    words, phrases, sentences = load_enrichment(toml_path)
    phrase_idx = build_phrase_index(words, phrases)

    html_text = out_path.read_text(encoding="utf-8")
    region = find_body_region(html_text)
    if region is None:
        sys.exit(
            f"error: {out_path} has no element with [data-story-body]. "
            f"Add data-story-body to the element wrapping your <p> tags."
        )
    content_start, content_end, _tag = region
    body_region = html_text[content_start:content_end]
    body_region = detokenize(body_region)
    new_body, missed, used = walk_html_body(body_region, words, phrase_idx, sentences)

    html_text = html_text[:content_start] + new_body + html_text[content_end:]
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


def main() -> None:
    ap = argparse.ArgumentParser(description="lee-espanol render — apply enrichment to a designer-authored HTML")
    ap.add_argument("story", nargs="?", help="path to stories/NN-slug/ (auto-picks newest if omitted)")
    ap.add_argument("--bootstrap", action="store_true", help="write a minimal design scaffold (use when starting a new story)")
    ap.add_argument("--force", action="store_true", help="with --bootstrap: overwrite existing index.html")
    ap.add_argument("--index-only", action="store_true", help="only refresh the project-wide index.html")
    args = ap.parse_args()

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
