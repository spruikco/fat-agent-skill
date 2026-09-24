"""Google Search guidelines compliance module (spam policies + current guidance).

Maps a page against Google Search Essentials as they stand after the 2024-2026
core/spam updates, so a traffic drop can be traced to a policy pattern rather
than guessed at. Everything here is observable in the static HTML:

- **Retired rich results** — FAQPage/HowTo/sitelinks-search-box and the 2025
  structured-data simplification. The markup isn't harmful, but it no longer
  earns a SERP feature, so it's effort pointed at nothing.
- **Title links & snippets** — over-long or keyword-stuffed titles (Google
  rewrites them), stuffed/over-long/too-short meta descriptions.
- **Keyword stuffing** — repeated terms and long lists of place names (the
  classic "we service Suburb A, Suburb B, Suburb C..." doorway tell).
- **Hidden text** — inline-styled hidden blocks holding real copy.
- **Sneaky redirects** — JS redirects conditioned on user agent / referrer.
- **Back button hijacking** — history manipulation on load / popstate
  redirects (spam policy added Apr 2026, enforced from 15 Jun 2026).
- **Indexing limits** — robots meta in <body> (honoured since Mar 2026) and
  HTML beyond Googlebot's 2MB indexing cut-off.
- **Scaled-content tells** — unedited AI output and generic filler phrasing
  (the Jan 2025 Quality Rater Guidelines rate low-effort scaled content Lowest).
- **Freshness honesty** — future-dated or inconsistent published/modified dates.
- **Link spam** — affiliate/paid outbound links without rel="sponsored".
- **SERP presentation** — favicon, site-name (WebSite) markup, snippet opt-outs
  that also suppress AI Overviews.

Site-level patterns (templated doorway pages, scaled content share, slash
duplicates) need a whole crawl; they live in sitewide.py and reuse the
constants below.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import urllib.parse
from collections import Counter

from modules import register_module
from modules.base import AuditModule

# Rich-result types Google has retired or restricted. Markup stays valid
# schema.org but earns no SERP feature (sources in references/google-guidelines.md).
RETIRED_RICH_RESULTS = {
    "HowTo": "HowTo rich results were removed in Sept 2023.",
    "FAQPage": "FAQ rich results stopped showing on 7 May 2026 and the docs were "
    "removed in June 2026.",
    "Quiz": "Practice problem rich results were retired (docs removed Jan 2026).",
    "MathSolver": "Math solver/practice problem features were retired in 2025-26.",
    "SpecialAnnouncement": "Retired in the June 2025 structured-data simplification.",
    "ClaimReview": "ClaimReview rich results were phased out in June 2025.",
    "EstimatedSalary": "Retired in the June 2025 structured-data simplification.",
    "LearningResource": "Learning Video rich results were retired in June 2025.",
    "Course": "Course Info rich results were retired in June 2025 (Course "
    "carousel/list markup is a separate feature).",
    "Book": "Book Actions were retired in June 2025.",
    "Vehicle": "Vehicle Listing rich results were retired in June 2025.",
    "Car": "Vehicle Listing rich results were retired in June 2025.",
}
SEARCH_ACTION_NOTE = (
    "The sitelinks search box (WebSite potentialAction SearchAction) was "
    "removed from Google results in Nov 2024."
)

TITLE_MAX = 60  # beyond ~600px Google truncates, and often rewrites the title
META_MIN, META_MAX = 70, 160

_STOP = set(
    """a an and are as at be by for from has have in is it its of on or our that the
    their this to was we were will with you your us can all any more not but
    so if do does how what why when who which into out about than then them
    they he she his her i me my also get been just over may most only other
    such very one two new use used using per via""".split()
)

# Unedited LLM output — a strong scaled-content-abuse signal on its own.
_AI_LEAK_RE = re.compile(
    r"as an ai (?:language )?model|as of my (?:last )?knowledge cutoff|"
    r"i (?:cannot|can't) browse the internet|regenerate response|"
    r"\[(?:insert|your|company|business) [^\]]{1,40}\]|"
    r"\[(?:city|suburb|location|keyword|business name)\]|\{\{\s*[a-z_]+\s*\}\}",
    re.IGNORECASE,
)
# Generic filler phrasing that clusters in low-effort generated copy. One hit is
# nothing; several distinct ones on one page is a pattern worth a human look.
_FILLER_PHRASES = [
    r"in today'?s (?:fast[- ]paced|digital|ever[- ](?:changing|evolving)|competitive)",
    r"ever[- ]evolving (?:landscape|world)",
    r"digital landscape",
    r"\bdelve(?:s|d)? (?:into|deeper)",
    r"unlock(?:ing)? the (?:full )?(?:power|potential)",
    r"look no further",
    r"\btapestry\b",
    r"navigat(?:e|ing) the (?:complex(?:ities)?|world|landscape)",
    r"elevate your (?:brand|business|online presence)",
    r"take your (?:business|brand) to the next level",
    r"whether you'?re a (?:small business|seasoned)",
    r"in conclusion,",
    r"it'?s (?:important|worth) (?:to note|noting) that",
    r"game[- ]changer",
    r"\bseamless(?:ly)?\b",
    r"\bsupercharge\b",
    r"harness(?:ing)? the power",
    r"one[- ]stop[- ]shop",
]
_FILLER_RE = [re.compile(p, re.IGNORECASE) for p in _FILLER_PHRASES]

_AFFILIATE_RE = re.compile(
    r"[?&](?:aff(?:iliate)?(?:_?id)?|ref(?:id)?|partner(?:id)?|tag|irclickid|clickid)=|"
    r"/(?:go|recommends|refer|aff|out)/|amzn\.to/|shareasale\.com|awin1\.com|"
    r"impact\.com|partnerize|commission-junction|anrdoezrs\.net|tkqlhce\.com|"
    r"prf\.hn|clk\.",
    re.IGNORECASE,
)
_SNEAKY_COND_RE = re.compile(
    r"(navigator\.userAgent|document\.referrer)[^;{}]{0,200}?[{(]?[^;]{0,200}?"
    r"(?:window\.|document\.|top\.)?location(?:\.href)?\s*(?:=|\.replace\(|\.assign\()",
    re.IGNORECASE | re.DOTALL,
)
_BACK_HIJACK_RE = re.compile(
    r"addEventListener\(\s*['\"]popstate['\"][^;]{0,400}?"
    r"(?:location(?:\.href)?\s*=|location\.(?:replace|assign)\(|window\.open\()|"
    r"onpopstate\s*=[^;]{0,400}?(?:location(?:\.href)?\s*=|location\.(?:replace|assign)\()",
    re.IGNORECASE | re.DOTALL,
)
_PUSHSTATE_RE = re.compile(r"history\.(?:pushState|replaceState)\s*\(", re.IGNORECASE)
GOOGLEBOT_HTML_LIMIT = 2 * 1024 * 1024  # bytes of uncompressed HTML Google indexes
_HIDDEN_STYLE_RE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:px|em|rem)?\s*[;\"']|"
    r"text-indent\s*:\s*-\d{3,}|left\s*:\s*-\d{4,}px",
    re.IGNORECASE,
)


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _visible_text(html: str) -> str:
    txt = re.sub(r"(?is)<(script|style|noscript|template|svg)[^>]*>.*?</\1>", " ", html)
    return " ".join(_strip_tags(txt).split())


def _body_text(html: str) -> str:
    """Visible text minus site chrome (nav/header/footer/aside)."""
    txt = re.sub(r"(?is)<(script|style|noscript|template|svg)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"(?is)<(nav|header|footer|aside)[^>]*>.*?</\1>", " ", txt)
    return " ".join(_strip_tags(txt).split())


def _words(text: str) -> list:
    return re.findall(r"[a-z][a-z0-9'-]+", text.lower())


def stuffed_terms(text: str, min_repeat: int = 3) -> list:
    """Content words repeated ``min_repeat``+ times in a short field (title/meta)."""
    counts = Counter(w for w in _words(text) if w not in _STOP and len(w) > 2)
    return sorted(w for w, c in counts.items() if c >= min_repeat)


def title_is_stuffed(title: str) -> bool:
    """A title reads as stuffed when it repeats a term 3+ times, strings 5+
    pipe/bullet-delimited fragments together ("SEO | SEO Agency | SEO Melbourne
    | ..."), or packs a 4+ item comma list into one segment. A normal
    "Topic | Qualifier, Qualifier | Brand" title passes."""
    if not title:
        return False
    if stuffed_terms(title):
        return True
    segments = [p for p in re.split(r"\s*[|•·]\s*", title) if p.strip()]
    if len(segments) >= 5:
        return True
    return any(len([x for x in seg.split(",") if x.strip()]) >= 4 for seg in segments)


def place_list_runs(text: str, min_items: int = 10) -> int:
    """Longest run of comma-separated short Title-Case items ("Carlton, Fitzroy,
    Richmond, ..."). Long runs are the classic location-stuffing doorway tell."""
    best = 0
    for m in re.finditer(
        r"(?:[A-Z][a-zA-Z'.-]+(?: [A-Z][a-zA-Z'.-]+){0,2}\s*,\s*){%d,}"
        r"(?:and\s+)?[A-Z][a-zA-Z'.-]+" % (min_items - 1),
        text,
    ):
        best = max(best, m.group(0).count(",") + 1)
    return best


def _jsonld_blocks(html: str) -> list:
    out = []
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            out.append(json.loads(m.group(1).strip()))
        except (ValueError, TypeError):
            continue
    return out


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _types(node) -> list:
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    return []


def _parse_date(value):
    if not isinstance(value, str):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    if not m:
        return None
    try:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _meta(html: str, name: str) -> str | None:
    for pat in (
        r'<meta\s[^>]*name=["\']%s["\'][^>]*content=["\']([^"\']*)["\']',
        r'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']%s["\']',
    ):
        m = re.search(pat % re.escape(name), html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _hidden_text_words(html: str) -> int:
    """Words of copy inside inline-style-hidden elements (menus/modals excluded).

    Conservative: only counts <p>/<div>/<span>/<section> blocks whose OWN style
    hides them and whose content isn't obviously a UI component.
    """
    total = 0
    for m in re.finditer(
        r"<(p|div|span|section)\b([^>]*)>(.*?)</\1>", html, re.IGNORECASE | re.DOTALL
    ):
        attrs, inner = m.group(2), m.group(3)
        style = re.search(r'style=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
        if not style or not _HIDDEN_STYLE_RE.search(style.group(1) + ";"):
            continue
        if re.search(
            r"(?:menu|modal|dropdown|drawer|tooltip|popup|dialog|toast|cookie|"
            r"tab-?panel|accordion|collapse|sr-only|visually-hidden)",
            attrs,
            re.IGNORECASE,
        ):
            continue
        if re.search(r"aria-(?:hidden|expanded|controls)|role=", attrs, re.IGNORECASE):
            continue
        n = len(_strip_tags(inner).split())
        if n >= 25:
            total += n
    return total


@register_module
class GoogleGuidelinesModule(AuditModule):
    MODULE_ID = "google_guidelines"
    DISPLAY_NAME = "Google Guidelines"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        today = kwargs.get("today") or _dt.date.today()
        path = urllib.parse.urlparse(url).path if url else ""
        is_home = path in ("", "/")

        tm = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = " ".join(_strip_tags(tm.group(1)).split()) if tm else ""
        meta_desc = _meta(html, "description") or ""

        body = _body_text(html)
        body_words = [w for w in _words(body)]
        content = [w for w in body_words if w not in _STOP and len(w) > 2]
        top_term, top_density = "", 0.0
        if len(body_words) >= 300 and content:
            top_term, n = Counter(content).most_common(1)[0]
            top_density = round(n / len(body_words) * 100, 2)

        # structured data
        retired, has_search_action, website_name = [], False, False
        published = modified = None
        for block in _jsonld_blocks(html):
            for node in _walk(block):
                for t in _types(node):
                    if t in RETIRED_RICH_RESULTS and t not in retired:
                        retired.append(t)
                    if t == "WebSite" and node.get("name"):
                        website_name = True
                pa = node.get("potentialAction")
                for act in pa if isinstance(pa, list) else [pa]:
                    if isinstance(act, dict) and "SearchAction" in _types(act):
                        has_search_action = True
                published = published or _parse_date(node.get("datePublished"))
                modified = modified or _parse_date(node.get("dateModified"))

        # robots snippet controls
        robots = " ".join(
            filter(None, [_meta(html, "robots"), _meta(html, "googlebot")])
        ).lower()
        if headers:
            for k, v in headers.items():
                if k.lower() == "x-robots-tag" and v:
                    robots += " " + str(v).lower()
        snippet_blocked = bool(
            re.search(r"\bnosnippet\b|max-snippet\s*:\s*0\b", robots)
        )
        data_nosnippet = len(re.findall(r"\bdata-nosnippet\b", html, re.IGNORECASE))

        # outbound affiliate / paid links lacking a qualifying rel
        host = urllib.parse.urlparse(url).netloc.lower() if url else ""
        unqualified = []
        for m in re.finditer(r"<a\b([^>]*)>", html, re.IGNORECASE):
            attrs = m.group(1)
            href = re.search(r'href=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if not href:
                continue
            h = href.group(1)
            target_host = urllib.parse.urlparse(h).netloc.lower()
            internal_go = bool(re.search(r"/(?:go|recommends|out)/", h))
            if (target_host and target_host != host) or internal_go:
                if _AFFILIATE_RE.search(h):
                    rel = re.search(r'rel=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
                    relv = rel.group(1).lower() if rel else ""
                    if "sponsored" not in relv and "nofollow" not in relv:
                        unqualified.append(h[:120])

        scripts = " ".join(
            re.findall(
                r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                html,
                re.IGNORECASE | re.DOTALL,
            )
        )

        body_start = re.search(r"<body\b", html, re.IGNORECASE)
        body_html = html[body_start.start():] if body_start else ""
        body_robots = [
            m.group(0)
            for m in re.finditer(
                r'<meta\s[^>]*name=["\'](?:robots|googlebot)["\'][^>]*>',
                body_html,
                re.IGNORECASE,
            )
        ]
        pushes = len(_PUSHSTATE_RE.findall(scripts))

        filler_hits = sorted(
            {p for p, rx in zip(_FILLER_PHRASES, _FILLER_RE) if rx.search(body)}
        )

        icons = [
            m.group(0)
            for m in re.finditer(
                r'<link[^>]*rel=["\'][^"\']*\bicon\b[^"\']*["\'][^>]*>',
                html,
                re.IGNORECASE,
            )
        ]

        return {
            "is_home": is_home,
            "title": title,
            "title_length": len(title),
            "title_stuffed": title_is_stuffed(title),
            "title_repeats": stuffed_terms(title),
            "meta_description_length": len(meta_desc),
            "meta_stuffed": stuffed_terms(meta_desc, 4),
            "meta_places": place_list_runs(meta_desc, 5),
            "body_word_count": len(body_words),
            "top_term": top_term,
            "top_term_density": top_density,
            "place_list_max": place_list_runs(body),
            "hidden_text_words": _hidden_text_words(html),
            "sneaky_redirect": bool(_SNEAKY_COND_RE.search(scripts)),
            "back_button_hijack": bool(_BACK_HIJACK_RE.search(scripts)),
            "history_push_calls": pushes,
            "body_robots_noindex": any("noindex" in t.lower() for t in body_robots),
            "body_robots_meta": len(body_robots),
            "html_bytes": len(html.encode("utf-8", "replace")),
            "ai_leak": bool(_AI_LEAK_RE.search(_visible_text(html))),
            "filler_hits": filler_hits,
            "retired_rich_results": retired,
            "search_action": has_search_action,
            "website_name": website_name,
            "date_published": published.isoformat() if published else None,
            "date_modified": modified.isoformat() if modified else None,
            "future_dated": bool(
                (published and published > today) or (modified and modified > today)
            ),
            "dates_inverted": bool(published and modified and modified < published),
            "snippet_blocked": snippet_blocked,
            "data_nosnippet": data_nosnippet,
            "has_favicon": bool(icons),
            "favicon_svg_only": bool(icons)
            and all(re.search(r"\.svg(?![a-z])|image/svg", i, re.IGNORECASE) for i in icons),
            "unqualified_affiliate_links": unqualified[:10],
        }

    # ------------------------------------------------------------------ #
    def score(self, analysis: dict) -> dict:
        a = analysis
        details = {}

        spam = 40
        if a.get("back_button_hijack"):
            spam -= 15
        if a.get("sneaky_redirect"):
            spam -= 15
        if a.get("hidden_text_words", 0) >= 25:
            spam -= 10
        if a.get("ai_leak"):
            spam -= 15
        if a.get("place_list_max", 0) >= 10 or a.get("top_term_density", 0) > 4:
            spam -= 10
        if a.get("unqualified_affiliate_links"):
            spam -= 5
        details["spam_policies"] = {"score": max(spam, 0), "max": 40}

        snippet = 30
        if a.get("title_stuffed"):
            snippet -= 10
        elif a.get("title_length", 0) > TITLE_MAX:
            snippet -= 4
        mlen = a.get("meta_description_length", 0)
        if mlen and (mlen < META_MIN or mlen > META_MAX):
            snippet -= 4
        if a.get("meta_stuffed") or a.get("meta_places", 0) >= 5:
            snippet -= 6
        if a.get("snippet_blocked"):
            snippet -= 6
        if a.get("body_robots_noindex") or a.get("html_bytes", 0) > GOOGLEBOT_HTML_LIMIT:
            snippet -= 10
        details["title_snippet"] = {"score": max(snippet, 0), "max": 30}

        quality = 20
        if len(a.get("filler_hits", [])) >= 3:
            quality -= 8
        if a.get("future_dated") or a.get("dates_inverted"):
            quality -= 6
        details["content_signals"] = {"score": max(quality, 0), "max": 20}

        serp = 10
        if not a.get("has_favicon") or a.get("favicon_svg_only"):
            serp -= 4
        if a.get("is_home") and not a.get("website_name"):
            serp -= 3
        if a.get("retired_rich_results") or a.get("search_action"):
            serp -= 3
        details["serp_presentation"] = {"score": max(serp, 0), "max": 10}

        self._findings(a)
        total = sum(d["score"] for d in details.values())
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a.get("back_button_hijack"):
            self.add_finding(
                priority="P1",
                title="Back button hijacking (spam policy, enforced Jun 2026)",
                description="An inline script listens for popstate (the back button) and "
                "redirects or opens a new page instead of letting the user leave. Google "
                "added back button hijacking to its spam policies in April 2026 and has "
                "enforced it since 15 June 2026. Check ad and 'recommended content' "
                "scripts too; they're the usual source.",
                fix="Remove the popstate redirect and any history.pushState calls that "
                "run without a user action.",
                effort="low",
            )
        elif a.get("history_push_calls", 0) >= 2:
            self.add_finding(
                priority="P3",
                title="History manipulation in page scripts (verify)",
                description=f"{a['history_push_calls']} history.pushState/replaceState "
                "calls in inline scripts. Fine for SPA routing, but inserting history "
                "entries on load so Back doesn't leave the site is back button hijacking "
                "under the June 2026 spam policy.",
                fix="Confirm every pushState runs only on genuine navigation.",
                effort="low",
            )
        if a.get("body_robots_noindex"):
            self.add_finding(
                priority="P0",
                title="noindex robots meta inside <body>",
                description="A robots meta tag with noindex sits in the page body. Google "
                "has honoured robots meta tags in the body since March 2026, so this "
                "page is being dropped from the index, even if the <head> says index.",
                fix="Remove the stray tag (often injected by a plugin, widget or "
                "page-builder block).",
                effort="low",
            )
        if a.get("html_bytes", 0) > GOOGLEBOT_HTML_LIMIT:
            mb = round(a["html_bytes"] / 1048576, 1)
            self.add_finding(
                priority="P1",
                title="HTML exceeds Googlebot's 2MB indexing limit",
                description=f"The HTML is {mb}MB uncompressed. Google only indexes the "
                "first 2MB, so content, links and structured data past that point are "
                "invisible to Search.",
                fix="Move inlined data/SVG/CSS out of the HTML, paginate, or trim "
                "hydration payloads.",
                effort="medium",
            )
        if a.get("ai_leak"):
            self.add_finding(
                priority="P1",
                title="Unedited AI output on page (scaled content abuse risk)",
                description="The page contains text like 'As an AI language model' or an "
                "unfilled '[Insert ...]' placeholder. Google's scaled content abuse policy "
                "and the Jan 2025 Quality Rater Guidelines treat unreviewed generated copy "
                "as Lowest quality.",
                fix="Remove the leaked text, then have a person edit the page so it adds "
                "real, specific value.",
                effort="low",
            )
        if a.get("sneaky_redirect"):
            self.add_finding(
                priority="P1",
                title="Conditional JavaScript redirect (sneaky redirect risk)",
                description="An inline script redirects based on the user agent or referrer. "
                "Sending users somewhere different from what Googlebot sees is a sneaky "
                "redirect under Google's spam policies.",
                fix="Remove the conditional redirect. Use a server-side 301 that treats every "
                "visitor the same.",
                effort="low",
            )
        if a.get("hidden_text_words", 0) >= 25:
            self.add_finding(
                priority="P2",
                title="Possible hidden text (verify)",
                description=f"About {a['hidden_text_words']} words of copy sit inside "
                "inline-styled hidden elements (display:none, off-screen or zero font size). "
                "Hidden keyword text is a spam policy violation. Legitimate tabs and "
                "accordions are fine, which is why this needs a human check.",
                fix="Show the copy to users or delete it. Don't keep keyword text only for "
                "crawlers.",
                effort="low",
            )
        if a.get("place_list_max", 0) >= 10:
            self.add_finding(
                priority="P2",
                title="Location list stuffing (doorway / keyword stuffing signal)",
                description=f"A run of {a['place_list_max']} comma-separated place names sits "
                "in the body copy. Google's spam policies name lists of cities and regions "
                "a page tries to rank for as keyword stuffing, and it often goes with "
                "doorway pages.",
                fix="Replace the list with a service-area map or a short sentence, and only "
                "build location pages that carry genuinely local content.",
                effort="low",
            )
        if a.get("top_term_density", 0) > 4:
            self.add_finding(
                # 4-6% can be natural for a product name ("Google Ads"); past 6%
                # it almost never is
                priority="P2" if a["top_term_density"] > 6 else "P3",
                title="Keyword repetition in body copy",
                description=f"'{a['top_term']}' makes up {a['top_term_density']}% of the body "
                "copy. Copy that repeats a keyword (often the place name on a location "
                "page) unnaturally reads as stuffing to both users and Google. Check it "
                "reads naturally aloud.",
                fix="Rewrite for readers: use synonyms and specifics, and say it once where "
                "it matters.",
                effort="medium",
            )
        if a.get("unqualified_affiliate_links"):
            n = len(a["unqualified_affiliate_links"])
            self.add_finding(
                priority="P2",
                title="Affiliate/paid links missing rel=\"sponsored\"",
                description=f"{n} outbound link(s) look like affiliate or tracked partner links "
                "but carry no rel=\"sponsored\" or rel=\"nofollow\". Google's link spam "
                "policy requires paid links to be qualified. Examples: "
                + "; ".join(a["unqualified_affiliate_links"][:3]),
                fix='Add rel="sponsored" to every paid, affiliate or partner link.',
                effort="low",
            )
        filler = a.get("filler_hits", [])
        if len(filler) >= 3:
            self.add_finding(
                priority="P2",
                title="Generic filler phrasing (low-effort content signal)",
                description=f"{len(filler)} stock phrases common in unedited generated copy "
                "(e.g. 'digital landscape', 'unlock the power', 'look no further'). The "
                "Jan 2025 Quality Rater Guidelines rate filler that adds nothing, and "
                "generated content without added value, at the bottom of the scale.",
                fix="Rewrite with specifics only you can give: named clients, numbers, "
                "process, local detail, opinions.",
                effort="medium",
            )
        if a.get("title_stuffed"):
            self.add_finding(
                priority="P2",
                title="Keyword-stuffed title tag",
                description=f"The title '{a['title'][:90]}' repeats terms"
                + (f" ({', '.join(a['title_repeats'])})" if a.get("title_repeats") else "")
                + " or strings keyword fragments together. Google rewrites title links "
                "it judges stuffed or boilerplate, and it's a keyword-stuffing signal.",
                fix="One clear, descriptive title per page: primary topic, one qualifier, "
                "brand.",
                effort="low",
            )
        elif a.get("title_length", 0) > TITLE_MAX:
            self.add_finding(
                priority="P3",
                title="Title likely truncated in results",
                description=f"The title is {a['title_length']} characters. Past about "
                "60 characters Google truncates it, and long titles are more often "
                "rewritten.",
                fix="Front-load the topic and trim to about 50-60 characters.",
                effort="low",
            )
        if a.get("meta_stuffed") or a.get("meta_places", 0) >= 5:
            self.add_finding(
                priority="P2",
                title="Keyword-stuffed meta description",
                description="The meta description repeats keywords or lists locations. "
                "Google ignores descriptions that read as keyword lists and writes its "
                "own snippet, so you lose control of the pitch.",
                fix="Write a one or two sentence summary that sells the click.",
                effort="low",
            )
        else:
            mlen = a.get("meta_description_length", 0)
            if mlen and mlen < META_MIN:
                self.add_finding(
                    priority="P3",
                    title="Meta description too short",
                    description=f"The meta description is {mlen} characters, too short "
                    "to summarise the page, so Google usually replaces it.",
                    fix="Aim for 120-160 characters that summarise the page and why to click.",
                    effort="low",
                )
            elif mlen > META_MAX:
                self.add_finding(
                    priority="P3",
                    title="Meta description likely truncated",
                    description=f"The meta description is {mlen} characters. Google "
                    "sets no length limit, but it truncates the snippet on display, so "
                    "anything past about 160 characters won't be read.",
                    fix="Trim to about 150-160 characters with the key point first.",
                    effort="low",
                )
        if a.get("future_dated"):
            self.add_finding(
                priority="P2",
                title="Structured data dates are in the future",
                description=f"datePublished/dateModified ({a.get('date_published')} / "
                f"{a.get('date_modified')}) is later than today. Google warns against "
                "faking freshness, and a future date erodes trust in the page's dates.",
                fix="Emit real dates from the CMS. Only bump dateModified for substantive "
                "edits.",
                effort="low",
            )
        elif a.get("dates_inverted"):
            self.add_finding(
                priority="P3",
                title="dateModified is earlier than datePublished",
                description="The structured data says the page was modified before it was "
                "published, which suggests templated or made-up dates.",
                fix="Emit the real published and modified dates from the CMS.",
                effort="low",
            )
        if a.get("snippet_blocked"):
            self.add_finding(
                priority="P3",
                title="Snippets suppressed (also removes page from AI Overviews)",
                description="nosnippet or max-snippet:0 is set. Google uses the same "
                "controls for AI Overviews and AI Mode, so this page can't be quoted "
                "there either.",
                fix="Remove it unless the opt-out is deliberate. Use data-nosnippet on "
                "specific blocks instead.",
                effort="low",
            )
        retired = a.get("retired_rich_results", [])
        if retired or a.get("search_action"):
            notes = [RETIRED_RICH_RESULTS[t] for t in retired]
            if a.get("search_action"):
                notes.append(SEARCH_ACTION_NOTE)
            self.add_finding(
                priority="P3",
                title="Markup for retired rich results",
                description="This page carries structured data for features Google no "
                "longer shows ("
                + ", ".join(retired + (["SearchAction"] if a.get("search_action") else []))
                + "). "
                + " ".join(notes)
                + " It's harmless, but don't count on it for SERP features or CTR.",
                fix="Leave it if it's cheap to keep. Put new schema effort into types that "
                "still earn results (Organization, LocalBusiness, Product, Article, "
                "Breadcrumb, Review snippets where eligible).",
                effort="low",
            )
        if a.get("favicon_svg_only"):
            self.add_finding(
                priority="P3",
                title="Favicon is SVG only",
                description="Every declared icon is SVG, which isn't in Google's list of "
                "supported favicon formats, so results may show a generic globe.",
                fix="Also declare a square PNG or ICO favicon (48x48 or a multiple).",
                effort="low",
            )
        if not a.get("has_favicon"):
            self.add_finding(
                priority="P3",
                title="No favicon declared",
                description="There's no <link rel=\"icon\">. Google shows a favicon next "
                "to every result, and a generic globe looks less trustworthy.",
                fix="Add a square favicon (48x48 or a multiple), crawlable and stable.",
                effort="low",
            )
        if a.get("is_home") and not a.get("website_name"):
            self.add_finding(
                priority="P3",
                title="No WebSite site-name markup on homepage",
                description="Google picks the site name shown in results from WebSite "
                "structured data first. Without it Google guesses, sometimes badly.",
                fix='Add WebSite JSON-LD on the homepage with "name" (and '
                '"alternateName" if needed) and "url".',
                effort="low",
            )
