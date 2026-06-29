"""Crawlability & indexation-depth audit module (Hobo-parity).

Crawl-management checks detectable from the page (and its robots.txt):

- **robots.txt blocking CSS/JS** — blocked render resources stop Google rendering
  the page correctly (a classic, damaging mistake).
- **Pagination** — crawlable `rel=next`/`?page=` anchors vs JS-only pagination.
- **Faceted / parameter URLs** — sort/filter/session/tracking links that explode
  crawl space and create duplicates.
- **JS-only navigation** — `<a>` without `href` (or `href="javascript:"`/`#`) that
  crawlers can't follow.

robots.txt is fetched (guarded); pass ``robots_txt=`` to analyse() to skip I/O.
Site-wide orphan/click-depth scoring needs a full crawl — drive that from
`crawl.py` / the seo-crawler skill.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request

from modules import register_module
from modules.ai_search import parse_robots
from modules.base import AuditModule

_PARAM_RE = re.compile(
    r"[?&](?:sort|orderby|order|filter|color|colour|size|view|sessionid|sid|"
    r"utm_[a-z]+|ref|fbclid|gclid|price|brand|sortby|page_size|per_page)=",
    re.IGNORECASE,
)


def _asset_paths(html, base):
    assets = []
    for m in re.finditer(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    ):
        assets.append(("css", m.group(1)))
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)', html, re.IGNORECASE):
        assets.append(("js", m.group(1)))
    out = []
    for kind, href in assets:
        p = urllib.parse.urlparse(urllib.parse.urljoin(base or "", href))
        # only same-host assets matter for this site's robots.txt
        if not p.netloc or (base and p.netloc == urllib.parse.urlparse(base).netloc):
            out.append((kind, p.path or "/"))
    return out


def _pattern_to_re(value):
    esc = re.escape(value.strip())
    esc = esc.replace(r"\*", ".*")
    if esc.endswith(r"\$"):
        esc = esc[:-2] + "$"
    return re.compile("^" + esc)


def path_disallowed(rules, path):
    """Googlebot-style: disallowed if a Disallow matches and no longer Allow does."""
    best_dis = best_allow = -1
    for kind, value in rules:
        if not value.strip():
            continue
        m = _pattern_to_re(value).match(path)
        if m:
            length = len(value.rstrip("$"))
            if kind == "disallow":
                best_dis = max(best_dis, length)
            else:
                best_allow = max(best_allow, length)
    return best_dis > best_allow


def _effective_rules(robots_text, agent="googlebot"):
    groups = parse_robots(robots_text or "")
    specific = [r for ag, r in groups if agent in ag]
    if specific:
        return specific[0]
    wildcard = [r for ag, r in groups if "*" in ag]
    return wildcard[0] if wildcard else []


def blocked_assets(robots_text, asset_paths):
    if not robots_text:
        return []
    rules = _effective_rules(robots_text)
    return [(kind, p) for kind, p in asset_paths if path_disallowed(rules, p)]


def pagination_signals(html):
    low = html.lower()
    return {
        "rel_next_prev": bool(re.search(r'rel=["\'](?:next|prev)["\']', low)),
        "page_param_links": bool(re.search(r'href=["\'][^"\']*[?&]page=\d', low)),
        "pagination_block": bool(re.search(r'class=["\'][^"\']*pagination', low)),
        "next_anchor": bool(re.search(r"<a[^>]*>\s*(?:next|»|&raquo;|older)\s*<", low)),
    }


def faceted_links(html):
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    return len({h for h in hrefs if _PARAM_RE.search(h)})


def js_only_nav(html):
    count = 0
    for tag in re.findall(r"<a\b[^>]*>", html, re.IGNORECASE):
        href = re.search(r'href=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        if not href:
            count += 1
        elif (
            href.group(1).strip().lower().startswith(("javascript:", "#"))
            and "onclick" in tag.lower()
        ):
            count += 1
    return count


@register_module
class CrawlabilityModule(AuditModule):
    MODULE_ID = "crawlability"
    DISPLAY_NAME = "Crawlability & Indexation"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def _fetch_robots(self, url, timeout=8):
        try:
            base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
            req = urllib.request.Request(
                base + "/robots.txt", headers={"User-Agent": "fat-agent-crawl/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return (
                    resp.read().decode("utf-8", errors="replace")
                    if resp.status == 200
                    else None
                )
        except Exception:
            return None

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        robots_txt = kwargs.get("robots_txt")
        if robots_txt is None and url:
            robots_txt = self._fetch_robots(url)
        base = (
            "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url)) if url else ""
        )
        blocked = blocked_assets(robots_txt, _asset_paths(html, base))
        return {
            "blocked_assets": blocked,
            "pagination": pagination_signals(html),
            "faceted_link_count": faceted_links(html),
            "js_only_nav": js_only_nav(html),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        render = 40 if not analysis["blocked_assets"] else 0
        details["render_resources"] = {"score": render, "max": 40}
        total += render

        nav = (
            30
            if analysis["js_only_nav"] == 0
            else max(0, 30 - 5 * analysis["js_only_nav"])
        )
        details["crawlable_nav"] = {"score": nav, "max": 30}
        total += nav

        facet = (
            30
            if analysis["faceted_link_count"] < 10
            else (15 if analysis["faceted_link_count"] < 30 else 0)
        )
        details["crawl_space"] = {"score": facet, "max": 30}
        total += facet

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a["blocked_assets"]:
            kinds = ", ".join(sorted({k for k, _ in a["blocked_assets"]}))
            self.add_finding(
                priority="P1",
                title=f"robots.txt blocks render resources ({kinds})",
                description="CSS/JS the page needs are disallowed in robots.txt, so Googlebot can't "
                "render the page as users see it — hurting indexing and ranking.",
                fix="Allow CSS/JS in robots.txt (Google needs to fetch them to render).",
                effort="low",
            )
        if a["js_only_nav"] >= 3:
            self.add_finding(
                priority="P2",
                title="JS-only navigation links (not crawlable)",
                description=f"{a['js_only_nav']} link(s) have no crawlable `href` (javascript:/#/onclick "
                "only). Crawlers follow `<a href>` — JS-only links can leave pages undiscovered.",
                fix="Use real `<a href>` links for navigation; enhance with JS, don't replace the href.",
                effort="medium",
            )
        if a["faceted_link_count"] >= 30:
            self.add_finding(
                priority="P2",
                title="Many faceted / parameter URLs exposed to crawlers",
                description=f"{a['faceted_link_count']} links carry sort/filter/session/tracking "
                "parameters. Crawlable facets explode crawl space and create duplicate URLs.",
                fix="Canonicalise or noindex parameterised variants and avoid linking crawlable "
                "sort/filter combinations (or block them in robots.txt).",
                effort="medium",
            )
        pg = a["pagination"]
        if pg["pagination_block"] and not (
            pg["page_param_links"] or pg["rel_next_prev"] or pg["next_anchor"]
        ):
            self.add_finding(
                priority="P3",
                title="Pagination may not be crawlable",
                description="A pagination UI was detected but no crawlable page links (`?page=`/next "
                "anchors). JS-only pagination can hide deeper pages from crawlers.",
                fix="Ensure each paginated page has a unique crawlable URL with real `<a href>` links.",
                effort="medium",
            )
