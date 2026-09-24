"""Security core audit module.

Checks HTML for mixed content, external link safety, and inline script sources.
When response headers are provided, checks HSTS, CSP, X-Frame-Options,
X-Content-Type-Options, Referrer-Policy, and Permissions-Policy.
Scoring mirrors calculate-score.py's calculate_security_score.

Depth checks (findings-only — they never change the score buckets, so parity
with calculate-score.py holds): CSP quality (unsafe-inline / unsafe-eval /
wildcard sources), HSTS quality (max-age / includeSubDomains), Set-Cookie
flags, server version disclosure, Subresource Integrity on cross-origin
scripts, secrets/API keys exposed in the page source, and source-map
references shipped to production.
"""

from __future__ import annotations

import re
import urllib.parse

from modules import register_module
from modules.base import AuditModule

# Secret patterns that should NEVER appear in served HTML/JS. Each entry:
# (label, regex, priority). Google AIza keys are often legitimately public
# (Maps JS) but must be restriction-locked, so they get their own P2 lane.
SECRET_PATTERNS = [
    ("Stripe live secret key", r"\b[sr]k_live_[0-9A-Za-z]{16,}", "P0"),
    ("AWS access key ID", r"\bAKIA[0-9A-Z]{16}\b", "P0"),
    ("GitHub token", r"\b(?:ghp_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,})", "P0"),
    ("Slack token", r"\bxox[bpars]-[0-9A-Za-z-]{10,}", "P0"),
    ("Anthropic API key", r"\bsk-ant-[0-9A-Za-z_-]{20,}", "P0"),
    ("OpenAI project key", r"\bsk-proj-[0-9A-Za-z_-]{20,}", "P0"),
    ("Private key block", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "P0"),
    ("Google API key (verify restrictions)", r"\bAIza[0-9A-Za-z_-]{35}\b", "P2"),
]

# HSTS max-age below ~180 days is treated as weak (preload list requires 1y).
HSTS_MIN_AGE = 15552000


def _parse_csp_weaknesses(csp_value):
    """Return the weaknesses present in a CSP header value."""
    weaknesses = []
    low = (csp_value or "").lower()
    if "'unsafe-inline'" in low:
        weaknesses.append("unsafe-inline")
    if "'unsafe-eval'" in low:
        weaknesses.append("unsafe-eval")
    # A bare * source in default-src / script-src defeats the policy.
    for directive in ("default-src", "script-src"):
        m = re.search(directive + r"\s+([^;]+)", low)
        if m and re.search(r"(?:^|\s)\*(?:\s|$)", m.group(1)):
            weaknesses.append("wildcard-source")
            break
    return weaknesses


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
            rel_val = rel_match.group(1).lower() if rel_match else ""
            # noreferrer implies noopener
            if "noopener" not in rel_val and "noreferrer" not in rel_val:
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

        # --- depth: CSP quality ---
        csp_weaknesses = (
            _parse_csp_weaknesses(h.get("content-security-policy", ""))
            if has_csp
            else []
        )

        # --- depth: HSTS quality ---
        hsts_max_age = None
        hsts_include_subdomains = False
        if has_hsts:
            hsts_value = h.get("strict-transport-security", "")
            m = re.search(r"max-age\s*=\s*(\d+)", hsts_value, re.IGNORECASE)
            if m:
                hsts_max_age = int(m.group(1))
            hsts_include_subdomains = "includesubdomains" in hsts_value.lower()

        # --- depth: Set-Cookie flags ---
        cookie_missing_flags = []
        set_cookie = h.get("set-cookie", "")
        if set_cookie:
            low_cookie = set_cookie.lower()
            for flag in ("secure", "httponly", "samesite"):
                if flag not in low_cookie:
                    cookie_missing_flags.append(flag)

        # --- depth: server version disclosure ---
        server_version_header = ""
        for header_name in ("server", "x-powered-by"):
            value = h.get(header_name, "")
            if re.search(r"\d+\.\d+", value):
                server_version_header = "%s: %s" % (header_name, value)
                break

        # --- depth: SRI on cross-origin scripts ---
        page_host = urllib.parse.urlparse(url).netloc.lower() if url else ""
        scripts_missing_sri = 0
        for tag in re.findall(
            r"<script\s[^>]*src=[\"'][^\"']+[\"'][^>]*>", html, re.IGNORECASE
        ):
            src_m = re.search(r'src=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if not src_m:
                continue
            src = src_m.group(1)
            src_host = urllib.parse.urlparse(
                "https:" + src if src.startswith("//") else src
            ).netloc.lower()
            cross_origin = bool(src_host) and (not page_host or src_host != page_host)
            if cross_origin and "integrity=" not in tag.lower():
                scripts_missing_sri += 1

        # --- depth: secrets in the served source ---
        exposed_secrets = []
        for label, pattern, priority in SECRET_PATTERNS:
            for m in re.finditer(pattern, html):
                token = m.group(0)
                exposed_secrets.append(
                    {
                        "type": label,
                        "priority": priority,
                        # never echo the full credential back into reports
                        "hint": (
                            token[:8] + "…" + token[-4:]
                            if len(token) > 14
                            else token[:6] + "…"
                        ),
                    }
                )

        # --- depth: source maps shipped to production ---
        sourcemap_refs = len(re.findall(r"sourceMappingURL\s*=", html))

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
            "csp_weaknesses": csp_weaknesses,
            "hsts_max_age": hsts_max_age,
            "hsts_include_subdomains": hsts_include_subdomains,
            "cookie_missing_flags": cookie_missing_flags,
            "server_version_header": server_version_header,
            "scripts_missing_sri": scripts_missing_sri,
            "exposed_secrets": exposed_secrets,
            "sourcemap_refs": sourcemap_refs,
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
            self._deep_findings(analysis)
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

        self._deep_findings(analysis)
        return {"total": min(total, 100), "max": 100, "details": details}

    def _deep_findings(self, analysis: dict):
        """Findings-only depth checks — never affect the score buckets."""
        for secret in analysis.get("exposed_secrets", []):
            if secret["priority"] == "P0":
                self.add_finding(
                    priority="P0",
                    title="Secret exposed in page source: %s" % secret["type"],
                    description="A credential matching the %s pattern (%s) is present in "
                    "the served HTML/JS. Anyone who views source has it."
                    % (secret["type"], secret["hint"]),
                    fix="Rotate the credential immediately, then move it server-side "
                    "(env var / secrets manager). Client code should call your own "
                    "backend, never carry live secrets.",
                    effort="medium",
                )
            else:
                self.add_finding(
                    priority="P2",
                    title="Google API key in page source — verify restrictions",
                    description="An AIza… key (%s) ships in the page. Maps/Firebase web "
                    "keys are designed to be public, but only if restricted."
                    % secret["hint"],
                    fix="In Google Cloud Console, lock the key to your HTTP referrers "
                    "and to only the APIs it needs, and set quota alerts.",
                    effort="low",
                )
        if analysis.get("csp_weaknesses"):
            self.add_finding(
                priority="P2",
                title="CSP present but weakened: %s"
                % ", ".join(analysis["csp_weaknesses"]),
                description="The Content-Security-Policy contains directives that "
                "largely defeat its XSS protection.",
                fix="Replace 'unsafe-inline' with nonces or hashes, remove "
                "'unsafe-eval', and enumerate explicit sources instead of *.",
                effort="high",
            )
        # HSTS-quality checks need the depth fields — hand-built legacy analysis
        # dicts (without them) keep their original presence-only behaviour.
        if analysis.get("has_hsts") and "hsts_include_subdomains" in analysis:
            max_age = analysis.get("hsts_max_age")
            if max_age is not None and max_age < HSTS_MIN_AGE:
                self.add_finding(
                    priority="P2",
                    title="HSTS max-age too short (%d seconds)" % max_age,
                    description="Short HSTS windows leave returning visitors open to "
                    "downgrade attacks between visits; the preload list requires one year.",
                    fix="Set Strict-Transport-Security: max-age=31536000; "
                    "includeSubDomains; preload.",
                    effort="low",
                )
            elif not analysis.get("hsts_include_subdomains"):
                self.add_finding(
                    priority="P3",
                    title="HSTS missing includeSubDomains",
                    description="Subdomains are not covered by the HSTS policy, so any "
                    "subdomain can still be downgraded to HTTP.",
                    fix="Add includeSubDomains (and preload once verified) to the "
                    "Strict-Transport-Security header.",
                    effort="low",
                )
        if analysis.get("cookie_missing_flags"):
            self.add_finding(
                priority="P2",
                title="Cookies set without %s"
                % "/".join(analysis["cookie_missing_flags"]),
                description="The Set-Cookie header omits standard hardening flags, "
                "exposing cookies to interception or cross-site sending.",
                fix="Set cookies with Secure; HttpOnly; SameSite=Lax (or Strict) "
                "unless a flag is genuinely incompatible with the cookie's job.",
                effort="low",
            )
        if analysis.get("server_version_header"):
            self.add_finding(
                priority="P3",
                title="Server version disclosed (%s)"
                % analysis["server_version_header"],
                description="Version numbers in Server/X-Powered-By headers hand "
                "attackers a shortcut to known CVEs for that exact version.",
                fix="Suppress the version (nginx server_tokens off; Apache "
                "ServerTokens Prod; remove X-Powered-By in the app/platform config).",
                effort="low",
            )
        sri_missing = analysis.get("scripts_missing_sri", 0)
        if sri_missing:
            self.add_finding(
                priority="P3",
                title="%d cross-origin script(s) without Subresource Integrity"
                % sri_missing,
                description="Third-party scripts load without an integrity hash — if "
                "the CDN or vendor is compromised, the page executes whatever it serves.",
                fix='Add integrity="sha384-…" + crossorigin="anonymous" to static '
                "third-party scripts, or self-host them.",
                effort="medium",
            )
        if analysis.get("sourcemap_refs"):
            self.add_finding(
                priority="P3",
                title="Source maps referenced in production",
                description="sourceMappingURL references ship in the served code — "
                "your unminified source (and any comments/paths in it) is one fetch away.",
                fix="Disable source-map emission in production builds, or block "
                "access to .map files at the edge.",
                effort="low",
            )
