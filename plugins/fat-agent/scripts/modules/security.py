"""Security core audit module.

Checks HTML for mixed content, external link safety, and inline script sources.
When response headers are provided, checks HSTS, CSP, X-Frame-Options,
X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
Scoring mirrors calculate-score.py's calculate_security_score.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule


@register_module
class SecurityModule(AuditModule):
    MODULE_ID = "security"
    DISPLAY_NAME = "Security"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        mixed_resources = re.findall(
            r'(?:src|action)=["\']http://[^"\']+["\']',
            html,
            re.IGNORECASE,
        )
        has_mixed_content = len(mixed_resources) > 0

        ext_links = re.findall(
            r"<a\s[^>]*target=[\"']_blank[\"'][^>]*>",
            html,
            re.IGNORECASE,
        )
        ext_total = len(ext_links)
        ext_without_noopener = 0
        for link in ext_links:
            rel_match = re.search(r'rel=["\']([^"\']*)["\']', link, re.IGNORECASE)
            if not rel_match or "noopener" not in rel_match.group(1).lower():
                ext_without_noopener += 1

        inline_event_handlers = len(
            re.findall(r"\bon\w+\s*=\s*[\"']", html, re.IGNORECASE)
        )

        h = {}
        if headers:
            h = {k.lower(): v for k, v in headers.items()}

        has_hsts = "strict-transport-security" in h
        has_csp = "content-security-policy" in h
        has_x_frame_options = "x-frame-options" in h
        has_x_content_type_options = (
            h.get("x-content-type-options", "").lower() == "nosniff"
        )
        has_referrer_policy = "referrer-policy" in h
        has_permissions_policy = "permissions-policy" in h

        return {
            "has_mixed_content": has_mixed_content,
            "mixed_content_count": len(mixed_resources),
            "external_links_total": ext_total,
            "external_links_without_noopener": ext_without_noopener,
            "inline_event_handlers": inline_event_handlers,
            "has_hsts": has_hsts,
            "has_csp": has_csp,
            "has_x_frame_options": has_x_frame_options,
            "has_x_content_type_options": has_x_content_type_options,
            "has_referrer_policy": has_referrer_policy,
            "has_permissions_policy": has_permissions_policy,
            "headers_available": bool(headers),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        # mixed content (10 points)
        mixed = 10 if not analysis.get("has_mixed_content") else 0
        details["mixed_content"] = {"score": mixed, "max": 10}
        total += mixed

        # link safety (5 points)
        link_safety = 5
        ext_total = analysis.get("external_links_total", 0)
        ext_no_opener = analysis.get("external_links_without_noopener", 0)
        if ext_total > 0 and ext_no_opener > 0:
            ratio = (ext_total - ext_no_opener) / ext_total
            link_safety = round(ratio * 5)
        details["link_safety"] = {"score": link_safety, "max": 5}
        total += link_safety

        if not analysis.get("headers_available"):
            if analysis.get("has_mixed_content"):
                self.add_finding(
                    priority="P0",
                    title="Mixed content detected",
                    description=f"Found {analysis.get('mixed_content_count', 0)} HTTP resources on an HTTPS page.",
                    fix="Change all http:// resource URLs to https://.",
                    effort="medium",
                )
            if ext_no_opener > 0:
                self.add_finding(
                    priority="P2",
                    title="External links missing rel='noopener'",
                    description=f"{ext_no_opener} of {ext_total} target='_blank' links lack noopener.",
                    fix="Add rel='noopener noreferrer' to all target='_blank' links.",
                    effort="low",
                )
            return {
                "total": total,
                "max": 100,
                "details": details,
                "note": "No response headers available",
            }

        # csp (30 points)
        csp = 30 if analysis.get("has_csp") else 0
        details["csp"] = {"score": csp, "max": 30}
        total += csp

        # hsts (18 points)
        hsts = 18 if analysis.get("has_hsts") else 0
        details["hsts"] = {"score": hsts, "max": 18}
        total += hsts

        # x-content-type-options (8 points)
        xcto = 8 if analysis.get("has_x_content_type_options") else 0
        details["x_content_type_options"] = {"score": xcto, "max": 8}
        total += xcto

        # x-frame-options (8 points)
        xfo = 8 if analysis.get("has_x_frame_options") else 0
        details["x_frame_options"] = {"score": xfo, "max": 8}
        total += xfo

        # referrer-policy (8 points)
        rp = 8 if analysis.get("has_referrer_policy") else 0
        details["referrer_policy"] = {"score": rp, "max": 8}
        total += rp

        # permissions-policy (13 points)
        pp = 13 if analysis.get("has_permissions_policy") else 0
        details["permissions_policy"] = {"score": pp, "max": 13}
        total += pp

        if analysis.get("has_mixed_content"):
            self.add_finding(
                priority="P0",
                title="Mixed content detected",
                description=f"Found {analysis.get('mixed_content_count', 0)} HTTP resources.",
                fix="Change all http:// resource URLs to https://.",
                effort="medium",
            )
        if not analysis.get("has_csp"):
            self.add_finding(
                priority="P1",
                title="Missing Content-Security-Policy header",
                description="No CSP header found. CSP prevents XSS and data injection attacks.",
                fix="Add a Content-Security-Policy header with appropriate directives.",
                effort="high",
            )
        if not analysis.get("has_hsts"):
            self.add_finding(
                priority="P1",
                title="Missing Strict-Transport-Security header",
                description="No HSTS header found. Without it, connections may be downgraded to HTTP.",
                fix="Add Strict-Transport-Security: max-age=31536000; includeSubDomains; preload.",
                effort="low",
            )
        if ext_no_opener > 0:
            self.add_finding(
                priority="P2",
                title="External links missing rel='noopener'",
                description=f"{ext_no_opener} of {ext_total} target='_blank' links lack noopener.",
                fix="Add rel='noopener noreferrer' to all target='_blank' links.",
                effort="low",
            )
        if not analysis.get("has_x_frame_options"):
            self.add_finding(
                priority="P2",
                title="Missing X-Frame-Options header",
                description="Page may be embedded in iframes on other sites (clickjacking risk).",
                fix="Add X-Frame-Options: DENY or SAMEORIGIN header.",
                effort="low",
            )
        if not analysis.get("has_referrer_policy"):
            self.add_finding(
                priority="P3",
                title="Missing Referrer-Policy header",
                description="No Referrer-Policy header. The browser default may leak referrer data.",
                fix="Add Referrer-Policy: strict-origin-when-cross-origin.",
                effort="low",
            )
        if not analysis.get("has_permissions_policy"):
            self.add_finding(
                priority="P3",
                title="Missing Permissions-Policy header",
                description="No Permissions-Policy header to restrict browser feature access.",
                fix="Add Permissions-Policy to disable unused APIs (camera, microphone, etc.).",
                effort="low",
            )

        return {"total": min(total, 100), "max": 100, "details": details}
