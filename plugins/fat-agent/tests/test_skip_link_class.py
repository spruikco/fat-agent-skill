"""A skip link is any early in-page link classed as a skip link, not only #main/#content."""

import importlib.util
import os

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("analyse_html", os.path.join(HERE, "..", "scripts", "analyse-html.py"))
analyse_html = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyse_html)


def _has_skip(html):
    p = analyse_html.FATHTMLAnalyser()
    p.feed(html)
    return p.has_skip_link


def test_class_skip_link_to_any_anchor():
    assert _has_skip('<body><a class="skip" href="#top">Skip to content</a><main id="top"></main></body>')


def test_main_anchor_still_counts():
    assert _has_skip('<body><a href="#main">Skip</a></body>')


def test_ordinary_hash_link_is_not_a_skip_link():
    assert not _has_skip('<body><a href="#pricing">Pricing</a></body>')


def _placeholders(html):
    p = analyse_html.FATHTMLAnalyser()
    p.feed(html)
    return p.placeholder_text_found


def test_word_placeholder_in_a_sentence_is_not_placeholder_copy():
    assert _placeholders("<ul><li>Placeholder text detected</li></ul>") == []


def test_real_placeholder_copy_is_caught():
    assert _placeholders("<h2>[Placeholder]</h2>")
    assert _placeholders("<p>Insert your text here</p>")
    assert _placeholders("<p>Lorem ipsum dolor sit amet</p>")
