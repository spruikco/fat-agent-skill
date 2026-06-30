"""Content-depth & quality audit module (Hobo-parity, Quality-Rater-aligned).

Goes beyond the word-count/readability of `content_quality` to the page-quality
signals Google's Quality Rater Guidelines and the helpful-content system weigh —
all from the live HTML:

- **YMYL detection** — flags Your-Money-or-Your-Life topics that need the highest
  E-E-A-T scrutiny.
- **Main-content vs ad density** — too many ad slots relative to content is a
  page-quality demotion.
- **Information gain / originality** — original media, data tables, citations,
  statistics (vs a thin re-hash).
- **Freshness** — a real published/updated date.
- **Featured-snippet readiness** — a concise lead answer.
- **Product-review quality** — first-hand testing, pros/cons, comparisons.
"""

from __future__ import annotations

import re
import urllib.parse

from modules import register_module
from modules.base import AuditModule

# Tightened with trailing boundaries/stems so "lawn", "taxi", "taxonomy",
# "investigative", "drugstore", "treatment plant" etc. don't trigger YMYL.
_YMYL_RE = re.compile(
    r"\b(health(?:care|y)?|medical|medicine|symptoms?|diagnos(?:is|tic)|"
    r"disease|mental[- ]health|finance|financial|invest(?:ing|ment|or)?|loans?|"
    r"mortgages?|insurance|tax(?:es|ation|payer)?|retirement|cryptocurrency|"
    r"legal|lawyer|attorney|immigration|divorce|prescription|nutritional?|"
    r"pregnan(?:t|cy))\b",
    re.IGNORECASE,
)
# True ad-network signals only — "banner"/"sponsor" hit hero/cookie/announcement
# banners and sponsored-athlete prose, so they're excluded.
_AD_RE = re.compile(
    r"adsbygoogle|googlesyndication|data-ad-client|data-ad-slot|"
    r'class=["\'][^"\']*\bad-?(?:slot|unit|container|wrapper)\b|'
    r'id=["\'][^"\']*\bad[-_]',
    re.IGNORECASE,
)
_FRESH_RE = re.compile(
    r'datepublished|datemodified|"datePublished"|"dateModified"|<time[\s>]|'
    r"last[\s-]?updated|updated on|published on|reviewed on",
    re.IGNORECASE,
)
# "review/vs/compared" only (not bare "best"); confirmed by a rating/pros-cons
# signal or Review/Product schema in is_review().
_REVIEW_CTX_RE = re.compile(
    r"\b(review|versus|compared?\s+to|head[- ]to[- ]head)\b|\bvs\.?\b", re.IGNORECASE
)
_REVIEW_EVIDENCE_RE = re.compile(
    r'"@type"\s*:\s*"(review|product)"|pros?\s*(?:&|and|/)\s*cons?|'
    r"star[- ]rating|aggregaterating|out of 5|/5\b|rating",
    re.IGNORECASE,
)
_FIRSTHAND_RE = re.compile(
    r"we tested|i tested|our test|hands[- ]on|in our (?:test|experience)|"
    r"we tried|we measured|after (?:using|testing)|our review",
    re.IGNORECASE,
)


def _visible_text(html):
    txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"(?is)<(nav|header|footer)[^>]*>.*?</\1>", " ", txt)
    return re.sub(r"<[^>]+>", " ", txt)


def _is_article(html, url):
    """True only on a per-page signal — NOT a /blog/ link sitting in the nav/footer.

    Requires the page's OWN URL path to be article-like, OR Article-family JSON-LD
    on this page, OR a small number of top-level <article> elements (not a card grid).
    """
    low = html.lower()
    path = urllib.parse.urlparse(url).path.lower() if url else ""
    if re.search(r"/blog/|/news/|/article/|/post/|/guides?/", path):
        return True
    if re.search(r'"@type"\s*:\s*"(article|blogposting|newsarticle)"', low):
        return True
    return "<article" in low and low.count("<article") <= 2


def lead_answer_present(html):
    """A concise (~40-60 word) paragraph soon after the H1 — featured-snippet bait."""
    m = re.search(r"</h1>(.*?)(?:<h2|</article>|$)", html, re.IGNORECASE | re.DOTALL)
    region = m.group(1) if m else html
    for para in re.findall(r"<p[^>]*>(.*?)</p>", region, re.IGNORECASE | re.DOTALL):
        words = len(re.sub(r"<[^>]+>", " ", para).split())
        if 20 <= words <= 70:
            return True
    return False


@register_module
class ContentDepthModule(AuditModule):
    MODULE_ID = "content_depth"
    DISPLAY_NAME = "Content Depth & Quality"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        text = _visible_text(html)
        words = len(text.split())
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        heading_text = " ".join(
            filter(None, [title and title.group(1), h1 and h1.group(1)])
        )

        ad_hits = len(_AD_RE.findall(html))
        originality = {
            "tables": "<table" in html.lower(),
            "figures_or_images": bool(re.search(r"<figure|<img", html, re.IGNORECASE)),
            "citations": bool(
                re.search(r"<blockquote|<cite|rel=[\"']nofollow", html, re.IGNORECASE)
            )
            or "http" in text,
            "statistics": bool(re.search(r"\d+\s?%|\b\d{2,}\b", text)),
        }
        return {
            "is_article": _is_article(html, url),
            "word_count": words,
            "ymyl": bool(_YMYL_RE.search(heading_text) or _YMYL_RE.search(url)),
            "ad_hits": ad_hits,
            "ad_heavy": ad_hits >= 4 and words < 1200,
            "has_freshness": bool(_FRESH_RE.search(html)),
            "originality": originality,
            "originality_score": sum(originality.values()),
            "lead_answer": lead_answer_present(html),
            "is_review": bool(_REVIEW_CTX_RE.search(heading_text))
            and bool(_REVIEW_EVIDENCE_RE.search(html)),
            "firsthand": bool(_FIRSTHAND_RE.search(text)),
            "discover": {
                "large_image_preview": bool(
                    re.search(r"max-image-preview\s*:\s*large", html, re.IGNORECASE)
                ),
                "og_image": bool(
                    re.search(r'property=["\']og:image', html, re.IGNORECASE)
                ),
                "feed": bool(
                    re.search(
                        r'rel=["\']alternate["\'][^>]*type=["\']application/(?:rss\+xml|atom\+xml)',
                        html,
                        re.IGNORECASE,
                    )
                ),
            },
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        ad = 20 if not analysis["ad_heavy"] else 5
        details["ad_balance"] = {"score": ad, "max": 20}
        total += ad

        orig = min(analysis["originality_score"] * 6, 24)
        details["originality"] = {"score": orig, "max": 24}
        total += orig

        fresh = (
            18
            if analysis["has_freshness"]
            else (18 if not analysis["is_article"] else 0)
        )
        details["freshness"] = {"score": fresh, "max": 18}
        total += fresh

        snippet = 18 if analysis["lead_answer"] else 8
        details["snippet_readiness"] = {"score": snippet, "max": 18}
        total += snippet

        ymyl_ok = (
            20 if not analysis["ymyl"] else 10
        )  # YMYL just raises the bar; handled in findings
        details["ymyl_baseline"] = {"score": ymyl_ok, "max": 20}
        total += ymyl_ok

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a["ymyl"]:
            self.add_finding(
                priority="P2",
                title="YMYL topic — apply highest E-E-A-T scrutiny",
                description="This page covers a Your-Money-or-Your-Life topic (health/finance/"
                "legal/safety). Google holds YMYL content to the highest accuracy and trust bar.",
                fix="Ensure a credentialed author, citations to authoritative sources, a "
                "'reviewed by' expert, clear dates, and visible contact/ownership.",
                effort="medium",
            )
        if a["ad_heavy"]:
            self.add_finding(
                priority="P2",
                title="High ad density relative to content",
                description=f"Detected {a['ad_hits']} ad slots against limited main content. A high "
                "ad-to-content ratio (and ads above the main content) is a page-quality demotion.",
                fix="Reduce ad units, keep them out of the way of the main content, and add "
                "substantive content.",
                effort="medium",
            )
        if a["is_article"] and a["originality_score"] <= 1:
            self.add_finding(
                priority="P2",
                title="Low information-gain / originality signals",
                description="The page shows few signs of original value — no data tables, original "
                "media, statistics, or citations. Google's helpful-content system rewards "
                "content that adds something new versus what already ranks.",
                fix="Add original data, first-hand examples, images you produced, or analysis that "
                "isn't available on competing pages.",
                effort="high",
            )
        if a["is_article"] and not a["has_freshness"]:
            self.add_finding(
                priority="P3",
                title="No published/updated date",
                description="No visible or structured publish/update date. Freshness is a ranking "
                "and trust signal, especially for time-sensitive topics.",
                fix="Show a published and last-updated date and mirror it in Article schema "
                "(`datePublished`/`dateModified`).",
                effort="low",
            )
        if not a["lead_answer"] and a["is_article"]:
            self.add_finding(
                priority="P3",
                title="No concise lead answer (featured-snippet/AEO)",
                description="The page doesn't open with a concise ~40-60 word answer, which both "
                "featured snippets and AI answer engines lift.",
                fix="Add a short, direct summary answering the core query near the top.",
                effort="low",
            )
        if a["is_review"] and not a["firsthand"]:
            self.add_finding(
                priority="P2",
                title="Review lacks first-hand evidence",
                description="This looks like a review/comparison page but shows no first-hand "
                "testing signals. Google's reviews system rewards demonstrable hands-on experience, "
                "evidence, and comparisons.",
                fix="Add original photos/measurements, pros and cons, how you tested, and "
                "comparisons to alternatives.",
                effort="high",
            )
        d = a["discover"]
        if a["is_article"] and not (d["large_image_preview"] and d["og_image"]):
            self.add_finding(
                priority="P3",
                title="Not optimised for Google Discover",
                description="Discover favours articles with a large, high-quality lead image. This "
                "page is missing `max-image-preview:large` and/or a large `og:image`"
                + (
                    ""
                    if d["feed"]
                    else ", and has no RSS/Atom feed for the Follow button"
                )
                + ".",
                fix='Add `<meta name="robots" content="max-image-preview:large">`, a ≥1200px '
                "`og:image`, and an RSS/Atom feed.",
                effort="low",
            )
