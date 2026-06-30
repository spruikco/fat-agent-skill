#!/usr/bin/env python3
"""From-afar schema & local-SEO advisor for fat-agent.

Given nothing but a live URL (or its fetched HTML), this:

1. Classifies the page (home, contact, article, product/PDP, listing/PLP, FAQ),
2. Scrapes business/product signals from the live markup (name, phone, address,
   social profiles, price, availability, ratings, breadcrumbs, …),
3. Works out which Schema.org types the page *should* carry and which are
   already present, and
4. Generates ready-to-paste JSON-LD, pre-populated with whatever it could scrape
   and `REPLACE_*` placeholders for the rest.

It needs no codebase access — everything is derived from the live HTML, so it
works equally well on your own site, a client's, or a prospect's. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------
# low-level extraction helpers (regex over HTML — stdlib only)
# --------------------------------------------------------------------------

_JSON_LD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_SOCIAL_HOSTS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "linkedin.com": "LinkedIn",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
}


def _meta(html, *, prop=None, name=None):
    """Return the content of a <meta property=…> or <meta name=…> tag.

    Quote handling uses a backreference (\\1) so a value containing the other
    quote character (e.g. ``content="Joe's Plumbing"``) is captured in full.
    """
    if prop:
        attr, val = "property", prop
    else:
        attr, val = "name", name
    esc = re.escape(val)
    # attribute before content
    m = re.search(
        r"<meta[^>]+%s=([\"'])%s\1[^>]*content=([\"'])(.*?)\2" % (attr, esc),
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(3).strip()
    # content before attribute
    m = re.search(
        r"<meta[^>]+content=([\"'])(.*?)\1[^>]*%s=([\"'])%s\3" % (attr, esc),
        html,
        re.IGNORECASE,
    )
    return m.group(2).strip() if m else None


def _title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def _first_h1(html):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


def _all_links(html):
    return re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)


def parse_jsonld(html):
    """Return all flattened JSON-LD dicts on the page (incl. @graph)."""
    out = []
    for block in _JSON_LD_RE.findall(html):
        try:
            data = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("@graph"), list):
                out.extend(d for d in item["@graph"] if isinstance(d, dict))
            else:
                out.append(item)
    return out


def present_types(html):
    """Lower-cased set of Schema.org @types already declared on the page."""
    types = set()
    for d in parse_jsonld(html):
        t = d.get("@type")
        for v in t if isinstance(t, list) else [t]:
            if v:
                types.add(str(v).lower())
    return types


def _title_brand(title):
    """First segment of a <title>, split only on a *separator* (` | `, ` - `,
    ` – `) — NOT an intra-word hyphen, so "Mercedes-Benz of Sydney" stays intact."""
    if not title:
        return None
    first = re.split(r"\s+[|–—\-]\s+", title)[0].strip()
    return first if re.search(r"\w", first) else None  # reject bare "-" / "|"


def _site_name(html):
    return (
        _meta(html, prop="og:site_name")
        or _meta(html, name="application-name")
        or _next(d.get("name") for d in parse_jsonld(html) if d.get("name"))
        or _title_brand(_title(html))
        or None
    )


def _next(iterable):
    for v in iterable:
        if v:
            return v
    return None


def _phone(html):
    m = re.search(r'href=["\']tel:([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    for d in parse_jsonld(html):
        if d.get("telephone"):
            return str(d["telephone"])
    return None


def _email(html):
    m = re.search(r'href=["\']mailto:([^"\'?]+)', html, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _logo(html, base):
    logo = _meta(html, prop="og:image") or _meta(html, name="og:image")
    if not logo:
        m = re.search(
            r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']([^"\']+)',
            html,
            re.IGNORECASE,
        )
        logo = m.group(1) if m else None
    if logo and base:
        return urllib.parse.urljoin(base, logo)
    return logo


def _social_profiles(html):
    found = {}
    for href in _all_links(html):
        netloc = urllib.parse.urlparse(href).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        for host, label in _SOCIAL_HOSTS.items():
            # match the actual host, not a substring — so "x.com" doesn't tag
            # netflix.com/dropbox.com, and "facebook.com" doesn't tag a subpath
            if (netloc == host or netloc.endswith("." + host)) and label not in found:
                if "share" in href.lower() or "intent" in href.lower():
                    continue
                found[label] = href.split("?")[0]
    return list(found.values())


def _address_from_jsonld(html):
    for d in parse_jsonld(html):
        addr = d.get("address")
        if isinstance(addr, dict):
            return addr
    return None


def _has_search(html):
    return bool(
        re.search(r'<input[^>]+type=["\']search["\']', html, re.IGNORECASE)
        or re.search(r'role=["\']search["\']', html, re.IGNORECASE)
        or re.search(r'<input[^>]+name=["\'](?:s|q|search)["\']', html, re.IGNORECASE)
    )


def _has_map(html):
    return bool(
        re.search(
            r"google\.com/maps|maps\.google|mapbox|openstreetmap", html, re.IGNORECASE
        )
    )


# --------------------------------------------------------------------------
# product / listing / faq / breadcrumb signal extraction
# --------------------------------------------------------------------------


def _price(html):
    for getter in (
        lambda: _meta(html, prop="product:price:amount"),
        lambda: _meta(html, prop="og:price:amount"),
    ):
        v = getter()
        if v:
            return v
    m = re.search(
        r'itemprop=["\']price["\'][^>]*content=["\']([\d.,]+)', html, re.IGNORECASE
    )
    if m:
        return m.group(1)
    m = re.search(r"[$£€]\s?(\d[\d.,]*)", html)
    return m.group(1) if m else None


def _currency(html):
    """Currency from EXPLICIT signals only.

    Never infer USD from a bare "$" — `$` is near-ubiquitous (jQuery, template
    literals) and would write the wrong currency into paste-ready Offer JSON-LD.
    Falls back to a currency code sitting next to a price, else None (placeholder).
    """
    explicit = (
        _meta(html, prop="product:price:currency")
        or _meta(html, prop="og:price:currency")
        or _next(
            d.get("offers", {}).get("priceCurrency")
            for d in parse_jsonld(html)
            if isinstance(d.get("offers"), dict)
        )
    )
    if explicit:
        return explicit
    # an ISO code adjacent to a number — incl. the common glued form "EUR12.99"
    # (NO \b after the code: there's no boundary between a letter and a digit).
    m = re.search(
        r"\b(USD|AUD|GBP|EUR|CAD|NZD|JPY)\s*\d|\d\s*(USD|AUD|GBP|EUR|CAD|NZD|JPY)\b",
        html,
    )
    if m:
        return m.group(1) or m.group(2)
    return None


def _availability(html):
    low = html.lower()
    if re.search(r"out of stock|sold out|unavailable", low):
        return "https://schema.org/OutOfStock"
    if re.search(r"in stock|add to cart|add to basket|buy now", low):
        return "https://schema.org/InStock"
    return None


def _rating_signals(html):
    """Return (rating_value, review_count) if any review signal is detected."""
    for d in parse_jsonld(html):
        agg = d.get("aggregateRating")
        if isinstance(agg, dict):
            return agg.get("ratingValue"), agg.get("reviewCount") or agg.get(
                "ratingCount"
            )
    m = re.search(r"(\d[\d,]*)\s+(?:reviews|ratings)", html, re.IGNORECASE)
    count = m.group(1).replace(",", "") if m else None
    if count or re.search(
        r'class=["\'][^"\']*(?:rating|stars?|review)', html, re.IGNORECASE
    ):
        return None, count
    return None


def _count_products(html):
    """Rough count of product *cards* on a listing page.

    Counts card-like containers and itemscope Products — not 'add to cart'
    occurrences, which double-count on a single PDP (class + button text).
    """
    signals = [
        len(
            re.findall(
                r'class=["\'][^"\']*product[-_ ]?(?:card|item|tile)',
                html,
                re.IGNORECASE,
            )
        ),
        len(re.findall(r'itemtype=["\'][^"\']*Product', html, re.IGNORECASE)),
    ]
    return max(signals)


def _faq_pairs(html):
    """Extract (question, answer) pairs from <details>/<summary> blocks."""
    pairs = []
    for block in re.findall(
        r"<details[^>]*>(.*?)</details>", html, re.DOTALL | re.IGNORECASE
    ):
        q = re.search(
            r"<summary[^>]*>(.*?)</summary>", block, re.DOTALL | re.IGNORECASE
        )
        if not q:
            continue
        question = re.sub(r"<[^>]+>", "", q.group(1)).strip()
        answer = re.sub(
            r"<[^>]+>",
            "",
            re.sub(
                r"<summary.*?</summary>", "", block, flags=re.DOTALL | re.IGNORECASE
            ),
        ).strip()
        if question:
            pairs.append(
                (question, re.sub(r"\s+", " ", answer)[:300] or "REPLACE_answer")
            )
    return pairs


def _has_faq(html):
    if len(_faq_pairs(html)) >= 2:
        return True
    if re.search(r"frequently asked questions|\bFAQ\b", html, re.IGNORECASE):
        q_headings = re.findall(
            r"<h[2-4][^>]*>([^<]*\?)\s*</h[2-4]>", html, re.IGNORECASE
        )
        return len(q_headings) >= 2
    return False


def _breadcrumb_present(html):
    return bool(
        re.search(r'aria-label=["\']breadcrumb', html, re.IGNORECASE)
        or re.search(r'class=["\'][^"\']*breadcrumb', html, re.IGNORECASE)
        or "breadcrumblist" in present_types(html)
    )


# --------------------------------------------------------------------------
# page classification
# --------------------------------------------------------------------------


def classify(html, url=""):
    """Return the set of page-type labels that apply to this page."""
    path = urllib.parse.urlparse(url).path.lower() if url else ""
    og_type = (_meta(html, prop="og:type") or "").lower()
    types = present_types(html)
    labels = set()

    if path in ("", "/", "/index.html", "/home"):
        labels.add("home")
    if "contact" in path or (_phone(html) and _has_map(html)):
        labels.add("contact")
    if (
        og_type == "article"
        or re.search(r"/blog/|/news/|/article/|/post/", path)
        or "<article" in html.lower()
    ):
        labels.add("article")

    # A STRONG single-product signal (og:type=product, Product schema, /product/
    # path) means PDP even when the page also shows a "related products" grid —
    # otherwise the most important deliverable (Product JSON-LD) is dropped.
    strong_product = bool(
        og_type == "product"
        or "product" in types
        or re.search(r"/product/|/products/[^/]+|/p/|/item/", path)
    )
    listing = not strong_product and bool(
        _count_products(html) >= 2
        or "itemlist" in types
        or re.search(r"/shop/?$|/category/|/collections?/|/products/?$", path)
    )
    product = strong_product or (
        _count_products(html) <= 1
        and bool(re.search(r"add[- ]to[- ]cart", html, re.IGNORECASE))
    )
    if listing:
        labels.add("plp")
    elif product:
        labels.add("pdp")

    if _has_faq(html):
        labels.add("faq")

    # local-business signals
    if _phone(html) and (
        _has_map(html) or _address_from_jsonld(html) or "localbusiness" in types
    ):
        labels.add("local")

    if not labels:
        labels.add("generic")
    return labels


# --------------------------------------------------------------------------
# JSON-LD generators (populated from scraped signals + REPLACE_ placeholders)
# --------------------------------------------------------------------------

_CTX = "https://schema.org"


def _base_url(url):
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.netloc else (url or "REPLACE_site_url")


def gen_organization(sig, local=False):
    org = {
        "@context": _CTX,
        "@type": "LocalBusiness" if local else "Organization",
        "name": sig["name"] or "REPLACE_business_name",
        "url": sig["base"],
    }
    if sig["logo"]:
        org["logo"] = sig["logo"]
        org["image"] = sig["logo"]
    if sig["phone"]:
        org["telephone"] = sig["phone"]
    if sig["email"]:
        org["email"] = sig["email"]
    if local:
        addr = sig["address"] or {}
        org["address"] = {
            "@type": "PostalAddress",
            "streetAddress": addr.get("streetAddress", "REPLACE_street_address"),
            "addressLocality": addr.get("addressLocality", "REPLACE_city"),
            "addressRegion": addr.get("addressRegion", "REPLACE_region"),
            "postalCode": addr.get("postalCode", "REPLACE_postcode"),
            "addressCountry": addr.get("addressCountry", "REPLACE_country_code"),
        }
        org["openingHoursSpecification"] = [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "opens": "REPLACE_09:00",
                "closes": "REPLACE_17:00",
            }
        ]
        org["priceRange"] = "REPLACE_$$"
    if sig["socials"]:
        org["sameAs"] = sig["socials"]
    else:
        org["sameAs"] = ["REPLACE_facebook_url", "REPLACE_instagram_url"]
    return org


def gen_website(sig):
    site = {
        "@context": _CTX,
        "@type": "WebSite",
        "name": sig["name"] or "REPLACE_site_name",
        "url": sig["base"],
    }
    if sig["has_search"]:
        site["potentialAction"] = {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{sig['base']}/?s={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        }
    return site


def gen_breadcrumb(sig):
    return {
        "@context": _CTX,
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": sig["base"]},
            {
                "@type": "ListItem",
                "position": 2,
                "name": "REPLACE_section",
                "item": "REPLACE_section_url",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": sig["h1"] or "REPLACE_current_page",
            },
        ],
    }


def gen_article(sig):
    return {
        "@context": _CTX,
        "@type": "Article",
        "headline": sig["h1"] or sig["title"] or "REPLACE_headline",
        "image": [sig["logo"]] if sig["logo"] else ["REPLACE_image_url"],
        "datePublished": "REPLACE_2026-01-01",
        "dateModified": "REPLACE_2026-01-01",
        "author": {"@type": "Person", "name": "REPLACE_author_name"},
        "publisher": {
            "@type": "Organization",
            "name": sig["name"] or "REPLACE_publisher",
            "logo": {"@type": "ImageObject", "url": sig["logo"] or "REPLACE_logo_url"},
        },
    }


def gen_product(sig):
    offer = {
        "@type": "Offer",
        "url": sig["url"] or sig["base"],
        "priceCurrency": sig["currency"] or "REPLACE_USD",
        "price": sig["price"] or "REPLACE_price",
        "availability": sig["availability"] or "https://schema.org/InStock",
        "itemCondition": "https://schema.org/NewCondition",
    }
    product = {
        "@context": _CTX,
        "@type": "Product",
        "name": sig["product_name"] or sig["h1"] or "REPLACE_product_name",
        "image": [sig["logo"]] if sig["logo"] else ["REPLACE_product_image_url"],
        "description": sig["description"] or "REPLACE_product_description",
        "sku": "REPLACE_sku",
        "brand": {"@type": "Brand", "name": sig["name"] or "REPLACE_brand"},
        "offers": offer,
    }
    rating = sig["rating"]
    if rating is not None:
        rv, rc = rating
        product["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": rv or "REPLACE_rating_value",
            "reviewCount": rc or "REPLACE_review_count",
        }
    return product


def gen_itemlist(sig):
    return {
        "@context": _CTX,
        "@type": "ItemList",
        "name": sig["h1"] or "REPLACE_category_name",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "url": "REPLACE_product_1_url"},
            {"@type": "ListItem", "position": 2, "url": "REPLACE_product_2_url"},
        ],
    }


def gen_faqpage(sig):
    pairs = sig["faq_pairs"] or [
        ("REPLACE_question_1", "REPLACE_answer_1"),
        ("REPLACE_question_2", "REPLACE_answer_2"),
    ]
    return {
        "@context": _CTX,
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }


# --------------------------------------------------------------------------
# recommendation engine
# --------------------------------------------------------------------------


def gather_signals(html, url=""):
    base = _base_url(url)
    return {
        "url": url or base,
        "base": base,
        "name": _site_name(html),
        "title": _title(html),
        "h1": _first_h1(html),
        "logo": _logo(html, base),
        "phone": _phone(html),
        "email": _email(html),
        "address": _address_from_jsonld(html),
        "socials": _social_profiles(html),
        "has_search": _has_search(html),
        "description": _meta(html, name="description")
        or _meta(html, prop="og:description"),
        "product_name": _meta(html, prop="og:title") or _first_h1(html),
        "price": _price(html),
        "currency": _currency(html),
        "availability": _availability(html),
        "rating": _rating_signals(html),
        "faq_pairs": _faq_pairs(html),
    }


def _required_props(jsonld):
    """A type is 'incomplete' if these keys hold REPLACE_ placeholders."""
    return [
        k for k, v in jsonld.items() if isinstance(v, str) and v.startswith("REPLACE_")
    ]


def recommend(html, url=""):
    """Build the full from-afar schema recommendation payload."""
    sig = gather_signals(html, url)
    labels = classify(html, url)
    have = present_types(html)
    recs = []

    def add(type_name, jsonld, priority, reason):
        status = "missing" if type_name.lower() not in have else "incomplete"
        recs.append(
            {
                "type": type_name,
                "priority": priority,
                "status": status,
                "reason": reason,
                "needs_input": _required_props(jsonld),
                "jsonld": jsonld,
            }
        )

    is_local = "local" in labels
    # Site-wide identity (every site benefits)
    add(
        "LocalBusiness" if is_local else "Organization",
        gen_organization(sig, local=is_local),
        "P1",
        "Establishes the business/brand entity for Knowledge Panel and rich results"
        + (" with NAP for local pack eligibility." if is_local else "."),
    )
    if "website" not in have:
        add(
            "WebSite",
            gen_website(sig),
            "P2",
            "Enables sitelinks search box and clarifies the site entity.",
        )

    if "home" not in labels and "breadcrumblist" not in have:
        add(
            "BreadcrumbList",
            gen_breadcrumb(sig),
            "P2",
            "Improves SERP breadcrumb display and crawl hierarchy.",
        )

    if "article" in labels and not (have & {"article", "blogposting", "newsarticle"}):
        add(
            "Article",
            gen_article(sig),
            "P1",
            "Eligible for article rich results and Top Stories.",
        )

    if "pdp" in labels:
        add(
            "Product",
            gen_product(sig),
            "P0" if "product" not in have else "P1",
            "Required for product rich results and Google Merchant free listings "
            "(price, availability, condition, brand, reviews).",
        )

    if "plp" in labels:
        add(
            "ItemList",
            gen_itemlist(sig),
            "P2",
            "Marks up the product grid for carousel/listing rich results.",
        )

    if "faq" in labels and "faqpage" not in have:
        add(
            "FAQPage",
            gen_faqpage(sig),
            "P2",
            "Eligible for FAQ rich results (expandable Q&A in SERP).",
        )

    return {
        "url": sig["url"],
        "page_types": sorted(labels),
        "present_types": sorted(have),
        "signals": {
            k: sig[k]
            for k in (
                "name",
                "phone",
                "email",
                "logo",
                "socials",
                "price",
                "currency",
                "availability",
            )
        },
        "recommendations": recs,
        "merchant_listing": (
            _merchant_gaps(sig, labels, have) if "pdp" in labels else None
        ),
    }


def _merchant_gaps(sig, labels, have):
    """Google Merchant / product rich-result readiness checklist for PDPs."""
    checks = {
        "price": bool(sig["price"]),
        "currency": bool(sig["currency"]),
        "availability": bool(sig["availability"]),
        "product_schema": "product" in have,
        "rating_or_reviews": sig["rating"] is not None,
        "image": bool(sig["logo"]),
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "missing": [k for k, ok in checks.items() if not ok],
    }


# --------------------------------------------------------------------------
# rendering + CLI
# --------------------------------------------------------------------------


def to_html_snippets(payload):
    """Render recommendations as paste-ready <script> blocks."""
    out = []
    for rec in payload["recommendations"]:
        out.append(
            f"<!-- {rec['type']} ({rec['priority']}, {rec['status']}) — {rec['reason']} -->\n"
            '<script type="application/ld+json">\n'
            + json.dumps(rec["jsonld"], indent=2)
            + "\n</script>"
        )
    return "\n\n".join(out)


def _read_html(args):
    if args.fetch:
        req = urllib.request.Request(
            args.url, headers={"User-Agent": "fat-agent-suggest/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    if args.file and args.file != "-":
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def build_parser():
    p = argparse.ArgumentParser(
        description="Suggest Schema.org markup for a page from its live HTML."
    )
    p.add_argument(
        "file",
        nargs="?",
        default="-",
        help="HTML file (default: stdin). Ignored with --fetch.",
    )
    p.add_argument(
        "--url", default="", help="Page URL (used for classification + absolute URLs)"
    )
    p.add_argument(
        "--fetch",
        action="store_true",
        help="Fetch --url over HTTP instead of reading a file/stdin",
    )
    p.add_argument(
        "--format",
        choices=["json", "html"],
        default="json",
        help="Output format (default: json)",
    )
    p.add_argument(
        "--output", default=None, help="Write to this file instead of stdout"
    )
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.fetch and not args.url:
        print("--fetch requires --url", file=sys.stderr)
        sys.exit(2)
    html = _read_html(args)
    payload = recommend(html, args.url)
    text = (
        to_html_snippets(payload)
        if args.format == "html"
        else json.dumps(payload, indent=2)
    )
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Schema suggestions written to {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
