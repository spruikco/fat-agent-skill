"""html parsing and text analysis helpers for content quality module."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP_TAGS = frozenset({"nav", "header", "footer", "script", "style", "noscript"})

_HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

_NBSP_RE = re.compile(r"&nbsp;|&#160;|\xa0")

_LOREM_RE = re.compile(
    r"lorem\s+ipsum|dolor\s+sit\s+amet|consectetur\s+adipiscing|"
    r"placeholder\s+text|your\s+text\s+here|insert\s+text\s+here|"
    r"coming\s+soon\s+placeholder",
    re.IGNORECASE,
)

_COPYRIGHT_RE = re.compile(r"(?:\u00a9|&copy;|\bcopyright\b)\s*(\d{4})", re.IGNORECASE)

_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "his",
        "how",
        "its",
        "may",
        "new",
        "now",
        "old",
        "see",
        "way",
        "who",
        "did",
        "get",
        "let",
        "say",
        "she",
        "too",
        "use",
        "with",
        "this",
        "that",
        "from",
        "they",
        "been",
        "have",
        "your",
        "will",
        "each",
        "make",
        "like",
        "than",
        "them",
        "then",
        "what",
        "when",
        "more",
        "some",
        "very",
        "about",
        "which",
        "their",
        "there",
        "would",
        "other",
    }
)


class BodyTextExtractor(HTMLParser):
    """Extracts visible body text, skipping nav/header/footer/script/style."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth: int = 0
        self._in_body: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag == "body":
            self._in_body = True
        if self._in_body and tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):
        if self._in_body and tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "body":
            self._in_body = False

    def handle_data(self, data: str):
        if self._in_body and self._skip_depth == 0:
            self.text_parts.append(data)


class TagTextExtractor(HTMLParser):
    """Extracts text from title, h1-h6, p tags and meta description."""

    def __init__(self):
        super().__init__()
        self.title_text: str = ""
        self.h1_texts: list[str] = []
        self.paragraphs: list[str] = []
        self.headings: list[str] = []
        self.meta_description: str = ""
        self._current_tag: str | None = None
        self._current_data: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag in ("title", "p") or tag in _HEADING_TAGS:
            self._current_tag = tag
            self._current_data = []
        if tag == "meta":
            attr_dict = dict(attrs)
            if attr_dict.get("name", "").lower() == "description":
                self.meta_description = attr_dict.get("content", "")

    def handle_endtag(self, tag: str):
        if tag == self._current_tag:
            text = " ".join(self._current_data).strip()
            if tag == "title":
                self.title_text = text
            elif tag == "h1":
                self.h1_texts.append(text)
                self.headings.append(text)
            elif tag in _HEADING_TAGS:
                self.headings.append(text)
            elif tag == "p":
                self.paragraphs.append(text)
            self._current_tag = None
            self._current_data = []

    def handle_data(self, data: str):
        if self._current_tag is not None:
            self._current_data.append(data)


def count_syllables(word: str) -> int:
    """Estimate syllable count via vowel-group heuristic."""
    word = word.lower().strip()
    if not word:
        return 0
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in "aeiouy"
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def flesch_kincaid_grade(text: str) -> float | None:
    """Return flesch-kincaid grade level, or None if insufficient text."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r"[a-zA-Z']+", text)
    if len(words) < 30 or len(sentences) < 1:
        return None
    total_syllables = sum(count_syllables(w) for w in words)
    grade = (
        0.39 * (len(words) / len(sentences))
        + 11.8 * (total_syllables / len(words))
        - 15.59
    )
    return round(grade, 1)


def extract_keywords(text: str) -> set[str]:
    """Extract significant words (3+ chars, lowercased) from text."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _STOP_WORDS}
