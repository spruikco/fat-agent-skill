import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.local_seo import LocalSEOModule

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_local_business_schema():
    html = '<html><head><script type="application/ld+json">{"@type": "LocalBusiness", "name": "Test"}</script></head><body></body></html>'
    assert LocalSEOModule.detect(html) is True


def test_detect_true_for_restaurant_subtype():
    html = '<html><head><script type="application/ld+json">{"@type": "Restaurant", "name": "Cafe"}</script></head><body></body></html>'
    assert LocalSEOModule.detect(html) is True


def test_detect_true_for_dentist_subtype():
    html = '<html><head><script type="application/ld+json">{"@type": "Dentist", "name": "Dr Smith"}</script></head><body></body></html>'
    assert LocalSEOModule.detect(html) is True


def test_detect_true_for_google_maps_embed():
    html = '<html><body><iframe src="https://www.google.com/maps/embed?pb=abc"></iframe></body></html>'
    assert LocalSEOModule.detect(html) is True


def test_detect_true_for_tel_link():
    html = '<html><body><a href="tel:+441234567890">Call</a></body></html>'
    assert LocalSEOModule.detect(html) is True


def test_detect_false_for_plain_page():
    html = "<html><body><h1>About Us</h1><p>Welcome.</p></body></html>"
    assert LocalSEOModule.detect(html) is False


def test_detect_true_for_fixture():
    html = _load_fixture("local_business.html")
    assert LocalSEOModule.detect(html) is True


def test_detect_false_for_basic_fixture():
    html = _load_fixture("basic.html")
    assert LocalSEOModule.detect(html) is False


# ---------------------------------------------------------------------------
# analyse() tests using fixtures
# ---------------------------------------------------------------------------


def test_analyse_local_business_fixture():
    html = _load_fixture("local_business.html")
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["local_business_schema"] is True
    assert result["nap_in_schema"] is True
    assert result["google_maps"] is True
    assert result["click_to_call"] is True


def test_analyse_basic_fixture_finds_nothing():
    html = _load_fixture("basic.html")
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["local_business_schema"] is False
    assert result["nap_in_schema"] is False
    assert result["google_maps"] is False
    assert result["click_to_call"] is False


def test_analyse_detects_whatsapp_link():
    html = '<html><body><a href="https://wa.me/441234567890">WhatsApp</a></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["whatsapp"] is True


def test_analyse_detects_gbp_link():
    html = '<html><body><a href="https://g.page/mybusiness">Google Profile</a></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["gbp_link"] is True


def test_analyse_detects_gbp_search_link():
    html = '<html><body><a href="https://www.google.com/maps/place/test">View on Maps</a></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["gbp_link"] is True


def test_analyse_detects_opening_hours():
    html = """<html><head><script type="application/ld+json">
    {"@type": "LocalBusiness", "name": "Test", "openingHours": "Mo-Fr 09:00-17:00"}
    </script></head><body></body></html>"""
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["opening_hours"] is True


def test_analyse_detects_opening_hours_specification():
    html = """<html><head><script type="application/ld+json">
    {"@type": "LocalBusiness", "name": "Test", "openingHoursSpecification": [{"@type": "OpeningHoursSpecification"}]}
    </script></head><body></body></html>"""
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["opening_hours"] is True


def test_analyse_detects_service_area():
    html = """<html><head><script type="application/ld+json">
    {"@type": "LocalBusiness", "name": "Test", "areaServed": "London"}
    </script></head><body></body></html>"""
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["service_area"] is True


def test_analyse_detects_service_area_in_html():
    html = '<html><body><div class="service-area">We cover London and Surrey</div></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["service_area"] is True


def test_analyse_detects_review_schema():
    html = """<html><head><script type="application/ld+json">
    {"@type": "LocalBusiness", "name": "Test", "aggregateRating": {"@type": "AggregateRating"}}
    </script></head><body></body></html>"""
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["review_schema"] is True


def test_analyse_detects_review_type():
    html = '<html><head><script type="application/ld+json">{"@type": "Review", "author": "Bob"}</script></head><body></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["review_schema"] is True


def test_analyse_detects_trust_signals():
    html = '<html><body><img alt="Checkatrade approved"></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["trust_signals"] is True


def test_analyse_detects_prominent_cta():
    html = (
        '<html><body><a href="tel:+441234567890" class="btn">Call Now</a></body></html>'
    )
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["prominent_cta"] is True


def test_analyse_detects_cta_get_quote():
    html = "<html><body><button>Get a Quote</button></body></html>"
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["prominent_cta"] is True


def test_analyse_detects_directions_link():
    html = '<html><body><a href="https://maps.google.com/maps/dir/?q=test">Get Directions</a></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["directions_link"] is True


def test_analyse_detects_directions_link_apple():
    html = '<html><body><a href="https://maps.apple.com/?daddr=test">Directions</a></body></html>'
    mod = LocalSEOModule()
    result = mod.analyse(html)
    assert result["directions_link"] is True


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    analysis = {
        "local_business_schema": True,
        "nap_in_schema": True,
        "google_maps": True,
        "click_to_call": True,
        "prominent_cta": True,
        "opening_hours": True,
        "service_area": True,
        "review_schema": True,
        "trust_signals": True,
        "gbp_link": True,
        "whatsapp": True,
        "directions_link": True,
    }
    mod = LocalSEOModule()
    result = mod.score(analysis)
    assert result["total"] == 100
    assert result["local_business_schema"] == 20
    assert result["nap_in_schema"] == 15
    assert result["google_maps"] == 10
    assert result["click_to_call"] == 10
    assert result["prominent_cta"] == 10
    assert result["opening_hours"] == 8
    assert result["service_area"] == 7
    assert result["review_schema"] == 5
    assert result["trust_signals"] == 5
    assert result["gbp_link"] == 5
    assert result["whatsapp"] == 3
    assert result["directions_link"] == 2


def test_score_nothing():
    analysis = {
        "local_business_schema": False,
        "nap_in_schema": False,
        "google_maps": False,
        "click_to_call": False,
        "prominent_cta": False,
        "opening_hours": False,
        "service_area": False,
        "review_schema": False,
        "trust_signals": False,
        "gbp_link": False,
        "whatsapp": False,
        "directions_link": False,
    }
    mod = LocalSEOModule()
    result = mod.score(analysis)
    assert result["total"] == 0


def test_score_generates_findings_for_missing_signals():
    analysis = {
        "local_business_schema": False,
        "nap_in_schema": False,
        "google_maps": False,
        "click_to_call": False,
        "prominent_cta": False,
        "opening_hours": False,
        "service_area": False,
        "review_schema": False,
        "trust_signals": False,
        "gbp_link": False,
        "whatsapp": False,
        "directions_link": False,
    }
    mod = LocalSEOModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert len(titles) > 0
    assert any("schema" in t.lower() or "localbusiness" in t.lower() for t in titles)
    assert any("call" in t.lower() or "tel" in t.lower() for t in titles)


def test_score_no_findings_when_perfect():
    analysis = {
        "local_business_schema": True,
        "nap_in_schema": True,
        "google_maps": True,
        "click_to_call": True,
        "prominent_cta": True,
        "opening_hours": True,
        "service_area": True,
        "review_schema": True,
        "trust_signals": True,
        "gbp_link": True,
        "whatsapp": True,
        "directions_link": True,
    }
    mod = LocalSEOModule()
    mod.score(analysis)
    assert len(mod.findings) == 0


# ---------------------------------------------------------------------------
# module metadata
# ---------------------------------------------------------------------------


def test_module_id():
    assert LocalSEOModule.MODULE_ID == "local_seo"


def test_display_name():
    assert LocalSEOModule.DISPLAY_NAME == "Local SEO"
