import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.content_quality import ContentQualityModule


def _words(n: int) -> str:
    """Generate n words of body text."""
    base = "the quick brown fox jumps over the lazy dog and runs across the field "
    repeated = base * ((n // 12) + 1)
    return " ".join(repeated.split()[:n])


def _page(body: str, title: str = "Test Page", h1: str = "Test Page") -> str:
    return (
        f"<html><head><title>{title}</title></head>"
        f"<body><h1>{h1}</h1>{body}</body></html>"
    )


# ---------------------------------------------------------------------------
# word count
# ---------------------------------------------------------------------------


def test_thin_content_flagged():
    html = _page(f"<p>{_words(50)}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["word_count"] < 300
    scores = mod.score(analysis)
    assert scores["adequate_word_count"] == 0
    assert any(f["title"] == "Thin content detected" for f in mod.findings)


def test_adequate_content_scores():
    html = _page(f"<p>{_words(350)}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["word_count"] >= 300
    scores = mod.score(analysis)
    assert scores["adequate_word_count"] == 25


# ---------------------------------------------------------------------------
# placeholder text
# ---------------------------------------------------------------------------


def test_lorem_ipsum_detected():
    html = _page("<p>Lorem ipsum dolor sit amet consectetur adipiscing elit.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["has_placeholder"] is True
    scores = mod.score(analysis)
    assert scores["no_placeholder_text"] == 0
    assert any(f["priority"] == "P0" for f in mod.findings)


def test_placeholder_text_variant():
    html = _page("<p>Your text here is where we start.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["has_placeholder"] is True


def test_no_placeholder_scores():
    html = _page(f"<p>{_words(350)}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["has_placeholder"] is False
    scores = mod.score(analysis)
    assert scores["no_placeholder_text"] == 20


# ---------------------------------------------------------------------------
# title / h1 overlap
# ---------------------------------------------------------------------------


def test_title_h1_overlap_present():
    html = _page(
        f"<p>{_words(350)}</p>",
        title="Professional Plumbing Services",
        h1="Plumbing Services in London",
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["title_h1_overlap"] is True
    scores = mod.score(analysis)
    assert scores["title_h1_overlap"] == 15


def test_title_h1_no_overlap():
    html = _page(
        f"<p>{_words(350)}</p>",
        title="Welcome to Our Website",
        h1="Contact Information",
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["title_h1_overlap"] is False
    scores = mod.score(analysis)
    assert scores["title_h1_overlap"] == 0


# ---------------------------------------------------------------------------
# readability
# ---------------------------------------------------------------------------


def test_readability_reasonable_grade():
    sentences = (
        "The company provides excellent services to all customers. "
        "We have been in business for over twenty years. "
        "Our team of experts is ready to help you today. "
        "Customer satisfaction is our top priority always. "
    )
    body = sentences * 20
    html = _page(f"<p>{body}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["fk_grade"] is not None
    scores = mod.score(analysis)
    if 6.0 <= analysis["fk_grade"] <= 14.0:
        assert scores["good_readability"] == 15


def test_readability_none_for_short_text():
    html = _page("<p>Short text here.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["fk_grade"] is None


# ---------------------------------------------------------------------------
# empty paragraphs
# ---------------------------------------------------------------------------


def test_empty_paragraphs_detected():
    html = _page(f"<p>{_words(350)}</p><p>   </p><p>&nbsp;</p><p></p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["empty_paragraphs"] == 3
    scores = mod.score(analysis)
    assert scores["no_empty_paragraphs"] == 0


def test_no_empty_paragraphs():
    html = _page(f"<p>{_words(350)}</p><p>Real content here.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["empty_paragraphs"] == 0
    scores = mod.score(analysis)
    assert scores["no_empty_paragraphs"] == 10


# ---------------------------------------------------------------------------
# heading-to-content ratio
# ---------------------------------------------------------------------------


def test_heading_ratio_bad():
    headings = "".join(f"<h2>Section {i}</h2><p>Short.</p>" for i in range(10))
    html = _page(headings)
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["heading_ratio_ok"] is False
    scores = mod.score(analysis)
    assert scores["reasonable_heading_ratio"] == 0


def test_heading_ratio_good():
    sections = "".join(f"<h2>Section {i}</h2><p>{_words(80)}</p>" for i in range(3))
    html = _page(sections)
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["heading_ratio_ok"] is True
    scores = mod.score(analysis)
    assert scores["reasonable_heading_ratio"] == 5


# ---------------------------------------------------------------------------
# copyright year
# ---------------------------------------------------------------------------


def test_current_copyright_year():
    year = datetime.now().year
    html = _page(f"<p>{_words(350)}</p><footer>&copy; {year} Acme Ltd</footer>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["copyright_year"] == year
    assert analysis["copyright_current"] is True
    scores = mod.score(analysis)
    assert scores["current_copyright"] == 10


def test_outdated_copyright_year():
    html = _page(f"<p>{_words(350)}</p><footer>&copy; 2019 Acme Ltd</footer>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["copyright_year"] == 2019
    assert analysis["copyright_current"] is False
    scores = mod.score(analysis)
    assert scores["current_copyright"] == 0
    assert any("Outdated copyright" in f["title"] for f in mod.findings)


def test_no_copyright():
    html = _page(f"<p>{_words(350)}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["copyright_year"] is None


# ---------------------------------------------------------------------------
# duplicate title / meta description
# ---------------------------------------------------------------------------


def test_duplicate_title_meta_description():
    html = (
        "<html><head><title>Acme Services</title>"
        '<meta name="description" content="Acme Services">'
        f"</head><body><h1>Acme Services</h1><p>{_words(350)}</p></body></html>"
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["duplicate_title_desc"] is True
    mod.score(analysis)
    assert any("identical" in f["title"].lower() for f in mod.findings)


def test_distinct_title_meta_description():
    html = (
        "<html><head><title>Acme Services</title>"
        '<meta name="description" content="We provide top-quality services.">'
        f"</head><body><h1>Acme Services</h1><p>{_words(350)}</p></body></html>"
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["duplicate_title_desc"] is False


# ---------------------------------------------------------------------------
# nav/header/footer text excluded from body count
# ---------------------------------------------------------------------------


def test_nav_text_excluded_from_word_count():
    nav_words = _words(400)
    html = (
        "<html><head><title>Test</title></head><body>"
        f"<nav>{nav_words}</nav>"
        "<h1>Test</h1><p>Only five words here now.</p>"
        "</body></html>"
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    assert analysis["word_count"] < 50


# ---------------------------------------------------------------------------
# scoring totals
# ---------------------------------------------------------------------------


def test_perfect_score():
    year = datetime.now().year
    sentences = (
        "The company provides excellent services to all customers. "
        "We have been in business for over twenty years. "
        "Our team of experts is ready to help you today. "
        "Customer satisfaction is our top priority always. "
    )
    body = sentences * 25
    html = (
        "<html><head>"
        "<title>Professional Plumbing Services</title>"
        '<meta name="description" content="Expert plumbing for your home.">'
        "</head><body>"
        "<h1>Professional Plumbing Services in London</h1>"
        f"<p>{body}</p>"
        f"<footer>&copy; {year} Acme Ltd</footer>"
        "</body></html>"
    )
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    scores = mod.score(analysis)
    assert scores["total"] == 100


def test_score_keys_present():
    html = _page(f"<p>{_words(50)}</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    scores = mod.score(analysis)
    expected_keys = {
        "adequate_word_count",
        "no_placeholder_text",
        "title_h1_overlap",
        "good_readability",
        "no_empty_paragraphs",
        "current_copyright",
        "reasonable_heading_ratio",
        "total",
    }
    assert expected_keys == set(scores.keys())


# ---------------------------------------------------------------------------
# findings priorities
# ---------------------------------------------------------------------------


def test_placeholder_is_p0():
    html = _page("<p>Lorem ipsum dolor sit amet.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    placeholder_findings = [
        f for f in mod.findings if f["title"] == "Placeholder text detected"
    ]
    assert len(placeholder_findings) == 1
    assert placeholder_findings[0]["priority"] == "P0"


def test_thin_content_is_p1():
    html = _page("<p>Short.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    thin_findings = [f for f in mod.findings if f["title"] == "Thin content detected"]
    assert len(thin_findings) == 1
    assert thin_findings[0]["priority"] == "P1"


def test_module_id_in_findings():
    html = _page("<p>Short.</p>")
    mod = ContentQualityModule()
    analysis = mod.analyse(html)
    mod.score(analysis)
    for finding in mod.findings:
        assert finding["module"] == "content_quality"
