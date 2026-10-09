import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.schema_validator import SchemaValidatorModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_true_for_json_ld():
    html = """<html><head>
    <script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Acme"}</script>
    </head><body></body></html>"""
    assert SchemaValidatorModule.detect(html) is True


def test_detect_false_for_no_json_ld():
    html = "<html><body><h1>No structured data</h1></body></html>"
    assert SchemaValidatorModule.detect(html) is False


# ---------------------------------------------------------------------------
# analyse() tests
# ---------------------------------------------------------------------------


def test_analyse_valid_organization():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"Acme","url":"https://acme.com"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_structured_data"] is True
    assert result["valid_json"] is True
    assert result["has_context"] is True
    assert result["known_types"] is True
    assert result["has_required_props"] is True
    assert result["no_duplicate_types"] is True
    assert "Organization" in result["types_found"]


def test_analyse_invalid_json():
    html = """<html><head>
    <script type="application/ld+json">{bad json here}</script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_structured_data"] is True
    assert result["valid_json"] is False


def test_analyse_missing_context():
    html = """<html><head>
    <script type="application/ld+json">
    {"@type":"Organization","name":"Acme","url":"https://acme.com"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_context"] is False


def test_analyse_unknown_type():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"FictionalWidget","name":"Widget"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["known_types"] is False


def test_analyse_missing_required_props():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Article"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_required_props"] is False


def test_analyse_duplicate_types():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"A","url":"https://a.com"}
    </script>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"B","url":"https://b.com"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["no_duplicate_types"] is False


def test_analyse_multiple_distinct_types():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Organization","name":"Acme","url":"https://acme.com"}
    </script>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"WebSite","name":"Acme Site"}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["no_duplicate_types"] is True
    assert result["known_types"] is True


def test_analyse_graph_structure():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
        {"@type":"Organization","name":"Acme","url":"https://acme.com"},
        {"@type":"WebSite","name":"Acme Site"}
    ]}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_structured_data"] is True
    assert result["known_types"] is True
    assert result["parsed_count"] == 2


def test_analyse_faq_page():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
        {"@type":"Question","name":"What?","acceptedAnswer":{"@type":"Answer","text":"This."}}
    ]}
    </script>
    </head><body></body></html>"""
    mod = SchemaValidatorModule()
    result = mod.analyse(html)
    assert result["has_required_props"] is True
    assert "FAQPage" in result["types_found"]


# ---------------------------------------------------------------------------
# score() tests
# ---------------------------------------------------------------------------


def test_score_perfect():
    mod = SchemaValidatorModule()
    analysis = {
        "has_structured_data": True,
        "valid_json": True,
        "has_context": True,
        "known_types": True,
        "has_required_props": True,
        "no_duplicate_types": True,
    }
    result = mod.score(analysis)
    assert result["total"] == 100
    assert len(mod.findings) == 0


def test_score_zero():
    mod = SchemaValidatorModule()
    analysis = {
        "has_structured_data": False,
        "valid_json": False,
        "has_context": False,
        "known_types": False,
        "has_required_props": False,
        "no_duplicate_types": False,
    }
    result = mod.score(analysis)
    assert result["total"] == 0
    assert len(mod.findings) > 0


def test_score_weights():
    mod = SchemaValidatorModule()
    analysis = {
        "has_structured_data": True,
        "valid_json": True,
        "has_context": False,
        "known_types": True,
        "has_required_props": False,
        "no_duplicate_types": True,
    }
    result = mod.score(analysis)
    assert result["has_structured_data"] == 20
    assert result["valid_json"] == 20
    assert result["has_context"] == 0
    assert result["known_types"] == 15
    assert result["has_required_props"] == 0
    assert result["no_duplicate_types"] == 10
    assert result["total"] == 65


# ---------------------------------------------------------------------------
# regression: valid schema.org types flagged as unknown (txsports.com.au)
# ---------------------------------------------------------------------------


def test_sports_and_local_business_subtypes_are_known():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"SportsActivityLocation","name":"TX Sports"},
      {"@type":"SportsTeam","name":"Corio FC"},
      {"@type":"SportsOrganization","name":"League"},
      {"@type":"SportingGoodsStore","name":"Shop"},
      {"@type":["Store","ProfessionalService"],"name":"Both"},
      {"@type":"https://schema.org/ClothingStore","name":"Prefixed"}
    ]}
    </script></head><body></body></html>"""
    result = SchemaValidatorModule().analyse(html)
    assert result["known_types"] is True


def test_made_up_type_still_unknown():
    html = """<html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"SportsShopThing","name":"X"}
    </script></head><body></body></html>"""
    assert SchemaValidatorModule().analyse(html)["known_types"] is False


# ---------------------------------------------------------------------------
# BreadcrumbList: every ListItem except the last needs an item URL
# ---------------------------------------------------------------------------


def _crumbs(elements):
    import json

    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }
    html = (
        '<html><head><script type="application/ld+json">'
        + json.dumps(data)
        + "</script></head><body></body></html>"
    )
    mod = SchemaValidatorModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    return analysis, [f for f in mod.findings if "BreadcrumbList" in f["title"]]


def test_breadcrumb_missing_item_flagged():
    analysis, found = _crumbs(
        [
            {"@type": "ListItem", "position": 1, "name": "Home"},
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Jerseys",
                "item": "https://e.com/jerseys",
            },
            {"@type": "ListItem", "position": 3, "name": "Corio FC Jersey"},
        ]
    )
    assert analysis["breadcrumb_missing_item"] == ["Home"]
    assert len(found) == 1 and found[0]["priority"] == "P2"


def test_breadcrumb_last_item_may_omit_url():
    analysis, found = _crumbs(
        [
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Jerseys",
                "item": {"@id": "https://e.com/jerseys"},
            },
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": "https://e.com/",
            },
            {"@type": "ListItem", "position": 3, "name": "Corio FC Jersey"},
        ]
    )
    assert analysis["breadcrumb_missing_item"] == []
    assert found == []
