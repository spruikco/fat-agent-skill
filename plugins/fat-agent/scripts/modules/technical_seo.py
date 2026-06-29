"""Technical SEO depth audit module.

Header- and DOM-level technical checks that sit beneath the core SEO module and
are fully detectable from afar:

- `X-Robots-Tag` HTTP header (a header-level noindex the meta-tag check misses)
- canonical host consistency (www vs non-www, http vs https, foreign host)
- meta-refresh redirects (use a 301 instead)
- intrusive interstitial / pop-up heuristics (a page-experience demotion)
- next-gen image adoption (WebP/AVIF) and explicit image dimensions (CLS)

Redirect-chain depth and soft-404 detection need multi-request following and are
driven from SKILL.md rather than this single-response module.
"""

from __future__ import annotations

import re
import urllib.parse

from modules import register_module
from modules.base import AuditModule


def _header(headers, name):
    if not headers:
        return ""
    name = name.lower()
    for k, v in headers.items():
        if k.lower() == name:
            return v or ""
    return ""


def canonical_host_issue(html, url):
    """Return a description if the canonical points at a different host/scheme."""
    if not url:
        return None
    m = re.search(
        r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
            html,
            re.IGNORECASE,
        )
    if not m:
        return None
    canon = m.group(1).strip()
    if canon.startswith("/") or not re.match(r"https?://", canon):
        return None  # relative/self canonical
    cu, pu = urllib.parse.urlparse(canon), urllib.parse.urlparse(url)
    if cu.scheme != pu.scheme and pu.scheme:
        return f"Canonical scheme ({cu.scheme}) differs from the page ({pu.scheme})."
    ch, ph = cu.netloc.lower(), pu.netloc.lower()
    if ph and ch != ph:
        if ch.lstrip("www.") == ph.lstrip("www.") and "www." in (ch + ph):
            return (
                f"Canonical host '{ch}' differs from page host '{ph}' (www vs non-www)."
            )
        return f"Canonical points to a different host: '{ch}' vs page '{ph}'."
    return None


def interstitial_signals(html):
    low = html.lower()
    hits = re.findall(
        r'class=["\'][^"\']*(?:modal|popup|pop-up|interstitial|overlay|newsletter-?(?:modal|popup)|'
        r"subscribe-?(?:modal|popup)|lightbox|gdpr-?wall|paywall)",
        low,
    )
    fixed_fullscreen = bool(
        re.search(r"position:\s*fixed[^}]*(?:width:\s*100|inset:\s*0|top:\s*0)", low)
    )
    return {"count": len(hits), "fixed_fullscreen": fixed_fullscreen}


def image_signals(html):
    imgs = re.findall(r"<img\b[^>]*>", html, re.IGNORECASE)
    total = len(imgs)
    legacy = next_gen = missing_dims = 0
    for tag in imgs:
        src = ""
        m = re.search(r'src=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if m:
            src = m.group(1).lower()
        if re.search(r"\.(?:jpg|jpeg|png)(?:\?|$)", src):
            legacy += 1
        if re.search(r"\.(?:webp|avif)(?:\?|$)", src):
            next_gen += 1
        has_w = re.search(r"\bwidth=", tag, re.IGNORECASE)
        has_h = re.search(r"\bheight=", tag, re.IGNORECASE)
        if not (has_w and has_h):
            missing_dims += 1
    has_picture_nextgen = bool(
        re.search(r'<source[^>]+type=["\']image/(?:webp|avif)', html, re.IGNORECASE)
    )
    return {
        "total": total,
        "legacy": legacy,
        "next_gen": next_gen or (1 if has_picture_nextgen else 0),
        "missing_dims": missing_dims,
        "has_picture_nextgen": has_picture_nextgen,
    }


@register_module
class TechnicalSEOModule(AuditModule):
    MODULE_ID = "technical_seo"
    DISPLAY_NAME = "Technical SEO"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        x_robots = _header(headers, "x-robots-tag").lower()
        return {
            "x_robots_tag": x_robots,
            "x_robots_noindex": "noindex" in x_robots,
            "canonical_host_issue": canonical_host_issue(html, url),
            "meta_refresh": bool(
                re.search(
                    r'<meta[^>]+http-equiv=["\']refresh["\']', html, re.IGNORECASE
                )
            ),
            "interstitial": interstitial_signals(html),
            "images": image_signals(html),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        indexability = 0 if analysis["x_robots_noindex"] else 30
        details["indexability"] = {"score": indexability, "max": 30}
        total += indexability

        canon = 0 if analysis["canonical_host_issue"] else 20
        details["canonical_consistency"] = {"score": canon, "max": 20}
        total += canon

        redirects = 0 if analysis["meta_refresh"] else 15
        details["redirects"] = {"score": redirects, "max": 15}
        total += redirects

        inter = analysis["interstitial"]
        ux = 15 if inter["count"] == 0 else (7 if inter["count"] == 1 else 0)
        details["page_experience"] = {"score": ux, "max": 15}
        total += ux

        img = analysis["images"]
        img_pts = 20
        if img["total"]:
            if img["legacy"] and not img["next_gen"]:
                img_pts -= 10
            if img["missing_dims"]:
                img_pts -= 10
        img_pts = max(0, img_pts)
        details["images"] = {"score": img_pts, "max": 20}
        total += img_pts

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a["x_robots_noindex"]:
            self.add_finding(
                priority="P0",
                title="Header-level noindex (X-Robots-Tag)",
                description="The HTTP response sends `X-Robots-Tag: noindex`, removing this page "
                "from search — and it's invisible to a meta-tag-only check.",
                fix="Remove `noindex` from the `X-Robots-Tag` response header if this page "
                "should rank.",
                effort="low",
            )
        if a["canonical_host_issue"]:
            self.add_finding(
                priority="P1",
                title="Canonical points to a different host/scheme",
                description=a["canonical_host_issue"]
                + " Split host/scheme canonicals fragment ranking signals.",
                fix="Make canonicals absolute and consistent on one host+scheme, and 301 the "
                "other variants to it.",
                effort="medium",
            )
        if a["meta_refresh"]:
            self.add_finding(
                priority="P2",
                title="Meta-refresh redirect in use",
                description="A `<meta http-equiv=refresh>` redirect was found. These are slow and "
                "pass signals poorly versus an HTTP 301.",
                fix="Replace meta-refresh with a server-side 301 redirect.",
                effort="low",
            )
        inter = a["interstitial"]
        if inter["count"] >= 1 and inter["fixed_fullscreen"]:
            self.add_finding(
                priority="P2",
                title="Possible intrusive interstitial / pop-up",
                description="A full-screen fixed overlay (modal/pop-up/paywall pattern) was "
                "detected. Intrusive interstitials are a confirmed page-experience demotion on "
                "mobile.",
                fix="Avoid full-screen interstitials on entry; use a non-blocking banner or a "
                "smaller, dismissible prompt.",
                effort="medium",
            )
        img = a["images"]
        if img["total"] and img["legacy"] and not img["next_gen"]:
            self.add_finding(
                priority="P2",
                title="No next-gen image formats",
                description=f"{img['legacy']} legacy JPEG/PNG image(s) and no WebP/AVIF. Next-gen "
                "formats cut bytes substantially and help LCP.",
                fix="Serve WebP/AVIF (via `<picture>` or your CDN/image pipeline).",
                effort="medium",
            )
        if img["total"] and img["missing_dims"]:
            self.add_finding(
                priority="P3",
                title="Images missing width/height (CLS risk)",
                description=f"{img['missing_dims']} image(s) lack explicit width/height, which can "
                "cause layout shift (CLS).",
                fix="Add intrinsic `width` and `height` attributes (or CSS `aspect-ratio`) to "
                "images.",
                effort="low",
            )
