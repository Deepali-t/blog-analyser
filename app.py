"""
SEO & Content Analyzer — Streamlit App
Run locally:  streamlit run app.py
100 % local — no external API calls.
"""

from __future__ import annotations

import re
from collections import Counter
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

import streamlit as st
import textstat
from streamlit_quill import st_quill

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS: Dict[str, Union[bool, int, float]] = {
    "FIRST_PARAGRAPH_KEYWORD":  True,
    "MIN_KEYWORD_DENSITY":      1.5,
    "MAX_KEYWORD_DENSITY":      3.5,
    "MIN_WORD_COUNT":           1000,
    "TITLE_KEYWORD":            True,
    "META_KEYWORD":             True,
    "TITLE_LENGTH_MAX":         60,
    "META_LENGTH_MAX":          160,
    "MIN_READABILITY_SCORE":    50.0,
    "MAX_PARAGRAPH_WORDS":      150,
    "HEADING_KEYWORD":          True,
}

# Maps each guideline key → (metrics_dict_key, operator)
# operator: "bool" | "min" | "max"
RULE_METRIC_MAP: Dict[str, Tuple[str, str]] = {
    # ── On-page SEO ──────────────────────────────────────────────────────────
    "TITLE_KEYWORD":                ("title_has_kw",                "bool"),
    "TITLE_KEYWORD_H1":             ("kw_in_h1",                    "bool"),
    "META_TITLE_START_KEYWORD":     ("title_starts_with_kw",        "bool"),
    "TITLE_LENGTH_MAX":             ("title_len",                   "max"),
    "META_KEYWORD":                 ("meta_has_kw",                 "bool"),
    "META_LENGTH_MAX":              ("meta_len",                    "max"),
    # ── Content placement ─────────────────────────────────────────────────────
    "FIRST_PARAGRAPH_KEYWORD":      ("kw_in_first_para",            "bool"),
    "FIRST_150_WORDS_KEYWORD_COUNT":("first_150_kw_count",          "min"),
    "HEADING_KEYWORD":              ("kw_in_headings",              "bool"),
    "MIN_H2_H3_KEYWORD_COUNT":      ("h2_h3_kw_count",             "min"),
    "KEYWORD_DISTRIBUTION_INTERVAL":("keyword_dist_max_gap",        "max"),
    # ── Density & readability ─────────────────────────────────────────────────
    "MIN_KEYWORD_DENSITY":          ("keyword_density",             "min"),
    "MAX_KEYWORD_DENSITY":          ("keyword_density",             "max"),
    "MIN_SECONDARY_KEYWORD_DENSITY":("secondary_max_density",       "min"),
    "MIN_READABILITY_SCORE":        ("readability_score",           "min"),
    "MIN_TRANSITION_WORDS_PERCENT": ("transition_words_pct",        "min"),
    # ── Structure ────────────────────────────────────────────────────────────
    "MIN_WORD_COUNT":               ("word_count",                  "min"),
    "MIN_PARAGRAPH_WORDS":          ("min_para_words",              "min"),
    "MAX_PARAGRAPH_WORDS":          ("max_para_words",              "max"),
    "MIN_HEADING_COUNT":            ("heading_count",               "min"),
    "MAX_HEADING_COUNT":            ("heading_count",               "max"),
    # ── Links ────────────────────────────────────────────────────────────────
    "INTERNAL_LINKS_SITEMAP":       ("has_internal_links",          "bool"),
    "MIN_INTERNAL_LINKS":           ("internal_link_count",         "min"),
    "MAX_INTERNAL_LINKS":           ("internal_link_count",         "max"),
    "MAX_EXTERNAL_LINKS":           ("external_link_count",         "max"),
    "DUPLICATE_INTERNAL_LINKS":     ("duplicate_internal_count",    "max"),
    "EXACT_MATCH_ANCHOR":           ("internal_anchor_has_kw",      "bool"),
    # ── Content richness ─────────────────────────────────────────────────────
    "MIN_STATS_COUNT":              ("stats_count",                 "min"),
    "FAQ_COUNT":                    ("faq_count",                   "exact"),
    "FAQ_ANSWER_WORD_COUNT_MIN":    ("faq_min_answer_words",        "min"),
    "FAQ_ANSWER_WORD_COUNT_MAX":    ("faq_max_answer_words",        "max"),
    "CLEAR_CTA_END":                ("has_cta_end",                 "bool"),
}

RULE_LABELS: Dict[str, str] = {
    "TITLE_KEYWORD":                "Keyword in SEO Title",
    "TITLE_KEYWORD_H1":             "Keyword in H1 Heading",
    "META_TITLE_START_KEYWORD":     "Keyword Starts SEO Title",
    "TITLE_LENGTH_MAX":             "SEO Title Max Length",
    "META_KEYWORD":                 "Keyword in Meta Description",
    "META_LENGTH_MAX":              "Meta Description Max Length",
    "FIRST_PARAGRAPH_KEYWORD":      "Keyword in First Paragraph",
    "FIRST_150_WORDS_KEYWORD_COUNT":"Keyword Count — First 180 Words",
    "HEADING_KEYWORD":              "Keyword in Any Heading",
    "MIN_H2_H3_KEYWORD_COUNT":      "Keyword in H2 / H3 Headings",
    "KEYWORD_DISTRIBUTION_INTERVAL":"Keyword Distribution (max word gap)",
    "MIN_KEYWORD_DENSITY":          "Minimum Keyword Density",
    "MAX_KEYWORD_DENSITY":          "Maximum Keyword Density",
    "MIN_SECONDARY_KEYWORD_DENSITY":"Min Secondary Keyword Density",
    "MIN_READABILITY_SCORE":        "Minimum Flesch Reading Ease",
    "MIN_TRANSITION_WORDS_PERCENT": "Min Transition Words %",
    "MIN_WORD_COUNT":               "Minimum Word Count",
    "MAX_PARAGRAPH_WORDS":          "Max Words Per Paragraph",
    "MIN_HEADING_COUNT":            "Minimum Heading Count",
    "MAX_HEADING_COUNT":            "Maximum Heading Count",
    "INTERNAL_LINKS_SITEMAP":       "Internal Links Present",
    "MIN_INTERNAL_LINKS":           "Internal Link Count",
    "MAX_INTERNAL_LINKS":           "Maximum Internal Links",
    "MAX_EXTERNAL_LINKS":           "Maximum External Links",
    "DUPLICATE_INTERNAL_LINKS":     "Duplicate Internal Links",
    "EXACT_MATCH_ANCHOR":           "Internal Links Use Keyword as Anchor Text",
    "MIN_STATS_COUNT":              "Minimum Statistics / Data Points",
    "FAQ_COUNT":                    "FAQ Count",
    "FAQ_ANSWER_WORD_COUNT_MIN":    "FAQ Answer Min Word Count",
    "FAQ_ANSWER_WORD_COUNT_MAX":    "FAQ Answer Max Word Count",
    "CLEAR_CTA_END":                "Clear CTA at End of Post",
}

# ─────────────────────────────────────────────────────────────────────────────
# Embedded Guidelines (22 rules — guideline upload disabled)
# ─────────────────────────────────────────────────────────────────────────────

EMBEDDED_GUIDELINES: Dict[str, Union[bool, int, float]] = {
    "TITLE_KEYWORD_H1":                True,
    "FIRST_150_WORDS_KEYWORD_COUNT":   2,
    "FIRST_PARAGRAPH_KEYWORD":         True,
    "MIN_H2_H3_KEYWORD_COUNT":         2,
    "META_TITLE_START_KEYWORD":        True,
    "TITLE_LENGTH_MAX":                60,
    "META_KEYWORD":                    True,
    "META_LENGTH_MAX":                 140,
    "MIN_INTERNAL_LINKS":              3,
    "MIN_SECONDARY_KEYWORD_DENSITY":   0.3,
    "DUPLICATE_INTERNAL_LINKS":        False,
    "MIN_READABILITY_SCORE":           60.0,
    "MAX_PARAGRAPH_WORDS":             53,
    "FAQ_COUNT":                       5,
    "FAQ_ANSWER_WORD_COUNT_MIN":       15,
    "FAQ_ANSWER_WORD_COUNT_MAX":       80,
    "KEYWORD_DISTRIBUTION_INTERVAL":   200,
    "CLEAR_CTA_END":                   True,
    "MIN_STATS_COUNT":                 3,
    "MIN_TRANSITION_WORDS_PERCENT":    15.0,
    "MAX_EXTERNAL_LINKS":              3,
}

GUIDELINE_DESCRIPTIONS: Dict[str, str] = {
    "TITLE_KEYWORD_H1":                "Primary keyword must be present in the H1 tag / Title of the page.",
    "FIRST_150_WORDS_KEYWORD_COUNT":   "Use the primary keyword at least 2 times within the first 180 words.",
    "FIRST_PARAGRAPH_KEYWORD":         "The primary keyword must appear in the first paragraph of the blog.",
    "MIN_H2_H3_KEYWORD_COUNT":         "The primary keyword must be placed in H2 or H3 subheadings at least 2 times.",
    "META_TITLE_START_KEYWORD":        "The primary keyword must be placed right at the start of the meta title.",
    "TITLE_LENGTH_MAX":                "The meta title must not exceed 60 characters in length.",
    "META_KEYWORD":                    "The primary keyword must be present in the meta description.",
    "META_LENGTH_MAX":                 "The meta description must not exceed 140 characters in length.",
    "MIN_INTERNAL_LINKS":              "Content must contain at least 3 internal links to related blogs and landing pages.",
    "MIN_SECONDARY_KEYWORD_DENSITY":   "At least one secondary keyword must have a density between 0.3% and 0.4%.",
    "DUPLICATE_INTERNAL_LINKS":        "Do not link to the exact same internal URL more than once in the article.",
    "MIN_READABILITY_SCORE":           "Ensure content is easy to read (Target standard Flesch Reading Ease score of 60+).",
    "MAX_PARAGRAPH_WORDS":             "Paragraph size must be a maximum of 3.5 lines (3.5 lines × 15 words = 53 words max).",
    "FAQ_COUNT":                       "Exactly 5 FAQs must be included on the page.",
    "FAQ_ANSWER_WORD_COUNT_MIN":       "Each FAQ answer must be a minimum of 15 words.",
    "FAQ_ANSWER_WORD_COUNT_MAX":       "Each FAQ answer must be a maximum of 35 words.",
    "KEYWORD_DISTRIBUTION_INTERVAL":   "The primary keyword must appear evenly, at least once every 200 words.",
    "CLEAR_CTA_END":                   "A clear Call-to-Action (CTA) must be present at the very end of the blog post.",
    "MIN_STATS_COUNT":                 "At least 3 statistical data points from credible research studies must be cited.",
    "MIN_TRANSITION_WORDS_PERCENT":    "Transition words must make up a minimum of 15% of the content.",
    "MAX_EXTERNAL_LINKS":              "Do not place more than 3 external links throughout the content.",
}

# ── Regex patterns ────────────────────────────────────────────────────────────

_META_STANDALONE_RE = re.compile(
    r"^(tl\s*;?\s*dr|references?|bibliography|sources?)\s*$",
    re.IGNORECASE,
)
_META_COLON_RE = re.compile(
    r"^(meta\s+(?:description|title)|seo\s+title|title\s+tag|focus\s+keyword"
    r"|word\s+count|reading\s+time|published|author"
    r"|keywords?\s*(used)?|tags?|slug|excerpt|category|date)"
    r"[^.\n]*[:\-]",
    re.IGNORECASE,
)

_URL_RE         = re.compile(r"(?:https?://|www\.)[^\s\)\]>\"',]+", re.IGNORECASE)
_ANCHOR_LINK_RE = re.compile(r"«([^|»]+)\|([^»]+)»")
_STAT_RE        = re.compile(
    r"\b\d+(?:\.\d+)?\s*%"
    r"|\b\d+\s*x\b"
    r"|\b\d+\s+(?:in|out\s+of)\s+\d+"
    r"|\$\s*\d+"
    r"|\b\d{1,3}(?:,\d{3})+"
    r"|\b\d+\s*(?:million|billion|thousand|mn|bn)\b"
    r"|\b\d+\s*(?:percent|times|fold)\b",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(
    r"^(?:q\s*\d*[:.]\s*|"
    r"(?:what|which|how|why|when|where|who|can|do|does|is|are|will|should)\b)",
    re.IGNORECASE,
)
_CTA_RE = re.compile(
    r"\b(contact\s+us|get\s+started|sign\s+up|learn\s+more"
    r"|try\s+(?:it\s+)?free|schedule\s+a\s+(?:demo|call)"
    r"|book\s+a\s+demo|request\s+a\s+(?:demo|quote)"
    r"|click\s+here|reach\s+out|talk\s+to\s+us|get\s+in\s+touch"
    r"|start\s+now|try\s+now|explore\s+now|find\s+out\s+more"
    r"|connect\s+with\s+us|see\s+how|discover\s+how|check\s+it\s+out"
    r"|get\s+a\s+(?:free\s+)?(?:demo|quote|consultation))\b",
    re.IGNORECASE,
)

_TRANSITION_WORDS = frozenset([
    "additionally", "also", "furthermore", "moreover", "in addition", "besides",
    "as well as", "however", "but", "nevertheless", "on the other hand",
    "although", "despite", "in contrast", "yet", "still", "conversely",
    "whereas", "while", "even though", "on the contrary", "alternatively",
    "therefore", "thus", "consequently", "as a result", "hence", "so",
    "because", "since", "due to", "given that", "for example", "for instance",
    "such as", "specifically", "namely", "to illustrate", "in particular",
    "including", "especially", "first", "second", "third", "fourth", "fifth",
    "finally", "then", "next", "subsequently", "previously", "initially",
    "lastly", "to begin with", "at the same time", "meanwhile", "in conclusion",
    "to summarize", "overall", "in summary", "to sum up", "in short",
    "to conclude", "all in all", "in brief", "in other words", "indeed",
    "certainly", "in fact", "of course", "clearly", "above all",
    "most importantly", "undoubtedly", "similarly", "likewise",
    "in the same way", "just as", "compared to", "equally",
    "instead", "rather", "otherwise", "regardless", "after all",
    "even so", "that is", "in turn",
])

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _is_list_or_table_block(text: str) -> bool:
    """Return True for bullet lists and comparison-table blocks.
    Used to exclude them from paragraph word-count stats and Flesch calculation."""
    s = text.strip()
    if re.match(r"^[●•\-\*\+]\s", s):
        return True
    lines = [l.strip() for l in s.split("\n") if l.strip()]
    if len(lines) >= 3:
        avg_words = sum(len(l.split()) for l in lines) / len(lines)
        if avg_words < 7:
            return True
    yn_count = len(re.findall(r"\b(Yes|No|Limited)\b", s, re.IGNORECASE))
    if yn_count >= 4:
        return True
    return False


def _prose_text(text: str) -> str:
    """Return prose-only text for Flesch readability (excludes headings, lists, tables)."""
    t = _ANCHOR_LINK_RE.sub(r"\1", text)
    t = _URL_RE.sub("", t)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", t) if b.strip()]
    prose = [
        b for b in blocks
        if not b.lstrip().startswith("#")
        and not _is_list_or_table_block(b)
        and len(b.split()) >= 20
    ]
    return " ".join(prose) if prose else t


def _text_for_gap(text: str) -> str:
    """Return URL/list-stripped text that KEEPS heading words for keyword gap calculation.
    Heading keyword mentions should count against the gap so we don't inflate it."""
    t = _ANCHOR_LINK_RE.sub(r"\1", text)
    t = _URL_RE.sub("", t)
    blocks = [b.strip() for b in re.split(r"\n\s*\n", t) if b.strip()]
    kept = []
    for b in blocks:
        if _is_list_or_table_block(b):
            continue
        kept.append(re.sub(r"^#+\s*", "", b))  # strip # prefix, keep heading words
    return " ".join(kept) if kept else t


# ─────────────────────────────────────────────────────────────────────────────
# Document Text Extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(data))
    lines: List[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        if "Heading" in style_name:
            m = re.search(r"\d", style_name)
            level = int(m.group()) if m else 1
            text = f"{'#' * level} {text}"

        # Embed «anchor|url» markers — iter() is recursive, finds nested hyperlinks
        try:
            for hl in para._p.iter(f"{{{_W_NS}}}hyperlink"):
                r_id = hl.get(f"{{{_R_NS}}}id")
                if r_id and r_id in para.part.rels:
                    url = para.part.rels[r_id].target_ref
                    if url.startswith("http"):
                        anchor = "".join(
                            node.text for node in hl.iter(f"{{{_W_NS}}}t") if node.text
                        ).strip() or url
                        text += f" «{anchor}|{url}»"
        except Exception:
            pass

        lines.append(text)
    return "\n\n".join(lines)


def _mark_pdf_headings(text: str) -> str:
    """
    Heuristically prefix heading-like lines with '#' in PDF-extracted text.
    Headings are short (1-12 words), no sentence-ending punctuation, start with
    a capital or digit, not a bullet, and either preceded by a blank line or
    followed by a distinctly longer body line.
    """
    lines = text.split("\n")
    out: List[str] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            out.append(line)
            continue

        words = s.split()
        is_bullet   = bool(re.match(r"^[●•\-\*\+]\s", s))
        is_num_list = bool(re.match(r"^\d+\)\s", s))
        looks_like_heading = (
            1 <= len(words) <= 12
            and not re.search(r"[.!,]$", s)
            and (s[0].isupper() or s[0].isdigit())
            and not is_bullet
            and not is_num_list
        )
        if looks_like_heading:
            prev_empty    = i == 0 or not lines[i - 1].strip()
            next_nonempty = next((l.strip() for l in lines[i + 1:i + 4] if l.strip()), "")
            next_longer   = len(next_nonempty.split()) > len(words) if next_nonempty else False
            # Treat as heading when preceded by a longer body paragraph (original lines)
            prev_nonempty_orig = next((lines[j].strip() for j in range(i - 1, -1, -1)
                                       if lines[j].strip()), "")
            prev_longer = len(prev_nonempty_orig.split()) > len(words) if prev_nonempty_orig else False
            # Chain: if the last processed non-empty line was already a heading, mark this too
            # (handles PDF page-header lines that steal the i==0 slot before the real title)
            last_out = next((l for l in reversed(out) if l.strip()), "")
            prev_was_heading = last_out.lstrip().startswith("#")
            if prev_empty or next_longer or prev_longer or prev_was_heading:
                out.append(f"# {s}")
                continue

        out.append(line)
    return "\n".join(out)


def parse_html_content(html: str) -> str:
    """
    Convert pasted HTML (from CMS, Google Docs, rich editor) into our internal
    plain-text format:
      • <h1>…</h1>  →  # heading
      • <h2>…</h2>  →  ## heading
      • <h3>…</h3>  →  ### heading
      • <a href="url">anchor</a>  →  anchor «anchor|url»
      • <p> / <div> / <li>  →  paragraph block (double-newline separated)
      • <strong>/<b>/<em>/<i>  →  plain text (bold/italic stripped for analysis)
    """
    from bs4 import BeautifulSoup, NavigableString, Tag

    soup = BeautifulSoup(html, "html.parser")
    blocks: List[str] = []

    def _node_text(node) -> str:
        """Recursively render a node to text, preserving anchor markers."""
        if isinstance(node, NavigableString):
            return str(node)
        if not isinstance(node, Tag):
            return ""
        if node.name == "a":
            href = (node.get("href") or "").strip()
            anchor = node.get_text(" ", strip=True)
            if href.startswith("http") and anchor:
                return f"{anchor} «{anchor}|{href}»"
            return anchor
        if node.name in ("br",):
            return "\n"
        return "".join(_node_text(c) for c in node.children)

    for elem in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "div"],
        recursive=True,
    ):
        # Skip divs that just contain other block elements (avoid duplication)
        if elem.name == "div" and elem.find(["h1","h2","h3","h4","h5","h6","p","li"]):
            continue

        tag = elem.name
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text  = elem.get_text(" ", strip=True)
            if text:
                blocks.append(f"{'#' * level} {text}")
        else:
            text = "".join(_node_text(c) for c in elem.children).strip()
            if text:
                blocks.append(text)

    result = "\n\n".join(b for b in blocks if b.strip())
    # If BeautifulSoup found no block elements, fall back to plain-text heuristic
    if not result.strip():
        result = _mark_pdf_headings(soup.get_text("\n"))
    return result


def _extract_pdf(data: bytes) -> str:
    raw = ""
    annotation_urls: List[str] = []
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            pages_text: List[str] = []
            for p in pdf.pages:
                pages_text.append(p.extract_text() or "")
                # Pull hyperlink URLs from PDF annotations (invisible in plain text)
                try:
                    for link in p.hyperlinks:
                        uri = link.get("uri", "")
                        if uri.startswith("http"):
                            annotation_urls.append(uri)
                except Exception:
                    pass
            raw = "\n\n".join(pages_text)
    except ImportError:
        pass

    if not raw:
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            raw = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            try:
                for page in reader.pages:
                    for annot in page.get("/Annots", []):
                        obj = annot.get_object() if hasattr(annot, "get_object") else annot
                        if isinstance(obj, dict):
                            uri = obj.get("/A", {}).get("/URI", "")
                            if uri and uri.startswith("http"):
                                annotation_urls.append(uri)
            except Exception:
                pass
        except ImportError:
            raise RuntimeError("No PDF library found. Run: pip install pdfplumber")

    marked = _mark_pdf_headings(raw)
    if annotation_urls:
        marked += "\n\n" + " ".join(annotation_urls)
    return marked


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    if name.endswith(".docx"):
        return _extract_docx(data)
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    raise ValueError(f"Unsupported file type: {uploaded_file.name!r}. Use .docx or .pdf.")


# ─────────────────────────────────────────────────────────────────────────────
# Guideline Parsing  (fully dynamic — no key filtering)
# ─────────────────────────────────────────────────────────────────────────────

def _infer_value(raw: str) -> Union[bool, int, float, str]:
    s = raw.split("|")[0].strip().rstrip(".,;")
    if s.lower() in ("true", "yes"):
        return True
    if s.lower() in ("false", "no"):
        return False
    m = re.match(r"^(\d+\.?\d*)\s*%$", s)
    if m:
        return float(m.group(1))
    if re.match(r"^\d+\.\d+$", s):
        return float(s)
    if re.match(r"^\d+$", s):
        return int(s)
    return s


def parse_guidelines(text: str) -> dict:
    result: dict = {}
    pattern = re.compile(r"\[([A-Z][A-Z0-9_]+)\]\s*[=:]\s*([^\n\r]+)", re.IGNORECASE)
    for m in pattern.finditer(text):
        result[m.group(1).upper()] = _infer_value(m.group(2))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Text Pre-processing
# ─────────────────────────────────────────────────────────────────────────────

def split_blocks(text: str) -> List[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def is_heading_block(block: str) -> bool:
    return block.lstrip().startswith("#")


def strip_metadata_blocks(text: str) -> str:
    clean: List[str] = []
    for block in split_blocks(text):
        first = re.sub(r"^#+\s*", "", block.split("\n")[0]).strip()
        if _META_STANDALONE_RE.match(first):
            continue
        if _META_COLON_RE.match(first):
            continue
        if re.match(r"^\[?[A-Z][A-Z0-9_\s]+\]?\s*[=:]", first):
            continue
        clean.append(block)
    return "\n\n".join(clean)


# ─────────────────────────────────────────────────────────────────────────────
# Core Analysis
# ─────────────────────────────────────────────────────────────────────────────

def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def contains_keyword(snippet: str, keyword: str) -> bool:
    if not keyword.strip():
        return False
    # Normalise whitespace — PDFs sometimes use non-breaking or multiple spaces
    norm_s = re.sub(r"[\s\xa0]+", " ", snippet).strip()
    norm_k = re.sub(r"[\s\xa0]+", " ", keyword).strip()
    return bool(re.search(re.escape(norm_k), norm_s, re.IGNORECASE))


def keyword_density(text: str, keyword: str) -> Tuple[int, float]:
    if not keyword.strip():
        return 0, 0.0
    total = count_words(text)
    if total == 0:
        return 0, 0.0
    hits = len(re.findall(re.escape(keyword), text, re.IGNORECASE))
    density = round((hits * len(keyword.split()) / total) * 100, 2)
    return hits, density


def secondary_keyword_analysis(text: str, raw: str) -> List[dict]:
    if not raw.strip():
        return []
    results = []
    for kw in [k.strip() for k in raw.split(",") if k.strip()]:
        hits, density = keyword_density(text, kw)
        results.append({"Keyword / Phrase": kw, "Occurrences": hits, "Density %": density})
    return results


def readability_score(text: str) -> float:
    return round(textstat.flesch_reading_ease(text), 1)


def structural_analysis(clean_text: str, keyword: str) -> dict:
    blocks   = split_blocks(clean_text)
    headings = [b for b in blocks if is_heading_block(b)]
    body     = [b for b in blocks if not is_heading_block(b)]
    first    = body[0] if body else ""

    # H1: explicit single-# headings (DOCX) or first heading block (PDF)
    explicit_h1 = [h for h in headings if re.match(r"^#(?!#)", h.lstrip())]
    h1s = explicit_h1 if explicit_h1 else headings[:1]

    # H2/H3: explicit ## / ### (DOCX) or all headings after the first (PDF)
    explicit_sub = [h for h in headings if re.match(r"^#{2,}", h.lstrip())]
    h2_h3 = explicit_sub if explicit_sub else headings[1:]
    h2_h3_kw_count = sum(1 for h in h2_h3 if contains_keyword(h, keyword))

    para_lengths = [(p, len(p.split())) for p in body]
    # Exclude list/table blocks and very short items (< 8 words) from min/max stats
    prose_paras = [(p, w) for p, w in para_lengths if w >= 8 and not _is_list_or_table_block(p)]
    use_paras   = prose_paras if prose_paras else para_lengths
    max_pw = max((w for _, w in use_paras), default=0)
    min_pw = min((w for _, w in use_paras if w > 0), default=0)

    all_body_words  = " ".join(body).split()
    first_180_text  = " ".join(all_body_words[:180])
    first_180_kw    = (
        len(re.findall(re.escape(keyword), first_180_text, re.IGNORECASE))
        if keyword.strip() else 0
    )

    return {
        "first_para":         first,
        "kw_in_first_para":   contains_keyword(first, keyword),
        "kw_in_headings":     any(contains_keyword(h, keyword) for h in headings),
        "kw_in_h1":           any(contains_keyword(h, keyword) for h in h1s),
        "h2_h3_kw_count":     h2_h3_kw_count,
        "heading_count":      len(headings),
        "body_para_count":    len(body),
        "para_lengths":       para_lengths,
        "max_para_words":     max_pw,
        "min_para_words":     min_pw,
        "first_150_kw_count": first_180_kw,
    }


def analyze_links(text: str, internal_domain: str, focus_keyword: str = "") -> dict:
    domain = internal_domain.strip().lower()

    structured: List[Tuple[str, str]] = [
        (m.group(1), m.group(2)) for m in _ANCHOR_LINK_RE.finditer(text)
    ]
    plain_text = _ANCHOR_LINK_RE.sub("", text)

    # Bare URLs from plain text (after removing «anchor|url» markers)
    bare_urls       = _URL_RE.findall(plain_text)
    structured_urls = [url for _, url in structured]

    # Deduplicate: a bare URL that already appears as a structured «anchor|url»
    # marker is the same link (PDF annotation blob re-lists inline links).
    structured_set = {u.lower().rstrip("/") for u in structured_urls}
    bare_unique     = [u for u in bare_urls if u.lower().rstrip("/") not in structured_set]

    all_urls = bare_unique + structured_urls

    internal = [u for u in all_urls if domain and domain in u.lower()]
    external = [u for u in all_urls if not domain or domain not in u.lower()]

    # Duplicates = same internal URL linked more than once in the body
    dup_internal = sum(
        1 for c in Counter(u.lower().rstrip("/") for u in internal).values() if c > 1
    )

    internal_anchors = [a for a, u in structured if domain and domain in u.lower()]
    anchor_has_kw    = (
        any(contains_keyword(a, focus_keyword) for a in internal_anchors)
        if focus_keyword.strip() else False
    )

    return {
        "internal_link_count":      len(internal),
        "external_link_count":      len(external),
        "duplicate_internal_count": dup_internal,
        "internal_anchor_has_kw":   anchor_has_kw,
        "internal_urls":            internal,
        "external_urls":            external,
        "internal_anchors":         internal_anchors,
    }


def count_statistics(text: str) -> int:
    return sum(1 for s in re.split(r"(?<=[.!?])\s+", text) if _STAT_RE.search(s))


def analyze_faqs(blocks: List[str]) -> dict:
    # Flatten ALL lines first (avoids block-boundary issues when FAQ heading
    # and first question are in the same block with no blank line between them)
    all_lines: List[str] = []
    for block in blocks:
        for ln in block.split("\n"):
            cleaned = re.sub(r"^[#*_`]+\s*", "", ln).strip()
            if cleaned:
                all_lines.append(cleaned)

    # Find the "FAQs" / "FAQ" section heading at line level
    faq_line_idx = -1
    for idx, ln in enumerate(all_lines):
        if re.match(r"^faqs?\s*$", ln, re.IGNORECASE):
            faq_line_idx = idx
            break

    # Scan only from the line after the FAQ heading (or full doc if none found)
    scan_lines = all_lines[faq_line_idx + 1:] if faq_line_idx >= 0 else all_lines

    # Sentinel: stop collecting FAQ content if we hit metadata-like lines
    _META_STOP_RE = re.compile(
        r"^(meta\s+(?:title|description)|seo\s+title|references?|bibliography|"
        r"tl;dr|about\s+the\s+author|conclusion|summary)",
        re.IGNORECASE,
    )

    def _is_faq_question(line: str) -> bool:
        words = line.split()
        return line.endswith("?") and 2 <= len(words) <= 30

    def _is_section_stop(line: str) -> bool:
        """Return True when a line signals we've left the FAQ section."""
        clean = re.sub(r"^[#*_`]+\s*", "", line).strip()
        return bool(_META_STOP_RE.match(clean))

    answer_word_counts: List[int] = []
    i = 0
    while i < len(scan_lines):
        if _is_section_stop(scan_lines[i]):
            break
        if _is_faq_question(scan_lines[i]):
            j = i + 1
            answer_parts: List[str] = []
            while j < len(scan_lines) and not _is_faq_question(scan_lines[j]):
                if _is_section_stop(scan_lines[j]):
                    break
                answer_parts.append(scan_lines[j])
                j += 1
            answer_text = " ".join(answer_parts).strip()
            if answer_text:
                answer_word_counts.append(len(answer_text.split()))
            i = j
        else:
            i += 1

    if not answer_word_counts:
        return {"faq_count": 0, "faq_min_answer_words": 0, "faq_max_answer_words": 0}
    return {
        "faq_count":            len(answer_word_counts),
        "faq_min_answer_words": min(answer_word_counts),
        "faq_max_answer_words": max(answer_word_counts),
    }


def keyword_dist_max_gap(text: str, keyword: str) -> int:
    if not keyword.strip():
        return 0
    words = text.split()
    total = len(words)
    if total == 0:
        return 0
    kw_tokens = keyword.lower().split()
    n = len(kw_tokens)
    positions: List[int] = []
    for i in range(total - n + 1):
        chunk = [w.lower().strip(".,;:!?\"'()[]") for w in words[i:i + n]]
        if chunk == kw_tokens:
            positions.append(i)
    if not positions:
        return total
    gaps = (
        [positions[0]]
        + [positions[j] - positions[j - 1] for j in range(1, len(positions))]
        + [total - positions[-1]]
    )
    return max(gaps)


def has_cta_at_end(text: str, last_n_words: int = 200) -> bool:
    words = text.split()
    tail = " ".join(words[-last_n_words:]) if len(words) > last_n_words else text
    return bool(_CTA_RE.search(tail))


def transition_words_percent(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0
    count = 0
    for sent in sentences:
        sl = sent.lower()
        for tw in _TRANSITION_WORDS:
            found = (tw in sl) if " " in tw else bool(re.search(r"\b" + re.escape(tw) + r"\b", sl))
            if found:
                count += 1
                break
    return round((count / len(sentences)) * 100, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Unified Metrics Bundle
# ─────────────────────────────────────────────────────────────────────────────

def transition_words_debug(text: str) -> List[Tuple[str, str]]:
    """Return (sentence, matched_transition_word) for every sentence that has one."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    matches: List[Tuple[str, str]] = []
    for sent in sentences:
        sl = sent.lower()
        for tw in _TRANSITION_WORDS:
            found = (tw in sl) if " " in tw else bool(re.search(r"\b" + re.escape(tw) + r"\b", sl))
            if found:
                matches.append((sent.strip(), tw))
                break
    return matches


def build_metrics(
    blog_text:        str,
    clean_text:       str,
    focus_keyword:    str,
    seo_title:        str,
    meta_description: str,
    internal_domain:  str,
    secondary_kw_raw: str = "",
) -> dict:
    prose           = _prose_text(clean_text)
    wc              = count_words(blog_text)
    score           = readability_score(prose if len(prose.split()) > 50 else blog_text)
    kw_hits, kw_pct = keyword_density(blog_text, focus_keyword)
    struct          = structural_analysis(clean_text, focus_keyword)
    links           = analyze_links(clean_text, internal_domain, focus_keyword)
    stats_n         = count_statistics(blog_text)
    faq             = analyze_faqs(split_blocks(clean_text))
    sec_results     = secondary_keyword_analysis(blog_text, secondary_kw_raw)
    sec_max_density = max((r["Density %"] for r in sec_results), default=0.0)
    gap_text        = _text_for_gap(clean_text)
    kw_gap          = keyword_dist_max_gap(gap_text if len(gap_text.split()) > 50 else blog_text, focus_keyword)
    cta_ok          = has_cta_at_end(blog_text)
    trans_pct       = transition_words_percent(blog_text)

    kw = focus_keyword.strip().lower()
    title_starts_kw = bool(kw) and seo_title.strip().lower().startswith(kw)

    return {
        "word_count":               wc,
        "keyword_density":          kw_pct,
        "keyword_hits":             kw_hits,
        "readability_score":        score,
        "title_len":                len(seo_title),
        "meta_len":                 len(meta_description),
        "title_has_kw":             contains_keyword(seo_title, focus_keyword),
        "meta_has_kw":              contains_keyword(meta_description, focus_keyword),
        "title_starts_with_kw":     title_starts_kw,
        "kw_in_first_para":         struct["kw_in_first_para"],
        "kw_in_headings":           struct["kw_in_headings"],
        "kw_in_h1":                 struct["kw_in_h1"],
        "h2_h3_kw_count":           struct["h2_h3_kw_count"],
        "first_150_kw_count":       struct["first_150_kw_count"],
        "max_para_words":           struct["max_para_words"],
        "min_para_words":           struct["min_para_words"],
        "heading_count":            struct["heading_count"],
        "internal_link_count":      links["internal_link_count"],
        "has_internal_links":       links["internal_link_count"] > 0,
        "external_link_count":      links["external_link_count"],
        "duplicate_internal_count": links["duplicate_internal_count"],
        "internal_anchor_has_kw":   links["internal_anchor_has_kw"],
        "stats_count":              stats_n,
        "faq_count":                faq["faq_count"],
        "faq_min_answer_words":     faq["faq_min_answer_words"],
        "faq_max_answer_words":     faq["faq_max_answer_words"],
        "secondary_max_density":    sec_max_density,
        "keyword_dist_max_gap":     kw_gap,
        "has_cta_end":              cta_ok,
        "transition_words_pct":     trans_pct,
        "_struct":                  struct,
        "_links":                   links,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rule Evaluator
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_val(v) -> str:
    if isinstance(v, bool):  return "Yes" if v else "No"
    if isinstance(v, int):   return f"{v:,}"
    if isinstance(v, float): return f"{v:.1f}"
    return str(v)


def _unit(metric_name: str) -> str:
    if any(k in metric_name for k in ("density", "score", "pct", "percent")):
        return " %"
    return ""


def evaluate_rule(key: str, value, metrics: dict) -> Optional[Tuple[bool, str, str]]:
    if key not in RULE_METRIC_MAP:
        return None
    metric_name, operator = RULE_METRIC_MAP[key]
    if metric_name not in metrics:
        return None
    actual = metrics[metric_name]

    if operator == "bool":
        if isinstance(value, bool) and not value:
            return "pass", "Not required", "—"
        status = "pass" if bool(actual) else "fail"
        return status, "Required", ("Present ✓" if status == "pass" else "Not found ✗")

    elif operator == "min":
        if isinstance(value, (bool, str)):
            return None
        u = _unit(metric_name)
        if actual < value:
            status = "fail"
        elif actual == value:
            status = "pass"
        else:           # actual > value → exceeds minimum
            status = "warn"
        return status, f"≥ {_fmt_val(value)}{u}", f"{_fmt_val(actual)}{u}"

    elif operator == "max":
        if isinstance(value, bool):
            if value:
                return "pass", "No limit", _fmt_val(actual)
            value = 0
        elif isinstance(value, str):
            return None
        u = _unit(metric_name)
        if actual > value:
            status = "fail"
        elif value > 0 and actual > value * 0.85:
            status = "warn"   # approaching the limit
        else:
            status = "pass"
        return status, f"≤ {_fmt_val(value)}{u}", f"{_fmt_val(actual)}{u}"

    elif operator == "exact":
        if isinstance(value, (bool, str)):
            return None
        if actual == value:
            status = "pass"
        elif actual > value:
            status = "warn"   # more than required (e.g. 6 FAQs when 5 needed)
        else:
            status = "fail"
        return status, f"= {_fmt_val(value)}", f"{_fmt_val(actual)}"

    return None


# ─────────────────────────────────────────────────────────────────────────────
# UI Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _key_to_label(key: str) -> str:
    return key.replace("_", " ").title()


def _check_row(label: str, status, required: str, actual: str) -> None:
    if status is None:
        icon, ac = "⚪", "#888"
    elif status == "pass":
        icon, ac = "🟢", "#4CAF50"
    elif status == "warn":
        icon, ac = "🟡", "#FFC107"
    else:
        icon, ac = "🔴", "#F44336"

    st.markdown(
        f"""<div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;">
          <span style="font-size:18px;line-height:1.6">{icon}</span>
          <div>
            <div style="font-weight:600;font-size:14px">{label}</div>
            <div style="font-size:12px;color:#999;margin-top:1px;">
              Required:&nbsp;<span style="color:#bbb">{required}</span>
              &nbsp;&nbsp;|&nbsp;&nbsp;
              Actual:&nbsp;<span style="color:{ac};font-weight:600">{actual}</span>
            </div>
          </div>
        </div>""",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="SEO & Content Analyzer",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """<style>
          .block-container { padding-top: 1.6rem; }
          [data-testid="metric-container"] {
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 1rem 1.2rem;
          }
        </style>""",
        unsafe_allow_html=True,
    )

    st.title("📊 SEO & Content Analyzer")
    st.caption("Guidelines are pre-loaded (22 rules). Upload your blog and fill in SEO fields to analyse.")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.header("🔍 SEO Metadata")
        focus_keyword    = st.text_input("Focus Keyword",    placeholder="e.g. multilingual AI interview platforms")
        seo_title        = st.text_input("SEO Title",        placeholder="e.g. Top 10 Multilingual AI Interview Platforms in India")
        meta_description = st.text_input("Meta Description", placeholder="e.g. Explore the top 10 multilingual AI interview platforms…")

        st.divider()
        st.header("🔑 Secondary Keywords")
        secondary_kw_raw = st.text_area(
            "Secondary Keywords",
            placeholder="AI Talent Insights, ITES Hiring Support, Strategy Talent Hub",
            help="Comma-separated. Each phrase is tracked for density.",
            height=80,
        )

        st.divider()
        st.header("⚙️ Settings")
        internal_domain = st.text_input(
            "Internal Domain", value="zeko.ai",
            help="Links containing this domain are counted as internal.",
        )

        st.divider()
        run_btn = st.button("▶  Run Analysis", type="primary", use_container_width=True)

    # ── Active Guidelines panel (always visible, full list) ───────────────────
    with st.expander("📋 Active Guidelines — 22 Rules (click to view)", expanded=False):
        for idx, (key, value) in enumerate(EMBEDDED_GUIDELINES.items(), 1):
            label = RULE_LABELS.get(key, key.replace("_", " ").title())
            desc  = GUIDELINE_DESCRIPTIONS.get(key, "")
            if isinstance(value, bool):
                val_str = "Required" if value else "Not allowed"
            elif isinstance(value, float):
                val_str = f"{value} %"
            else:
                val_str = str(value)
            st.markdown(
                f"**{idx}. {label}** &nbsp;`{val_str}`  \n"
                f"<span style='color:#aaa;font-size:13px'>{desc}</span>",
                unsafe_allow_html=True,
            )
            if idx < len(EMBEDDED_GUIDELINES):
                st.divider()

    # ── Blog content input: Upload OR Paste ───────────────────────────────────
    st.divider()
    tab_upload, tab_paste = st.tabs(["📂 Upload File (.docx / .pdf)", "📋 Paste Content"])

    blog_text: Optional[str] = None

    with tab_upload:
        upload_file = st.file_uploader(
            "Upload your blog document", type=["docx", "pdf"],
            label_visibility="collapsed",
        )
        if upload_file:
            try:
                blog_text = extract_text(upload_file)
                st.success(f"Loaded **{upload_file.name}** — {len(blog_text.split()):,} words detected.")
            except Exception as exc:
                st.error(f"Could not read file: {exc}")

    with tab_paste:
        _paste_saved = st.session_state.get("paste_content", "")
        if _paste_saved:
            _wc = len(_paste_saved.split())
            _col1, _col2 = st.columns([5, 1])
            _col1.success(f"Content loaded — **{_wc:,} words** ready for analysis.")
            if _col2.button("Replace", key="replace_paste"):
                st.session_state["paste_content"] = ""
                for _k in list(st.session_state.keys()):
                    if _k.startswith("quill_"):
                        del st.session_state[_k]
                st.rerun()
            blog_text = _paste_saved
        else:
            st.markdown(
                "Copy your blog from **Google Docs**, **Word**, or any rich editor "
                "and paste below — headings, bold, and hyperlinks are all preserved."
            )
            quill_html = st_quill(
                placeholder="Paste your blog here (Cmd+V / Ctrl+V)…",
                html=True,
                key="quill_editor",
            )
            # Quill returns "<p><br></p>" when empty
            if quill_html and quill_html.strip() not in ("", "<p><br></p>"):
                parsed = parse_html_content(quill_html)
                if parsed.strip():
                    st.session_state["paste_content"] = parsed
                    blog_text = parsed
                    st.rerun()

    # ── Blog content preview ──────────────────────────────────────────────────
    if blog_text:
        with st.expander("📝 Blog Content Preview (parsed)", expanded=False):
            st.text(blog_text[:5000] + ("\n\n[… truncated]" if len(blog_text) > 5000 else ""))

    # ── Idle guard ────────────────────────────────────────────────────────────
    if not run_btn:
        st.info(
            "**Getting started:**\n\n"
            "1. **Upload** your blog (.docx / .pdf) or **Paste** its content in the tabs above.\n"
            "2. Fill in **Focus Keyword**, **SEO Title**, and **Meta Description** in the sidebar.\n"
            "3. Optionally add **Secondary Keywords** (comma-separated).\n"
            "4. Click **▶ Run Analysis**."
        )
        return

    if not blog_text or not blog_text.strip():
        st.error("Please upload a blog document or paste content in the Paste Content tab.")
        return

    # ── Use embedded guidelines ───────────────────────────────────────────────
    G = EMBEDDED_GUIDELINES

    # ── Ensure headings are marked ────────────────────────────────────────────
    # Pasted content from editors without <h1> tags has no '#' markers.
    # Apply the same heuristic used for PDFs so structural checks work correctly.
    _first_nonempty = next((l.strip() for l in blog_text.split("\n") if l.strip()), "")
    if not _first_nonempty.startswith("#"):
        blog_text = _mark_pdf_headings(blog_text)

    # ── Build metrics ─────────────────────────────────────────────────────────
    with st.spinner("Analysing content…"):
        clean_text = strip_metadata_blocks(blog_text)
        M = build_metrics(
            blog_text, clean_text,
            focus_keyword, seo_title, meta_description,
            internal_domain, secondary_kw_raw,
        )

    wc      = M["word_count"]
    score   = M["readability_score"]
    kw_pct  = M["keyword_density"]
    kw_hits = M["keyword_hits"]

    # ── Top metrics row ───────────────────────────────────────────────────────
    st.divider()
    m1, m2, m3, m4, m5, m6 = st.columns(6)

    read_label = (
        "Easy" if score >= 80 else "Standard" if score >= 60
        else "Fairly Difficult" if score >= 50 else "Difficult"
    )
    m1.metric("📖 Reading Ease", f"{score} ({read_label})")

    # Embedded guidelines don't have MIN/MAX_KEYWORD_DENSITY — use display defaults
    d_min, d_max = 1.5, 3.5
    if kw_pct < d_min:
        dd, dc = f"↓ below {d_min} %", "inverse"
    elif kw_pct > d_max:
        dd, dc = f"↑ above {d_max} %", "inverse"
    else:
        dd, dc = "✓ in range", "normal"
    m2.metric("🎯 Keyword Density", f"{kw_pct} %", delta=dd, delta_color=dc)

    wc_min = 1000  # not in embedded guidelines, display-only default
    m3.metric(
        "📝 Word Count", f"{wc:,}",
        delta=f"↓ {wc_min - wc:,} short" if wc < wc_min else f"✓ meets {wc_min:,}",
        delta_color="inverse" if wc < wc_min else "normal",
    )
    m4.metric("🔁 Keyword Hits",   kw_hits)
    m5.metric("🔗 Internal Links", M["internal_link_count"])
    m6.metric("📊 Stats Found",    M["stats_count"])

    # ── Secondary keyword table ───────────────────────────────────────────────
    st.divider()
    st.subheader("🔑 Secondary Keyword Density")
    sec_data = secondary_keyword_analysis(blog_text, secondary_kw_raw)
    if sec_data:
        for row in sec_data:
            d = row["Density %"]
            row["Status"] = (
                "🟢 In Range (0.3–0.4%)" if 0.3 <= d <= 0.4 else
                "🟡 Low (< 0.3%)"        if d < 0.3          else
                "🟠 High (> 0.4%)"
            )
        st.dataframe(sec_data, use_container_width=True, hide_index=True)
        best = max(sec_data, key=lambda r: r["Density %"])
        st.caption(
            f"The **Min Secondary Keyword Density** rule checks whether at least one "
            f"secondary keyword has density ≥ 0.3 %. "
            f"Highest here: **{best['Keyword / Phrase']}** at **{best['Density %']} %**."
        )
    else:
        st.caption("Enter secondary keywords in the sidebar to track their density.")

    # ── Unified dynamic checklist ─────────────────────────────────────────────
    st.divider()
    st.subheader("✅ Full Analysis Checklist")

    known_rows:   List[tuple] = []
    unknown_rows: List[tuple] = []

    for key, value in G.items():
        label  = RULE_LABELS.get(key, _key_to_label(key))
        result = evaluate_rule(key, value, M)
        if result is None:
            unknown_rows.append((label, None, _fmt_val(value), "Manual check required"))
        else:
            status, required, actual = result
            known_rows.append((label, status, required, actual))

    all_rows   = known_rows + unknown_rows
    left_rows  = all_rows[0::2]
    right_rows = all_rows[1::2]

    cl1, cl2 = st.columns(2)
    with cl1:
        for label, status, required, actual in left_rows:
            _check_row(label, status, required, actual)
    with cl2:
        for label, status, required, actual in right_rows:
            _check_row(label, status, required, actual)

    # ── Per-paragraph breakdown ───────────────────────────────────────────────
    st.divider()
    with st.expander("📄 Per-Paragraph Word-Count Breakdown", expanded=False):
        rows = M["_struct"]["para_lengths"]
        max_limit = G.get("MAX_PARAGRAPH_WORDS", DEFAULTS["MAX_PARAGRAPH_WORDS"])
        if not isinstance(max_limit, (int, float)):
            max_limit = DEFAULTS["MAX_PARAGRAPH_WORDS"]
        if rows:
            st.dataframe(
                [
                    {
                        "Preview": (p[:110] + "…") if len(p) > 110 else p,
                        "Words": pw,
                        "Status": (
                            "🔴 Too long" if pw > max_limit else "🟢 OK"
                        ),
                    }
                    for p, pw in rows
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No body paragraphs detected.")

    # ── Transition words ──────────────────────────────────────────────────────
    with st.expander("🔀 Transition Words Found", expanded=False):
        tw_matches = transition_words_debug(blog_text)
        if tw_matches:
            total_sents = len([s for s in re.split(r'[.!?]+', blog_text) if s.strip()])
            st.caption(f"**{len(tw_matches)}** sentences out of {total_sents} contain a transition word.")
            word_counts = Counter(tw for _, tw in tw_matches)
            words_display = "  ".join(
                f"**{tw}**" + (f" ×{c}" if c > 1 else "")
                for tw, c in sorted(word_counts.items(), key=lambda x: -x[1])
            )
            st.markdown(words_display)
        else:
            st.caption("No transition words detected.")

    # ── Link details ──────────────────────────────────────────────────────────
    with st.expander("🔗 Detected Links", expanded=False):
        ld = M["_links"]
        lc1, lc2 = st.columns(2)
        with lc1:
            st.markdown(f"**Internal links ({ld['internal_link_count']}) — domain: `{internal_domain}`**")
            if ld["internal_urls"]:
                anchors = ld.get("internal_anchors", [])
                for idx, u in enumerate(ld["internal_urls"]):
                    anchor_label = f" *(anchor: {anchors[idx]})*" if idx < len(anchors) else ""
                    st.markdown(f"- {u}{anchor_label}")
            else:
                st.caption("None found.")
        with lc2:
            st.markdown(f"**External links ({ld['external_link_count']}) — counted against ≤ {G.get('MAX_EXTERNAL_LINKS', 3)} limit**")
            if ld["external_urls"]:
                for u in ld["external_urls"][:30]:
                    st.markdown(f"- {u}")
            else:
                st.caption("None found.")


if __name__ == "__main__":
    main()
