"""Cookie & GDPR compliance audit module.

Checks for consent management platforms, privacy policy links, cookie policy
links, consent-before-tracking behaviour, and data controller information.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

_FORM_RE = re.compile(r"<form", re.IGNORECASE)
_COOKIE_RE = re.compile(r"document\.cookie|set-cookie|cookie", re.IGNORECASE)
_ANALYTICS_RE = re.compile(
    r"google-analytics|googletagmanager|gtag|analytics\.js|fbevents\.js"
    r"|hotjar|clarity\.ms|segment\.com|plausible|matomo|piwik",
    re.IGNORECASE,
)

_CONSENT_BANNERS = {
    "cookiebot": re.compile(r"cookiebot|Cookiebot", re.IGNORECASE),
    "onetrust": re.compile(r"onetrust|OneTrust|optanon", re.IGNORECASE),
    "cookieyes": re.compile(r"cookieyes|CookieYes", re.IGNORECASE),
    "termly": re.compile(r"termly\.io|Termly", re.IGNORECASE),
    "iubenda": re.compile(r"iubenda", re.IGNORECASE),
    "trustarc": re.compile(r"trustarc|TrustArc|truste", re.IGNORECASE),
    "osano": re.compile(r"osano", re.IGNORECASE),
    "complianz": re.compile(r"complianz|cmplz", re.IGNORECASE),
    "quantcast_choice": re.compile(
        r"quantcast|QuantcastChoice|quantcast-choice", re.IGNORECASE
    ),
}

_PRIVACY_LINK_RE = re.compile(r'href="[^"]*privacy[^"]*"', re.IGNORECASE)

_COOKIE_POLICY_RE = re.compile(r'href="[^"]*cookie[- _]?policy[^"]*"', re.IGNORECASE)

_GDPR_META_RE = re.compile(r"gdpr|data-protection|datenschutz|rgpd", re.IGNORECASE)

_DATA_CONTROLLER_RE = re.compile(
    r"data\s+controller|data\s+processor|data\s+protection\s+officer|DPO",
    re.IGNORECASE,
)

_CONSENT_BEFORE_TRACKING_RE = re.compile(
    r"data-cookie-consent|data-consent|cookie_consent|cookieConsent"
    r"|consent.*required|__consent|data-requires-consent",
    re.IGNORECASE,
)


@register_module
class CookieGDPRModule(AuditModule):
    MODULE_ID = "cookie_gdpr"
    DISPLAY_NAME = "Cookie & GDPR Compliance"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """True if site has forms, cookies, or analytics scripts."""
        if _FORM_RE.search(html):
            return True
        if _COOKIE_RE.search(html):
            return True
        if _ANALYTICS_RE.search(html):
            return True
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        detected_banners = []
        for name, pattern in _CONSENT_BANNERS.items():
            if pattern.search(html):
                detected_banners.append(name)

        has_consent_banner = len(detected_banners) > 0
        has_privacy_policy_link = bool(_PRIVACY_LINK_RE.search(html))
        has_cookie_policy = bool(_COOKIE_POLICY_RE.search(html))
        has_gdpr_meta = bool(_GDPR_META_RE.search(html))
        has_data_controller_info = bool(_DATA_CONTROLLER_RE.search(html))
        consent_before_tracking = bool(_CONSENT_BEFORE_TRACKING_RE.search(html))

        return {
            "has_consent_banner": has_consent_banner,
            "detected_banners": detected_banners,
            "has_privacy_policy_link": has_privacy_policy_link,
            "has_cookie_policy": has_cookie_policy,
            "has_gdpr_meta": has_gdpr_meta,
            "has_data_controller_info": has_data_controller_info,
            "consent_before_tracking": consent_before_tracking,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        weights = {
            "has_consent_banner": 30,
            "has_privacy_policy_link": 25,
            "has_cookie_policy": 20,
            "consent_before_tracking": 15,
            "has_data_controller_info": 10,
        }

        result = {}
        total = 0
        for key, weight in weights.items():
            pts = weight if analysis.get(key) else 0
            result[key] = pts
            total += pts
        result["total"] = total

        if not analysis.get("has_consent_banner"):
            self.add_finding(
                priority="P0",
                title="No cookie consent banner detected",
                description="No consent management platform (Cookiebot, OneTrust, "
                "CookieYes, etc.) was found. GDPR and ePrivacy regulations "
                "require explicit consent before setting non-essential cookies.",
                fix="Implement a cookie consent banner using a CMP such as Cookiebot, "
                "OneTrust, or CookieYes.",
                effort="medium",
            )

        if not analysis.get("has_privacy_policy_link"):
            self.add_finding(
                priority="P0",
                title="No privacy policy link found",
                description="No link to a privacy policy was detected. GDPR Article 13 "
                "requires a clear link to the privacy policy on every page.",
                fix="Add a link to your privacy policy in the footer of every page.",
                effort="low",
            )

        if not analysis.get("has_cookie_policy"):
            self.add_finding(
                priority="P1",
                title="No cookie policy link found",
                description="No dedicated cookie policy link was found. A cookie policy "
                "explaining what cookies are set and why is a regulatory "
                "requirement in many jurisdictions.",
                fix="Create a cookie policy page and link to it from your footer "
                "and cookie banner.",
                effort="medium",
            )

        if not analysis.get("consent_before_tracking"):
            self.add_finding(
                priority="P1",
                title="Tracking may load before consent",
                description="No evidence of consent-gating on tracking scripts was found. "
                "Analytics and marketing scripts should only fire after the "
                "user grants consent.",
                fix="Ensure tracking scripts use data-consent attributes or are "
                "loaded conditionally via your CMP.",
                effort="medium",
            )

        if not analysis.get("has_data_controller_info"):
            self.add_finding(
                priority="P2",
                title="No data controller information found",
                description="No mention of a data controller, data processor, or DPO was "
                "found. GDPR requires identifying the data controller.",
                fix="Include data controller details in your privacy policy and "
                "consider mentioning a DPO if applicable.",
                effort="low",
            )

        return result
