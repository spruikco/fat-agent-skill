"""Local SEO audit module.

Checks for LocalBusiness JSON-LD schema (and subtypes), Google Maps embeds,
click-to-call tel: links, NAP in schema, WhatsApp links, GBP links, service
area, opening hours, review schema, trust signals, prominent CTAs, and
directions links.
"""

from __future__ import annotations

import json
import re

from modules import register_module
from modules.base import AuditModule

_LOCAL_BUSINESS_TYPES = (
    "LocalBusiness",
    "Restaurant",
    "Store",
    "AutoRepair",
    "Plumber",
    "Dentist",
    "Electrician",
    "LegalService",
    "MedicalBusiness",
    "RealEstateAgent",
    "FinancialService",
    "AutomotiveBusiness",
    "HomeAndConstructionBusiness",
    "ProfessionalService",
)

_LOCAL_BUSINESS_RE = re.compile(
    r'"@type"\s*:\s*"(' + "|".join(_LOCAL_BUSINESS_TYPES) + r')"',
    re.IGNORECASE,
)

_GOOGLE_MAPS_RE = re.compile(
    r"google\.com/maps/embed|maps\.googleapis\.com",
    re.IGNORECASE,
)

_TEL_LINK_RE = re.compile(r'href="tel:', re.IGNORECASE)

_WHATSAPP_RE = re.compile(
    r"wa\.me/|api\.whatsapp\.com|whatsapp\.com/send", re.IGNORECASE
)

_GBP_RE = re.compile(
    r"g\.page/|google\.com/maps/place|business\.google\.com", re.IGNORECASE
)

_DIRECTIONS_RE = re.compile(
    r"maps\.google\.com/maps/dir|maps\.apple\.com/\?daddr|google\.com/maps/dir",
    re.IGNORECASE,
)

_TRUST_PATTERNS = [
    re.compile(r"checkatrade", re.IGNORECASE),
    re.compile(r"trustatrader", re.IGNORECASE),
    re.compile(r"trustpilot", re.IGNORECASE),
    re.compile(r"google.reviews?", re.IGNORECASE),
    re.compile(r"accreditation", re.IGNORECASE),
    re.compile(r"certified", re.IGNORECASE),
    re.compile(r"trading.standards", re.IGNORECASE),
    re.compile(r"which.*trusted", re.IGNORECASE),
    re.compile(r"feefo", re.IGNORECASE),
    re.compile(r"reviews\.io", re.IGNORECASE),
]

_CTA_PATTERNS = [
    re.compile(r"call\s+(us|now|today)", re.IGNORECASE),
    re.compile(r"get\s+a?\s*quote", re.IGNORECASE),
    re.compile(r"book\s+(now|online|a\s+)", re.IGNORECASE),
    re.compile(r"request\s+a?\s*callback", re.IGNORECASE),
    re.compile(r"free\s+(estimate|consultation|quote)", re.IGNORECASE),
    re.compile(r"contact\s+us", re.IGNORECASE),
    re.compile(r"enquire\s+now", re.IGNORECASE),
    re.compile(r'class="[^"]*btn[^"]*"[^>]*>.*?call', re.IGNORECASE | re.DOTALL),
    re.compile(r'href="tel:[^"]*"[^>]*class="[^"]*btn', re.IGNORECASE),
]

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


@register_module
class LocalSEOModule(AuditModule):
    MODULE_ID = "local_seo"
    DISPLAY_NAME = "Local SEO"

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------

    @classmethod
    def detect(cls, html: str) -> bool:
        """Return True when local business signals are found."""
        if _LOCAL_BUSINESS_RE.search(html):
            return True
        if _GOOGLE_MAPS_RE.search(html):
            return True
        if _TEL_LINK_RE.search(html):
            return True
        return False

    # ------------------------------------------------------------------
    # analysis
    # ------------------------------------------------------------------

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        schemas = self._extract_schemas(html)

        local_business_schema = any(
            isinstance(s, dict)
            and s.get("@type", "").lower() in [t.lower() for t in _LOCAL_BUSINESS_TYPES]
            for s in schemas
        )

        nap_in_schema = self._check_nap(schemas)
        google_maps = bool(_GOOGLE_MAPS_RE.search(html))
        click_to_call = bool(_TEL_LINK_RE.search(html))
        whatsapp = bool(_WHATSAPP_RE.search(html))
        gbp_link = bool(_GBP_RE.search(html))
        directions_link = bool(_DIRECTIONS_RE.search(html))
        trust_signals = any(p.search(html) for p in _TRUST_PATTERNS)

        prominent_cta = any(p.search(html) for p in _CTA_PATTERNS)

        opening_hours = self._check_opening_hours(schemas, html)
        service_area = self._check_service_area(schemas, html)
        review_schema = self._check_review_schema(schemas)

        return {
            "local_business_schema": local_business_schema,
            "nap_in_schema": nap_in_schema,
            "google_maps": google_maps,
            "click_to_call": click_to_call,
            "prominent_cta": prominent_cta,
            "opening_hours": opening_hours,
            "service_area": service_area,
            "review_schema": review_schema,
            "trust_signals": trust_signals,
            "gbp_link": gbp_link,
            "whatsapp": whatsapp,
            "directions_link": directions_link,
        }

    # ------------------------------------------------------------------
    # scoring
    # ------------------------------------------------------------------

    def score(self, analysis: dict) -> dict:
        weights = {
            "local_business_schema": 20,
            "nap_in_schema": 15,
            "google_maps": 10,
            "click_to_call": 10,
            "prominent_cta": 10,
            "opening_hours": 8,
            "service_area": 7,
            "review_schema": 5,
            "trust_signals": 5,
            "gbp_link": 5,
            "whatsapp": 3,
            "directions_link": 2,
        }

        result = {}
        total = 0
        for key, weight in weights.items():
            pts = weight if analysis.get(key) else 0
            result[key] = pts
            total += pts
        result["total"] = total

        if not analysis.get("local_business_schema"):
            self.add_finding(
                priority="P1",
                title="Missing LocalBusiness structured data",
                description="No LocalBusiness (or subtype) JSON-LD schema was found. "
                "Search engines use this to show rich local results with "
                "address, phone, and opening hours.",
                fix="Add a JSON-LD script with @type LocalBusiness (or a more specific "
                "subtype like Restaurant, Plumber, Dentist) including name, address, "
                "and telephone.",
                effort="medium",
            )

        if analysis.get("local_business_schema") and not analysis.get("nap_in_schema"):
            self.add_finding(
                priority="P1",
                title="LocalBusiness schema missing NAP details",
                description="The LocalBusiness schema was found but is missing Name, "
                "Address, or Phone (NAP). Consistent NAP data is critical "
                "for local search rankings.",
                fix="Add 'name', 'telephone', and 'address' (with @type PostalAddress) "
                "to your LocalBusiness schema.",
                effort="low",
            )

        if not analysis.get("google_maps"):
            self.add_finding(
                priority="P2",
                title="No Google Maps embed found",
                description="No Google Maps embed was detected. An embedded map helps "
                "customers find your location and signals to search engines "
                "that this is a local business.",
                fix="Embed a Google Maps iframe showing your business location.",
                effort="low",
            )

        if not analysis.get("click_to_call"):
            self.add_finding(
                priority="P1",
                title="No click-to-call tel: link found",
                description="No clickable telephone link (tel:) was found. Mobile users "
                "expect to tap to call directly from the page.",
                fix="Add a clickable telephone link, e.g. "
                '<a href="tel:+44XXXXXXXXXX">Call Us</a>.',
                effort="low",
            )

        if not analysis.get("prominent_cta"):
            self.add_finding(
                priority="P2",
                title="No prominent call-to-action found",
                description="No clear CTA like 'Call Now', 'Get a Quote', or 'Book Online' "
                "was detected. Prominent CTAs drive conversions for local "
                "businesses.",
                fix="Add visible CTA buttons with action-oriented text like "
                "'Get a Free Quote' or 'Call Now'.",
                effort="low",
            )

        if not analysis.get("opening_hours"):
            self.add_finding(
                priority="P2",
                title="No opening hours found",
                description="Opening hours were not found in schema markup. Showing hours "
                "in structured data helps appear in local search features.",
                fix="Add 'openingHours' or 'openingHoursSpecification' to your "
                "LocalBusiness schema.",
                effort="low",
            )

        if not analysis.get("service_area"):
            self.add_finding(
                priority="P3",
                title="No service area defined",
                description="No service area information was found in schema or HTML. "
                "Defining areas served helps rank in nearby location searches.",
                fix="Add 'areaServed' to your LocalBusiness schema or include a visible "
                "service area section on the page.",
                effort="low",
            )

        if not analysis.get("review_schema"):
            self.add_finding(
                priority="P2",
                title="No review or rating schema found",
                description="No AggregateRating or Review structured data was detected. "
                "Review markup enables star ratings in search results.",
                fix="Add 'aggregateRating' with @type AggregateRating to your "
                "LocalBusiness schema, or embed Review schema.",
                effort="medium",
            )

        if not analysis.get("trust_signals"):
            self.add_finding(
                priority="P3",
                title="No trust signals detected",
                description="No trust badges or accreditation mentions were found "
                "(Checkatrade, Trustpilot, Trading Standards, etc.). "
                "Trust signals build customer confidence.",
                fix="Display logos or badges from review platforms and trade "
                "accreditation bodies you belong to.",
                effort="low",
            )

        if not analysis.get("gbp_link"):
            self.add_finding(
                priority="P3",
                title="No Google Business Profile link found",
                description="No link to your Google Business Profile was found. "
                "Linking to your GBP encourages reviews and reinforces "
                "local authority.",
                fix="Add a link to your Google Business Profile (g.page/yourbusiness "
                "or Google Maps place link).",
                effort="low",
            )

        if not analysis.get("whatsapp"):
            self.add_finding(
                priority="P3",
                title="No WhatsApp contact link found",
                description="No WhatsApp link was detected. Many local customers "
                "prefer messaging via WhatsApp for quick enquiries.",
                fix="Add a WhatsApp link: "
                '<a href="https://wa.me/44XXXXXXXXXX">WhatsApp Us</a>.',
                effort="low",
            )

        if not analysis.get("directions_link"):
            self.add_finding(
                priority="P3",
                title="No directions link found",
                description="No link to get directions (Google Maps or Apple Maps) was "
                "found. A directions link makes it easier for customers to "
                "visit your premises.",
                fix="Add a 'Get Directions' link pointing to Google Maps or Apple Maps "
                "with your address.",
                effort="low",
            )

        return result

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_schemas(html: str) -> list[dict]:
        """Extract all JSON-LD objects from the page."""
        schemas: list[dict] = []
        for match in _JSON_LD_RE.finditer(html):
            try:
                data = json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, list):
                schemas.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                schemas.append(data)
        return schemas

    @staticmethod
    def _check_nap(schemas: list[dict]) -> bool:
        """Check if any local business schema has name, address, and telephone."""
        types_lower = [t.lower() for t in _LOCAL_BUSINESS_TYPES]
        for s in schemas:
            if s.get("@type", "").lower() in types_lower:
                has_name = bool(s.get("name"))
                has_phone = bool(s.get("telephone"))
                has_address = bool(s.get("address"))
                if has_name and has_phone and has_address:
                    return True
        return False

    @staticmethod
    def _check_opening_hours(schemas: list[dict], html: str) -> bool:
        """Check for opening hours in schema."""
        for s in schemas:
            if s.get("openingHours") or s.get("openingHoursSpecification"):
                return True
        return False

    @staticmethod
    def _check_service_area(schemas: list[dict], html: str) -> bool:
        """Check for service area in schema or HTML."""
        for s in schemas:
            if s.get("areaServed") or s.get("serviceArea"):
                return True
        if re.search(
            r"service.area|areas?.served|areas?.we.cover", html, re.IGNORECASE
        ):
            return True
        return False

    @staticmethod
    def _check_review_schema(schemas: list[dict]) -> bool:
        """Check for review or rating structured data."""
        for s in schemas:
            if s.get("aggregateRating"):
                return True
            schema_type = s.get("@type", "")
            if schema_type in ("Review", "AggregateRating"):
                return True
        return False
