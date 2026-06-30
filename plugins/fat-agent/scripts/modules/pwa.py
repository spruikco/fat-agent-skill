"""PWA readiness audit module.

Checks for web app manifest, theme colour, apple touch icon, service worker
registration, and viewport meta tag.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

_MANIFEST_RE = re.compile(r'<link[^>]*rel=["\']manifest["\'][^>]*>', re.IGNORECASE)

_THEME_COLOR_RE = re.compile(
    r'<meta[^>]*name=["\']theme-color["\'][^>]*>', re.IGNORECASE
)

_APPLE_TOUCH_ICON_RE = re.compile(
    r'<link[^>]*rel=["\']apple-touch-icon["\'][^>]*>', re.IGNORECASE
)

_SERVICE_WORKER_RE = re.compile(
    r"navigator\.serviceWorker\.register|serviceWorker\.register"
    r"|workbox|sw\.js|service-worker\.js",
    re.IGNORECASE,
)

_VIEWPORT_RE = re.compile(r'<meta[^>]*name=["\']viewport["\'][^>]*>', re.IGNORECASE)


@register_module
class PWAModule(AuditModule):
    MODULE_ID = "pwa"
    DISPLAY_NAME = "PWA Readiness"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """True if a manifest link or service worker reference is found."""
        if _MANIFEST_RE.search(html):
            return True
        if _SERVICE_WORKER_RE.search(html):
            return True
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        has_manifest = bool(_MANIFEST_RE.search(html))
        has_theme_color = bool(_THEME_COLOR_RE.search(html))
        has_apple_touch_icon = bool(_APPLE_TOUCH_ICON_RE.search(html))
        has_service_worker = bool(_SERVICE_WORKER_RE.search(html))
        has_viewport = bool(_VIEWPORT_RE.search(html))

        return {
            "has_manifest": has_manifest,
            "has_theme_color": has_theme_color,
            "has_apple_touch_icon": has_apple_touch_icon,
            "has_service_worker": has_service_worker,
            "has_viewport": has_viewport,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        weights = {
            "has_manifest": 30,
            "has_theme_color": 15,
            "has_apple_touch_icon": 15,
            "has_service_worker": 25,
            "has_viewport": 15,
        }

        result = {}
        total = 0
        for key, weight in weights.items():
            pts = weight if analysis.get(key) else 0
            result[key] = pts
            total += pts
        result["total"] = total

        if not analysis.get("has_manifest"):
            self.add_finding(
                priority="P3",
                title="No web app manifest found",
                description="No <link rel='manifest'> was detected. A web app manifest "
                "enables PWA installability — relevant only if you want an installable "
                "app experience; most marketing/content sites don't need one.",
                fix="Create a manifest.json (or manifest.webmanifest) and add "
                "<link rel='manifest' href='/manifest.json'> to the <head>.",
                effort="low",
            )

        if not analysis.get("has_theme_color"):
            self.add_finding(
                priority="P2",
                title="No theme-color meta tag found",
                description="No <meta name='theme-color'> was detected. The theme colour "
                "customises the browser toolbar and task-switcher appearance.",
                fix="Add <meta name='theme-color' content='#HEXCOLOR'> to the <head>.",
                effort="low",
            )

        if not analysis.get("has_apple_touch_icon"):
            self.add_finding(
                priority="P2",
                title="No Apple touch icon found",
                description="No <link rel='apple-touch-icon'> was detected. iOS uses this "
                "icon when adding the site to the home screen.",
                fix="Add <link rel='apple-touch-icon' href='/apple-touch-icon.png'> "
                "with a 180x180 PNG.",
                effort="low",
            )

        if not analysis.get("has_service_worker"):
            self.add_finding(
                priority="P1",
                title="No service worker registration found",
                description="No service worker registration was detected. A service worker "
                "enables offline support, push notifications, and background sync.",
                fix="Register a service worker in your main JS, e.g. "
                "navigator.serviceWorker.register('/sw.js').",
                effort="medium",
            )

        if not analysis.get("has_viewport"):
            self.add_finding(
                priority="P1",
                title="No viewport meta tag found",
                description="No <meta name='viewport'> was detected. A viewport meta tag "
                "is essential for responsive design and mobile usability.",
                fix="Add <meta name='viewport' content='width=device-width, "
                "initial-scale=1'> to the <head>.",
                effort="low",
            )

        return result
