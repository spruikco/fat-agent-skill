import re

_REGISTRY: dict[str, type] = {}

CORE_MODULES = {"seo", "security", "accessibility", "performance"}

SITE_TYPE_MODULES: dict[str, list[str]] = {
    "ecommerce": ["ecommerce"],
    "local_business": ["local_seo"],
    "saas": [],
    "blog": [],
    "portfolio": [],
    "web_app": [],
    "landing_page": ["local_seo"],
    "marketing": ["local_seo"],
}

DETECTION_SIGNALS: dict[str, list[re.Pattern]] = {
    "ecommerce": [
        re.compile(r"add-to-cart", re.IGNORECASE),
        re.compile(r"shopping-cart", re.IGNORECASE),
        re.compile(r'"@type"\s*:\s*"Product"', re.IGNORECASE),
        re.compile(r"product-price", re.IGNORECASE),
        re.compile(r"data-product-id", re.IGNORECASE),
        re.compile(r"shopify", re.IGNORECASE),
        re.compile(r"woocommerce", re.IGNORECASE),
    ],
    "i18n": [
        re.compile(r"hreflang=", re.IGNORECASE),
        re.compile(r"lang-selector", re.IGNORECASE),
        re.compile(r"language-switcher", re.IGNORECASE),
    ],
    "local_seo": [
        re.compile(
            r'"@type"\s*:\s*"(LocalBusiness|Restaurant|Store|AutoRepair|Plumber|'
            r"Dentist|Electrician|LegalService|MedicalBusiness|RealEstateAgent|"
            r"FinancialService|AutomotiveBusiness|HomeAndConstructionBusiness|"
            r'ProfessionalService)"',
            re.IGNORECASE,
        ),
        re.compile(r"google\.com/maps/embed", re.IGNORECASE),
        re.compile(r"maps\.googleapis\.com", re.IGNORECASE),
        re.compile(r'href="tel:', re.IGNORECASE),
        re.compile(r"service-area", re.IGNORECASE),
    ],
    "email_deliverability": [
        re.compile(r"<form", re.IGNORECASE),
        re.compile(r"contact-form", re.IGNORECASE),
        re.compile(r'type="email"', re.IGNORECASE),
    ],
}


def register_module(cls):
    """Decorator that registers an AuditModule subclass in the registry."""
    _REGISTRY[cls.MODULE_ID] = cls
    return cls


def detect_modules(
    html: str,
    site_type: str | None = None,
    force_enable: list[str] | None = None,
    force_disable: list[str] | None = None,
) -> list[str]:
    """Detect which modules should run for the given HTML.

    Returns a sorted list of module IDs.
    """
    enabled: set[str] = set(CORE_MODULES)

    # links module is universally useful
    enabled.add("links")

    # auto-detect from html signals
    for module_id, patterns in DETECTION_SIGNALS.items():
        for pattern in patterns:
            if pattern.search(html):
                enabled.add(module_id)
                break

    # add modules based on site type hint
    if site_type and site_type in SITE_TYPE_MODULES:
        for module_id in SITE_TYPE_MODULES[site_type]:
            enabled.add(module_id)

    # apply overrides
    if force_enable:
        for module_id in force_enable:
            enabled.add(module_id)

    if force_disable:
        for module_id in force_disable:
            enabled.discard(module_id)

    return sorted(enabled)


def get_module(module_id: str) -> type | None:
    """Return the registered class for a module ID, or None."""
    return _REGISTRY.get(module_id)


def list_all_modules() -> list[dict]:
    """Return metadata for all registered modules."""
    return [
        {
            "id": cls.MODULE_ID,
            "name": cls.DISPLAY_NAME,
            "core": cls.MODULE_ID in CORE_MODULES,
        }
        for cls in _REGISTRY.values()
    ]


# import submodules to trigger @register_module decorators
from modules import (  # noqa: E402, F401
    seo,
    security,
    accessibility,
    performance,
    local_seo,
    ecommerce,
    email_deliverability,
    i18n,
    links,
    dns_infra,
    js_bundle,
    sitemap,
    content_quality,
    cookie_gdpr,
    pwa,
    schema_validator,
)
