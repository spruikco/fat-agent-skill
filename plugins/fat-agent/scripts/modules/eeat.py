"""E-E-A-T & Trust audit module.

Audits the Experience / Expertise / Authoritativeness / Trustworthiness signals
that modern Google ranking (and the 2024 Content Warehouse leak's authorship and
entity signals) reward — all detectable from the live HTML, no codebase needed:

- author byline / bio / author-page link / `author` in Article schema / Person entity
- trust pages: About, Contact, Privacy, Terms, Editorial policy, Returns/Shipping
- Organization entity: schema with logo, sameAs, contactPoint
- reachable contact info: phone, email, postal address
- outbound citations to authoritative sources
- affiliate / sponsored disclosure
- "reviewed by" / fact-check signals for YMYL trust
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_SOCIAL_RE = re.compile(
    r"facebook\.com|instagram\.com|linkedin\.com|twitter\.com|x\.com|youtube\.com|"
    r"tiktok\.com|pinterest\.com|wikipedia\.org|wikidata\.org",
    re.IGNORECASE,
)

# trust pages -> link-text / href patterns that signal their presence
_TRUST_PAGES = {
    "about": r"about(?:-us)?|who-we-are|our-story",
    "contact": r"contact(?:-us)?|get-in-touch",
    "privacy": r"privacy",
    "terms": r"terms|conditions|legal",
    "editorial": r"editorial|review-process|our-process|methodology|fact-check",
}


def _has_article_context(html):
    """Looks like editorial content (so author/citation findings are relevant)."""
    low = html.lower()
    return bool(
        "<article" in low
        or re.search(r'"@type"\s*:\s*"(article|blogposting|newsarticle)"', low)
        or re.search(r"/blog/|/news/|/article/|/post/", low)
    )


def _author_signals(html):
    low = html.lower()
    byline = bool(
        re.search(r'rel=["\']author["\']', low)
        or re.search(r'class=["\'][^"\']*(?:author|byline)', low)
        or re.search(r'itemprop=["\']author["\']', low)
        or re.search(r">\s*by\s+[A-Z][a-z]+\s+[A-Z][a-z]+", html)
    )
    author_page = bool(re.search(r'href=["\'][^"\']*/author[s]?/', low))
    schema_author = False
    person_entity = False
    for block in _JSON_LD_RE.findall(html):
        bl = block.lower()
        if '"author"' in bl:
            schema_author = True
        if '"@type"' in bl and '"person"' in bl:
            person_entity = True
    return {
        "byline": byline,
        "author_page": author_page,
        "schema_author": schema_author,
        "person_entity": person_entity,
    }


def _trust_pages(html):
    found = {}
    for key, pattern in _TRUST_PAGES.items():
        found[key] = bool(
            re.search(r'href=["\'][^"\']*(?:%s)' % pattern, html, re.IGNORECASE)
            or re.search(r">[^<]*(?:%s)[^<]*</a>" % pattern, html, re.IGNORECASE)
        )
    return found


def _org_entity(html):
    has_org = False
    has_sameas = False
    has_logo = False
    has_contactpoint = False
    for block in _JSON_LD_RE.findall(html):
        bl = block.lower()
        if re.search(r'"@type"\s*:\s*"organization"', bl) or re.search(
            r'"@type"\s*:\s*"localbusiness"', bl
        ):
            has_org = True
        if '"sameas"' in bl:
            has_sameas = True
        if '"logo"' in bl:
            has_logo = True
        if '"contactpoint"' in bl:
            has_contactpoint = True
    return {
        "organization": has_org,
        "sameAs": has_sameas,
        "logo": has_logo,
        "contactPoint": has_contactpoint,
    }


def _contactable(html):
    return {
        "phone": bool(re.search(r'href=["\']tel:', html, re.IGNORECASE)),
        "email": bool(re.search(r'href=["\']mailto:', html, re.IGNORECASE)),
        "address": bool(
            re.search(r"<address[\s>]", html, re.IGNORECASE)
            or re.search(r'"@type"\s*:\s*"postaladdress"', html, re.IGNORECASE)
        ),
    }


def _outbound_citations(html, url=""):
    """Count external links that look like editorial citations (not social/nav)."""
    host = re.sub(r"^https?://", "", url).split("/")[0].lower() if url else ""
    count = 0
    for href in re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE):
        h = href.lower()
        if host and host in h:
            continue
        if _SOCIAL_RE.search(h):
            continue
        count += 1
    return count


def _disclosure(html):
    return bool(
        re.search(
            r"affiliate (?:link|disclosure)|sponsored|advertising disclosure|"
            r"we may earn|commission",
            html,
            re.IGNORECASE,
        )
    )


def _reviewed_by(html):
    return bool(
        re.search(
            r"reviewed by|medically reviewed|fact[- ]checked|expert[- ]reviewed",
            html,
            re.IGNORECASE,
        )
    )


@register_module
class EEATModule(AuditModule):
    MODULE_ID = "eeat"
    DISPLAY_NAME = "E-E-A-T & Trust"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        return {
            "is_article": _has_article_context(html),
            "author": _author_signals(html),
            "trust_pages": _trust_pages(html),
            "org": _org_entity(html),
            "contact": _contactable(html),
            "outbound_citations": _outbound_citations(html, url),
            "disclosure": _disclosure(html),
            "reviewed_by": _reviewed_by(html),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        author = analysis["author"]
        author_pts = 0
        if author["byline"]:
            author_pts += 10
        if author["schema_author"] or author["person_entity"]:
            author_pts += 8
        if author["author_page"]:
            author_pts += 2
        details["authorship"] = {"score": author_pts, "max": 20}
        total += author_pts

        trust = analysis["trust_pages"]
        trust_pts = sum(5 for k in ("about", "contact", "privacy") if trust.get(k))
        trust_pts += 5 if trust.get("editorial") else 0
        trust_pts = min(trust_pts, 20)
        details["trust_pages"] = {"score": trust_pts, "max": 20}
        total += trust_pts

        org = analysis["org"]
        org_pts = (
            (8 if org["organization"] else 0)
            + (6 if org["sameAs"] else 0)
            + (3 if org["logo"] else 0)
            + (3 if org["contactPoint"] else 0)
        )
        details["entity"] = {"score": org_pts, "max": 20}
        total += org_pts

        contact = analysis["contact"]
        contact_pts = sum(
            n
            for n, ok in zip(
                (6, 6, 8), (contact["phone"], contact["email"], contact["address"])
            )
            if ok
        )
        details["contactable"] = {"score": contact_pts, "max": 20}
        total += contact_pts

        misc_pts = 0
        if analysis["outbound_citations"] >= 1:
            misc_pts += 10
        if analysis["disclosure"]:
            misc_pts += 5
        if analysis["reviewed_by"]:
            misc_pts += 5
        details["transparency"] = {"score": misc_pts, "max": 20}
        total += misc_pts

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        author = a["author"]
        if a["is_article"] and not author["byline"]:
            self.add_finding(
                priority="P1",
                title="No author byline on content",
                description="Editorial content has no visible author. In 2026 anonymity is a "
                "ranking liability — Google's quality signals and the leaked authorship "
                "fields reward identifiable expertise.",
                fix="Add a visible author byline linking to an author bio page, and include "
                "the author in Article schema (`author` → `Person` with `sameAs`).",
                effort="medium",
            )
        if a["is_article"] and not (author["schema_author"] or author["person_entity"]):
            self.add_finding(
                priority="P2",
                title="No author markup (Person / Article author)",
                description="No `author`/`Person` structured data found. Author markup connects "
                "content to a real, verifiable entity.",
                fix="Add `author` to the Article schema, referencing a `Person` with `name`, "
                "`url`, `jobTitle`, and `sameAs` (LinkedIn, etc.).",
                effort="low",
            )

        trust = a["trust_pages"]
        missing_trust = [k for k in ("about", "contact", "privacy") if not trust.get(k)]
        if missing_trust:
            self.add_finding(
                priority="P1" if "contact" in missing_trust else "P2",
                title=f"Missing trust page link(s): {', '.join(missing_trust)}",
                description="Core trust pages weren't linked from this page. About/Contact/Privacy "
                "are baseline trust signals (and required for YMYL).",
                fix="Link About, Contact, and Privacy from the global header or footer.",
                effort="low",
            )

        org = a["org"]
        if not org["organization"]:
            self.add_finding(
                priority="P2",
                title="No Organization entity markup",
                description="No `Organization` (or `LocalBusiness`) JSON-LD found. This is the "
                "anchor for your brand's Knowledge Graph entity.",
                fix="Add `Organization` schema with `name`, `url`, `logo`, `sameAs`, and "
                "`contactPoint`.",
                effort="low",
            )
        elif not org["sameAs"]:
            self.add_finding(
                priority="P3",
                title="Organization entity missing sameAs",
                description="`Organization` markup has no `sameAs`. `sameAs` links disambiguate "
                "your brand entity to Google and AI engines.",
                fix="Add `sameAs` pointing to your social profiles and, ideally, "
                "Wikipedia/Wikidata.",
                effort="low",
            )

        if a["is_article"] and a["outbound_citations"] == 0:
            self.add_finding(
                priority="P3",
                title="No outbound citations",
                description="Editorial content cites no external sources. Citing authoritative "
                "sources is an E-E-A-T signal and fuels AI-answer citations.",
                fix="Link to authoritative primary sources where you make factual claims.",
                effort="low",
            )
