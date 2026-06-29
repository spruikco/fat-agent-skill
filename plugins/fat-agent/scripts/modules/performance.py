"""Performance core audit module.

Analyses HTML for performance signals: document size, render-blocking scripts,
lazy loading, image optimisation hints, inline asset sizes, and resource hints.
Scoring mirrors calculate-score.py's calculate_performance_score.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule


@register_module
class PerformanceModule(AuditModule):
    MODULE_ID = "performance"
    DISPLAY_NAME = "Performance"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        html_size_bytes = len(html.encode("utf-8"))
        html_size_kb = round(html_size_bytes / 1024, 1)

        all_scripts = re.findall(r"<script\s[^>]*>", html, re.IGNORECASE)
        render_blocking = 0
        for tag in all_scripts:
            if re.search(r'src=["\']', tag, re.IGNORECASE):
                has_async = bool(re.search(r"\basync\b", tag, re.IGNORECASE))
                has_defer = bool(re.search(r"\bdefer\b", tag, re.IGNORECASE))
                has_module = bool(
                    re.search(r'type=["\']module["\']', tag, re.IGNORECASE)
                )
                if not (has_async or has_defer or has_module):
                    render_blocking += 1

        imgs = re.findall(r"<img\s[^>]*>", html, re.IGNORECASE)
        images_total = len(imgs)
        images_lazy = sum(
            1
            for img in imgs
            if re.search(r'loading=["\']lazy["\']', img, re.IGNORECASE)
        )
        images_with_srcset = sum(
            1 for img in imgs if re.search(r"srcset=", img, re.IGNORECASE)
        )
        modern_exts = re.compile(r"\.(webp|avif|svg)", re.IGNORECASE)
        images_modern = sum(1 for img in imgs if modern_exts.search(img))
        picture_elements = len(re.findall(r"<picture[\s>]", html, re.IGNORECASE))

        inline_scripts = re.findall(
            r"<script(?:\s[^>]*)?>(.+?)</script>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        inline_script_bytes = sum(
            len(s.encode("utf-8"))
            for s in inline_scripts
            if not re.match(r"\s*\{", s.strip())
        )
        inline_script_kb = round(inline_script_bytes / 1024, 1)

        inline_styles = re.findall(
            r"<style[^>]*>(.+?)</style>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        inline_style_bytes = sum(len(s.encode("utf-8")) for s in inline_styles)
        inline_style_kb = round(inline_style_bytes / 1024, 1)

        has_preconnect = bool(
            re.search(r'<link[^>]*rel=["\']preconnect["\']', html, re.IGNORECASE)
        )
        has_preload = bool(
            re.search(r'<link[^>]*rel=["\']preload["\']', html, re.IGNORECASE)
        )

        return {
            "html_size_kb": html_size_kb,
            "render_blocking_scripts": render_blocking,
            "images_total": images_total,
            "images_lazy_loaded": images_lazy,
            "images_with_srcset": images_with_srcset,
            "images_modern_format": images_modern,
            "picture_elements": picture_elements,
            "inline_script_kb": inline_script_kb,
            "inline_style_kb": inline_style_kb,
            "has_preconnect": has_preconnect,
            "has_preload": has_preload,
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        # html size (15 points)
        html_kb = analysis.get("html_size_kb", 0)
        if html_kb <= 50:
            html_pts = 15
        elif html_kb <= 100:
            html_pts = 12
        elif html_kb <= 200:
            html_pts = 7
        else:
            html_pts = 2
        details["html_size"] = {"score": html_pts, "max": 15}
        total += html_pts

        # render-blocking scripts (15 points)
        blocking = analysis.get("render_blocking_scripts", 0)
        if blocking == 0:
            block_pts = 15
        elif blocking <= 1:
            block_pts = 10
        elif blocking <= 2:
            block_pts = 6
        elif blocking <= 4:
            block_pts = 3
        else:
            block_pts = 0
        details["render_blocking"] = {"score": block_pts, "max": 15}
        total += block_pts

        # image optimisation (20 points)
        img_total = analysis.get("images_total", 0)
        img_pts = 0
        if img_total == 0:
            img_pts = 20
        else:
            modern = analysis.get("images_modern_format", 0)
            all_modern = modern >= img_total
            srcset = analysis.get("images_with_srcset", 0)
            picture = analysis.get("picture_elements", 0)
            responsive = srcset + picture
            if all_modern or responsive >= img_total:
                img_pts += 10
            elif responsive > 0:
                img_pts += round((responsive / img_total) * 10)
            if all_modern:
                img_pts += 10
            elif modern > 0:
                img_pts += round((modern / img_total) * 10)
            else:
                img_pts += 3
        details["image_optimisation"] = {"score": img_pts, "max": 20}
        total += img_pts

        # resource hints (15 points)
        hints = 0
        if analysis.get("has_preconnect"):
            hints += 8
        if analysis.get("has_preload"):
            hints += 7
        details["resource_hints"] = {"score": hints, "max": 15}
        total += hints

        # inline asset size (10 points)
        inline_script_kb = analysis.get("inline_script_kb", 0)
        inline_style_kb = analysis.get("inline_style_kb", 0)
        total_inline = inline_script_kb + inline_style_kb
        if total_inline <= 10:
            inline_pts = 10
        elif total_inline <= 30:
            inline_pts = 7
        elif total_inline <= 50:
            inline_pts = 4
        else:
            inline_pts = 1
        details["inline_assets"] = {"score": inline_pts, "max": 10}
        total += inline_pts

        # lazy loading (10 points)
        lazy = analysis.get("images_lazy_loaded", 0)
        if img_total == 0:
            lazy_pts = 10
        elif img_total <= 1:
            lazy_pts = 10
        else:
            if lazy > 0:
                ratio = lazy / img_total
                lazy_pts = round(ratio * 10)
                lazy_pts = max(lazy_pts, 5)
            else:
                lazy_pts = 3
        details["lazy_loading"] = {"score": lazy_pts, "max": 10}
        total += lazy_pts

        if blocking > 0:
            self.add_finding(
                priority="P1",
                title="Render-blocking scripts detected",
                description=f"{blocking} script(s) without async/defer block rendering.",
                fix="Add async or defer attributes to non-critical scripts.",
                effort="low",
            )

        if not analysis.get("has_preconnect") and not analysis.get("has_preload"):
            self.add_finding(
                priority="P2",
                title="No resource hints found",
                description="No preconnect or preload hints detected.",
                fix="Add <link rel='preconnect'> for critical origins and <link rel='preload'> for key assets.",
                effort="low",
            )

        if html_kb > 200:
            self.add_finding(
                priority="P1",
                title="Large HTML document",
                description=f"HTML is {html_kb}KB. Large documents slow initial parsing.",
                fix="Reduce inline content, move large data to async-loaded resources.",
                effort="high",
            )

        if img_total > 1 and lazy == 0:
            self.add_finding(
                priority="P2",
                title="No lazy-loaded images",
                description=f"{img_total} images found but none use loading='lazy'.",
                fix="Add loading='lazy' to below-the-fold images.",
                effort="low",
            )

        inline_total = inline_script_kb + inline_style_kb
        if inline_total > 30:
            self.add_finding(
                priority="P2",
                title="Large inline scripts/styles",
                description=f"{inline_total:.1f}KB of inline assets detected.",
                fix="Move large inline scripts and styles to external files for caching.",
                effort="medium",
            )

        return {"total": min(total, 100), "max": 100, "details": details}
