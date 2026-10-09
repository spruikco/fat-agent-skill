"""Email Deliverability audit module.

Checks SPF, DKIM, and DMARC DNS records for domains that have contact forms,
helping ensure emails sent from the site are properly authenticated and less
likely to land in spam.
"""

from __future__ import annotations

import re
import subprocess
from urllib.parse import urlparse

from modules import register_module
from modules.base import AuditModule

# Common DKIM selectors. Selectors cannot be listed from DNS, so a miss here
# means "not verifiable", not "missing" (SES, for one, uses random tokens).
_DKIM_SELECTORS = (
    "google",  # Google Workspace
    "selector1",  # Microsoft 365
    "selector2",  # Microsoft 365
    "default",
    "dkim",
    "mail",
    "smtp",
    "k1",  # Mailchimp / Mandrill
    "k2",
    "s1",  # SendGrid
    "s2",
    "mandrill",
    "everlytickey1",
    "everlytickey2",
    "mxvault",
)

# SPF include -> (provider, where its DKIM selector lives)
_SPF_PROVIDER_HINTS = (
    ("amazonses.com", "Amazon SES", "<token>._domainkey CNAMEs to dkim.amazonses.com"),
    ("spf.protection.outlook.com", "Microsoft 365", "selector1/selector2._domainkey"),
    ("_spf.google.com", "Google Workspace", "google._domainkey"),
    ("sendgrid.net", "SendGrid", "s1/s2._domainkey"),
    ("mailgun.org", "Mailgun", "the selector shown in the Mailgun dashboard"),
    ("servers.mcsv.net", "Mailchimp", "k1/k2._domainkey"),
)

_DMARC_POLICY_SCORES: dict[str, int] = {
    "reject": 30,
    "quarantine": 20,
    "none": 10,
}


@register_module
class EmailDeliverabilityModule(AuditModule):
    MODULE_ID = "email_deliverability"
    DISPLAY_NAME = "Email Deliverability"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """Return True when the page has a <form> AND a type=\"email\" input."""
        has_form = bool(re.search(r"<form", html, re.IGNORECASE))
        has_email = bool(re.search(r'type=["\']?email', html, re.IGNORECASE))
        return has_form and has_email

    # ------------------------------------------------------------------
    # analysis (uses dig CLI)
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        domain = self._extract_domain(url)
        contact_form = self.detect(html)

        spf = self._check_spf(domain) if domain else {"found": False}
        dkim = self._check_dkim(domain) if domain else {"found": False}
        dmarc = self._check_dmarc(domain) if domain else {"found": False}

        analysis = {
            "domain": domain,
            "contact_form": contact_form,
            "spf": spf,
            "dkim": dkim,
            "dmarc": dmarc,
        }
        return analysis

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        spf_score = 30 if analysis["spf"].get("found") else 0
        dkim_score = 30 if analysis["dkim"].get("found") else 0

        dmarc_data = analysis["dmarc"]
        if dmarc_data.get("found"):
            policy = dmarc_data.get("policy", "none")
            dmarc_score = _DMARC_POLICY_SCORES.get(policy, 10)
        else:
            dmarc_score = 0

        form_score = 10 if analysis.get("contact_form") else 0

        total = spf_score + dkim_score + dmarc_score + form_score

        # generate findings
        if not analysis["spf"].get("found"):
            self.add_finding(
                priority="P1",
                title="Missing SPF record",
                description="No SPF TXT record was found for this domain. "
                "Without SPF, receiving servers cannot verify that "
                "emails claiming to come from your domain are legitimate.",
                fix="Add a TXT record to your DNS: v=spf1 include:<your-esp> -all",
                effort="low",
            )

        if not analysis["dkim"].get("found"):
            spf_record = (analysis["spf"].get("record") or "").lower()
            hints = [
                f"{name} ({where})"
                for needle, name, where in _SPF_PROVIDER_HINTS
                if needle in spf_record
            ]
            provider = (
                " SPF names " + "; ".join(hints) + ", so check there." if hints else ""
            )
            self.add_finding(
                priority="P3",
                title="DKIM not verifiable from DNS (selectors unknown)",
                description="None of the common DKIM selectors resolved. DKIM "
                "selectors cannot be listed from DNS, so this is not proof DKIM "
                "is missing: Amazon SES signs with random token selectors, Microsoft "
                "365 uses selector1/selector2, Google uses google." + provider,
                fix="Confirm DKIM is enabled in the sending provider's console, or "
                "read the DKIM-Signature header (s= is the selector) of a real email "
                "from this domain and look up <selector>._domainkey.<domain>.",
                effort="low",
            )

        if not dmarc_data.get("found"):
            self.add_finding(
                priority="P1",
                title="Missing DMARC record",
                description="No DMARC record was found at _dmarc.<domain>. "
                "DMARC tells receivers what to do when SPF/DKIM fail.",
                fix="Add a TXT record at _dmarc.<domain>: "
                "v=DMARC1; p=quarantine; rua=mailto:dmarc@<domain>",
                effort="low",
            )
        elif dmarc_data.get("policy") in ("none",):
            self.add_finding(
                priority="P2",
                title="DMARC policy is set to none (weak)",
                description="Your DMARC record uses p=none, which only monitors "
                "but does not reject or quarantine unauthenticated email. "
                "This provides limited protection against spoofing.",
                fix="After monitoring, tighten the policy to p=quarantine or p=reject.",
                effort="low",
            )

        return {
            "total": total,
            "spf": spf_score,
            "dkim": dkim_score,
            "dmarc": dmarc_score,
            "contact_form": form_score,
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
    def _dig_txt(name: str, timeout: int = 5) -> list[str]:
        """Run `dig TXT <name>` and return all TXT record strings."""
        try:
            result = subprocess.run(
                ["dig", "+short", "TXT", name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return []
            records: list[str] = []
            for line in result.stdout.strip().splitlines():
                # dig returns quoted strings, strip them
                cleaned = line.strip().strip('"')
                if cleaned:
                    records.append(cleaned)
            return records
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # No dig on this machine (Windows, minimal containers). Fall back
            # to DNS-over-HTTPS so SPF/DKIM/DMARC are not reported missing
            # when they exist.
            return EmailDeliverabilityModule._doh_txt(name, timeout)

    @staticmethod
    def _doh_txt(name: str, timeout: int = 5) -> list[str]:
        """Resolve TXT records via Google's DNS-over-HTTPS JSON API."""
        import json
        import urllib.parse
        import urllib.request

        url = "https://dns.google/resolve?" + urllib.parse.urlencode({"name": name, "type": "TXT"})
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            return []
        records: list[str] = []
        for ans in data.get("Answer", []) or []:
            if ans.get("type") != 16:
                continue
            # Long TXT records come back as several quoted chunks: join them.
            raw = ans.get("data", "")
            cleaned = "".join(part.strip().strip('"') for part in raw.split('" "'))
            cleaned = cleaned.strip().strip('"')
            if cleaned:
                records.append(cleaned)
        return records

    def _check_spf(self, domain: str) -> dict:
        records = self._dig_txt(domain)
        for rec in records:
            if rec.lower().startswith("v=spf1"):
                return {"found": True, "record": rec}
        return {"found": False}

    def _check_dkim(self, domain: str) -> dict:
        for selector in _DKIM_SELECTORS:
            name = f"{selector}._domainkey.{domain}"
            records = self._dig_txt(name)
            for rec in records:
                if "dkim" in rec.lower() or "k=" in rec.lower() or "p=" in rec.lower():
                    return {"found": True, "selector": selector, "record": rec}
        return {"found": False}

    def _check_dmarc(self, domain: str) -> dict:
        name = f"_dmarc.{domain}"
        records = self._dig_txt(name)
        for rec in records:
            if rec.lower().startswith("v=dmarc1"):
                policy = "none"
                match = re.search(r"p\s*=\s*(\w+)", rec, re.IGNORECASE)
                if match:
                    policy = match.group(1).lower()
                return {"found": True, "record": rec, "policy": policy}
        return {"found": False}
