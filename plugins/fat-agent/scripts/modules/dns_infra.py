"""DNS & Infrastructure audit module.

Checks DNSSEC, CAA records, SSL certificate expiry, CDN detection,
and HTTP/2 support for a given URL.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse

from modules import register_module
from modules.base import AuditModule


@register_module
class DNSInfraModule(AuditModule):
    MODULE_ID = "dns_infra"
    DISPLAY_NAME = "DNS & Infrastructure"

    # ------------------------------------------------------------------
    # detection — opt-in only, never auto-detected
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        domain = self._extract_domain(url)
        headers = headers or {}

        ssl_info = (
            self._check_ssl(domain) if domain else {"valid": False, "days_remaining": 0}
        )
        dnssec = self._check_dnssec(domain) if domain else False
        caa = self._check_caa(domain) if domain else False
        cdn_provider = self._detect_cdn(headers)
        http2 = self._check_http2(headers)

        return {
            "domain": domain,
            "ssl_valid": ssl_info.get("valid", False),
            "ssl_days_remaining": ssl_info.get("days_remaining", 0),
            "has_dnssec": dnssec,
            "has_caa_record": caa,
            "has_cdn": cdn_provider is not None,
            "cdn_provider": cdn_provider,
            "http2_support": http2,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        ssl_valid_pts = 25 if analysis.get("ssl_valid") else 0
        ssl_days_pts = (
            15
            if (
                analysis.get("ssl_valid") and analysis.get("ssl_days_remaining", 0) > 30
            )
            else 0
        )
        dnssec_pts = 15 if analysis.get("has_dnssec") else 0
        caa_pts = 15 if analysis.get("has_caa_record") else 0
        cdn_pts = 15 if analysis.get("has_cdn") else 0
        http2_pts = 15 if analysis.get("http2_support") else 0

        total = (
            ssl_valid_pts + ssl_days_pts + dnssec_pts + caa_pts + cdn_pts + http2_pts
        )

        # findings
        if not analysis.get("ssl_valid"):
            self.add_finding(
                priority="P0",
                title="SSL certificate invalid or missing",
                description="The SSL certificate for this domain is either missing, "
                "expired, or otherwise invalid. This will cause browser "
                "warnings and hurt trust and SEO.",
                fix="Install a valid SSL certificate. Use Let's Encrypt for free "
                "automated certificates, or purchase one from your hosting provider.",
                effort="low",
            )
        elif analysis.get("ssl_days_remaining", 0) <= 30:
            self.add_finding(
                priority="P1",
                title="SSL certificate expiring soon",
                description=f"The SSL certificate expires in {analysis.get('ssl_days_remaining', 0)} days. "
                "If it lapses, visitors will see browser security warnings.",
                fix="Renew the SSL certificate before it expires. If using Let's Encrypt, "
                "check that auto-renewal is configured correctly.",
                effort="low",
            )

        if not analysis.get("has_dnssec"):
            self.add_finding(
                priority="P2",
                title="DNSSEC not enabled",
                description="DNSSEC was not detected for this domain. Without DNSSEC, "
                "DNS responses can be spoofed by attackers.",
                fix="Enable DNSSEC through your DNS provider or domain registrar.",
                effort="medium",
            )

        if not analysis.get("has_caa_record"):
            self.add_finding(
                priority="P2",
                title="Missing CAA DNS record",
                description="No CAA record was found. CAA records specify which "
                "certificate authorities are allowed to issue certificates "
                "for your domain, reducing the risk of mis-issuance.",
                fix='Add a CAA DNS record, e.g. 0 issue "letsencrypt.org"',
                effort="low",
            )

        if not analysis.get("has_cdn"):
            self.add_finding(
                priority="P3",
                title="No CDN detected",
                description="No content delivery network was detected. A CDN can "
                "improve page load times for geographically distributed users "
                "and provide DDoS protection.",
                fix="Consider using a CDN such as Cloudflare, Fastly, or CloudFront.",
                effort="medium",
            )

        if not analysis.get("http2_support"):
            self.add_finding(
                priority="P3",
                title="HTTP/2 not detected",
                description="HTTP/2 support was not detected in the response headers. "
                "HTTP/2 enables multiplexing and header compression for "
                "faster page loads.",
                fix="Enable HTTP/2 on your web server or CDN configuration.",
                effort="low",
            )

        return {
            "total": total,
            "ssl_valid": ssl_valid_pts,
            "ssl_days_remaining": ssl_days_pts,
            "has_dnssec": dnssec_pts,
            "has_caa_record": caa_pts,
            "has_cdn": cdn_pts,
            "http2_support": http2_pts,
        }

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        return parsed.hostname or ""

    @staticmethod
    def _check_ssl(domain: str, timeout: int = 5) -> dict:
        """Check SSL certificate validity and days until expiry via openssl s_client."""
        try:
            result = subprocess.run(
                [
                    "openssl",
                    "s_client",
                    "-connect",
                    f"{domain}:443",
                    "-servername",
                    domain,
                ],
                input="",
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            cert_text = result.stdout

            # extract expiry date from the certificate
            date_result = subprocess.run(
                ["openssl", "x509", "-noout", "-enddate"],
                input=cert_text,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if date_result.returncode != 0:
                return {"valid": False, "days_remaining": 0}

            match = re.search(r"notAfter=(.+)", date_result.stdout)
            if not match:
                return {"valid": False, "days_remaining": 0}

            expiry_str = match.group(1).strip()
            expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            expiry = expiry.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            days_remaining = (expiry - now).days

            return {
                "valid": days_remaining > 0,
                "days_remaining": max(days_remaining, 0),
            }
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return {"valid": False, "days_remaining": 0}

    @staticmethod
    def _check_dnssec(domain: str, timeout: int = 5) -> bool:
        """Check for DNSSEC by looking for the ad flag or RRSIG records."""
        try:
            result = subprocess.run(
                ["dig", "+dnssec", "+short", domain],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return False
            output = result.stdout.lower()
            return "rrsig" in output
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _check_caa(domain: str, timeout: int = 5) -> bool:
        """Check for CAA DNS records."""
        try:
            result = subprocess.run(
                ["dig", "+short", "CAA", domain],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return False
            return bool(result.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _detect_cdn(headers: dict | None) -> str | None:
        """Detect CDN provider from HTTP response headers."""
        if not headers:
            return None

        lower_headers = {k.lower(): v for k, v in headers.items()}

        if "cf-ray" in lower_headers:
            return "Cloudflare"

        if "x-amz-cf-id" in lower_headers:
            return "CloudFront"

        if "x-served-by" in lower_headers or "x-cache" in lower_headers:
            server = lower_headers.get("server", "").lower()
            if server != "akamaighost":
                return "Fastly"

        server_val = lower_headers.get("server", "")
        if server_val == "AkamaiGHost" or server_val.lower() == "akamaighost":
            return "Akamai"

        if "x-cdn" in lower_headers:
            return lower_headers["x-cdn"]

        return None

    @staticmethod
    def _check_http2(headers: dict | None) -> bool:
        """Detect HTTP/2 support from response headers or protocol indicators."""
        if not headers:
            return False
        lower_headers = {k.lower(): v for k, v in headers.items()}
        if lower_headers.get("http-version", "").startswith("2"):
            return True
        if "alt-svc" in lower_headers:
            alt_svc = lower_headers["alt-svc"].lower()
            if "h2" in alt_svc:
                return True
        return False
