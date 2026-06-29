"""Audit profiles - presets for which modules to run."""

PROFILES = {
    "quick": ["seo", "security", "links"],
    "full": [
        "seo",
        "security",
        "accessibility",
        "performance",
        "links",
        "ecommerce",
        "email_deliverability",
        "i18n",
        "local_seo",
        "dns_infra",
        "js_bundle",
        "content_quality",
        "cookie_gdpr",
        "pwa",
        "schema_validator",
        "sitemap",
    ],
    "seo": ["seo", "content_quality", "sitemap", "schema_validator"],
    "security": ["security", "dns_infra", "cookie_gdpr"],
    "local": [
        "seo",
        "security",
        "accessibility",
        "performance",
        "local_seo",
        "email_deliverability",
        "links",
        "content_quality",
        "schema_validator",
    ],
    "ecommerce": [
        "seo",
        "security",
        "accessibility",
        "performance",
        "ecommerce",
        "links",
        "schema_validator",
    ],
    "accessibility": ["accessibility", "performance"],
    "content": ["seo", "content_quality", "links", "sitemap"],
}


def resolve_profile(name: str) -> list[str]:
    """Resolve a profile name to a list of module names.

    Falls back to the 'full' profile if the name is not recognised.
    """
    return PROFILES.get(name, PROFILES["full"])
