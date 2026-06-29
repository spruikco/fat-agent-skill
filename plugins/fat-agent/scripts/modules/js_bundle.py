"""JS Bundle Analysis audit module.

HTML-level JavaScript analysis: counts external scripts, detects heavy
libraries, measures inline script size, identifies bundler patterns,
and checks for async/defer and module usage.
"""

from __future__ import annotations

import re

from modules import register_module
from modules.base import AuditModule

# regex patterns

_SCRIPT_TAG_RE = re.compile(
    r"<script\b([^>]*)(?:>(.*?)</script>|/>)",
    re.IGNORECASE | re.DOTALL,
)

_SRC_RE = re.compile(r'\bsrc\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_ASYNC_RE = re.compile(r"\basync\b", re.IGNORECASE)
_DEFER_RE = re.compile(r"\bdefer\b", re.IGNORECASE)
_TYPE_MODULE_RE = re.compile(r'\btype\s*=\s*["\']module["\']', re.IGNORECASE)

# heavy library detection patterns (url-based)
_HEAVY_LIBS: list[tuple[str, re.Pattern]] = [
    ("moment", re.compile(r"[/\.]moment(?:\.min)?\.js", re.IGNORECASE)),
    # match full lodash but not lodash-es, lodash/fp, lodash.get etc.
    ("lodash", re.compile(r"[/\.]lodash(?:\.min)?\.js", re.IGNORECASE)),
    ("jquery", re.compile(r"[/\.]jquery(?:[.-]\d)?[^/]*\.js", re.IGNORECASE)),
    (
        "bootstrap.js",
        re.compile(r"[/\.]bootstrap(?:\.bundle)?(?:\.min)?\.js", re.IGNORECASE),
    ),
]

# bundler detection patterns (applied to src attributes)
_WEBPACK_RE = re.compile(r"\.chunk\.js", re.IGNORECASE)
_VITE_RE = re.compile(r"/assets/[^/]+-[A-Za-z0-9_-]{6,}\.js", re.IGNORECASE)
_PARCEL_RE = re.compile(r"/[^/]+\.[a-f0-9]{8}\.js", re.IGNORECASE)


@register_module
class JSBundleModule(AuditModule):
    MODULE_ID = "js_bundle"
    DISPLAY_NAME = "JS Bundle Analysis"

    @classmethod
    def detect(cls, html: str) -> bool:
        return bool(re.search(r"<script[\s>]", html, re.IGNORECASE))

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        external_script_count = 0
        scripts_with_async_or_defer = 0
        scripts_without_async_or_defer = 0
        module_script_count = 0
        inline_script_total_chars = 0
        heavy_libraries: list[str] = []
        bundler_detected: list[str] = []
        all_srcs: list[str] = []

        for m in _SCRIPT_TAG_RE.finditer(html):
            attrs = m.group(1)
            body = m.group(2) or ""

            src_m = _SRC_RE.search(attrs)

            if src_m:
                src = src_m.group(1)
                external_script_count += 1
                all_srcs.append(src)

                # async/defer
                has_async = bool(_ASYNC_RE.search(attrs))
                has_defer = bool(_DEFER_RE.search(attrs))
                if has_async or has_defer:
                    scripts_with_async_or_defer += 1
                else:
                    scripts_without_async_or_defer += 1

                # module type check
                if _TYPE_MODULE_RE.search(attrs):
                    module_script_count += 1

                # heavy library check
                for lib_name, pattern in _HEAVY_LIBS:
                    if lib_name not in heavy_libraries and pattern.search(src):
                        heavy_libraries.append(lib_name)

            else:
                # inline script
                inline_script_total_chars += len(body.strip()) if body else 0

        # bundler detection from all src values
        webpack_found = any(_WEBPACK_RE.search(s) for s in all_srcs)
        vite_found = any(_VITE_RE.search(s) for s in all_srcs)
        parcel_found = any(_PARCEL_RE.search(s) for s in all_srcs)

        if webpack_found:
            bundler_detected.append("webpack")
        if vite_found:
            bundler_detected.append("vite")
        if parcel_found and not webpack_found and not vite_found:
            bundler_detected.append("parcel")

        return {
            "external_script_count": external_script_count,
            "scripts_with_async_or_defer": scripts_with_async_or_defer,
            "scripts_without_async_or_defer": scripts_without_async_or_defer,
            "module_script_count": module_script_count,
            "inline_script_total_chars": inline_script_total_chars,
            "heavy_libraries": heavy_libraries,
            "bundler_detected": bundler_detected,
        }

    def score(self, analysis: dict) -> dict:
        ext_count = analysis.get("external_script_count", 0)
        heavy_libs = analysis.get("heavy_libraries", [])
        with_ad = analysis.get("scripts_with_async_or_defer", 0)
        without_ad = analysis.get("scripts_without_async_or_defer", 0)
        module_count = analysis.get("module_script_count", 0)
        inline_chars = analysis.get("inline_script_total_chars", 0)
        bundler = analysis.get("bundler_detected", [])

        # scoring criteria
        reasonable_script_count = 20 if ext_count <= 15 else 0
        no_heavy_libraries = 20 if len(heavy_libs) == 0 else 0

        total_ext = with_ad + without_ad
        if total_ext == 0:
            scripts_have_async_or_defer = 20
        elif without_ad == 0:
            scripts_have_async_or_defer = 20
        else:
            scripts_have_async_or_defer = 0

        uses_modern_modules = 15 if module_count > 0 else 0
        no_large_inline_scripts = 15 if inline_chars < 10000 else 0
        uses_bundler = 10 if len(bundler) > 0 else 0

        total = (
            reasonable_script_count
            + no_heavy_libraries
            + scripts_have_async_or_defer
            + uses_modern_modules
            + no_large_inline_scripts
            + uses_bundler
        )

        # generate findings
        if heavy_libs:
            self.add_finding(
                priority="P1",
                title="Heavy JavaScript libraries detected",
                description=(
                    f"Found {len(heavy_libs)} heavy library/libraries loaded: "
                    f"{', '.join(heavy_libs)}. These significantly increase page "
                    "weight and load time."
                ),
                fix="Replace heavy libraries with modern lighter alternatives "
                "(e.g. date-fns instead of moment.js, native JS instead of "
                "jQuery, lodash-es with tree shaking instead of full lodash).",
                effort="medium",
            )

        if ext_count > 15:
            self.add_finding(
                priority="P2",
                title="Too many external scripts",
                description=(
                    f"Found {ext_count} external script tags. Each additional "
                    "request adds latency, especially on slow connections."
                ),
                fix="Bundle scripts together using a build tool (webpack, Vite, "
                "esbuild) to reduce the number of HTTP requests.",
                effort="medium",
            )

        if without_ad > 0:
            self.add_finding(
                priority="P2",
                title="Scripts missing async or defer attributes",
                description=(
                    f"{without_ad} external script(s) lack async or defer "
                    "attributes. These scripts block HTML parsing and delay "
                    "page rendering."
                ),
                fix="Add async or defer to script tags that do not need to "
                "execute synchronously during page parse.",
                effort="low",
            )

        if module_count == 0 and ext_count > 0:
            self.add_finding(
                priority="P3",
                title="No ES module scripts detected",
                description=(
                    'No <script type="module"> tags found. ES modules enable '
                    "tree shaking and modern browser optimizations."
                ),
                fix='Migrate to ES modules with type="module" on script tags.',
                effort="medium",
            )

        if inline_chars >= 10000:
            self.add_finding(
                priority="P2",
                title="Large inline script content",
                description=(
                    f"Inline scripts total {inline_chars:,} characters "
                    f"({inline_chars // 1024}KB). Large inline scripts cannot "
                    "be cached by the browser."
                ),
                fix="Move large inline scripts to external files so they can "
                "be cached and loaded asynchronously.",
                effort="low",
            )

        if not bundler and ext_count > 1:
            self.add_finding(
                priority="P3",
                title="No bundler detected",
                description=(
                    "No evidence of a JavaScript bundler (webpack, Vite, Parcel) "
                    "was found. Bundlers optimize delivery through code splitting, "
                    "tree shaking, and minification."
                ),
                fix="Use a modern bundler like Vite or esbuild to optimize "
                "JavaScript delivery.",
                effort="high",
            )

        return {
            "total": total,
            "reasonable_script_count": reasonable_script_count,
            "no_heavy_libraries": no_heavy_libraries,
            "scripts_have_async_or_defer": scripts_have_async_or_defer,
            "uses_modern_modules": uses_modern_modules,
            "no_large_inline_scripts": no_large_inline_scripts,
            "uses_bundler": uses_bundler,
        }
