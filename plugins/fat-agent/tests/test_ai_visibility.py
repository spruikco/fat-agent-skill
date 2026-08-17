import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import ai_visibility  # noqa: E402

# ---------------------------------------------------------------------------
# registrable_domain()
# ---------------------------------------------------------------------------


def test_registrable_domain_strips_scheme_www_and_path():
    assert (
        ai_visibility.registrable_domain("https://www.example.com/page?x=1")
        == "example.com"
    )


def test_registrable_domain_bare_host():
    assert ai_visibility.registrable_domain("Example.COM") == "example.com"


def test_registrable_domain_port_stripped():
    assert ai_visibility.registrable_domain("https://example.com:8443/x") == "example.com"


def test_registrable_domain_empty():
    assert ai_visibility.registrable_domain("") == ""


# ---------------------------------------------------------------------------
# extract_citations()
# ---------------------------------------------------------------------------


def test_extract_citations_top_level_list():
    resp = {"citations": ["https://a.com/1", "https://b.com/2"]}
    assert ai_visibility.extract_citations(resp) == [
        "https://a.com/1",
        "https://b.com/2",
    ]


def test_extract_citations_search_results_fallback():
    resp = {
        "search_results": [
            {"title": "A", "url": "https://a.com/1"},
            {"title": "B", "url": "https://b.com/2"},
        ]
    }
    assert ai_visibility.extract_citations(resp) == [
        "https://a.com/1",
        "https://b.com/2",
    ]


def test_extract_citations_citation_dicts():
    resp = {"citations": [{"url": "https://a.com/1"}]}
    assert ai_visibility.extract_citations(resp) == ["https://a.com/1"]


def test_extract_citations_none():
    assert ai_visibility.extract_citations({}) == []


# ---------------------------------------------------------------------------
# check_query() with an injected transport
# ---------------------------------------------------------------------------


def fake_post_factory(urls):
    def fake_post(payload, api_key, timeout=45):
        assert payload["messages"][0]["content"]
        assert api_key == "test-key"
        return {"citations": urls}

    return fake_post


def test_check_query_returns_domains():
    result = ai_visibility.check_query(
        "best pies melbourne",
        "test-key",
        post=fake_post_factory(["https://www.target.com/pies", "https://rival.com/x"]),
    )
    assert result["citation_domains"] == ["target.com", "rival.com"]


# ---------------------------------------------------------------------------
# analyse_results()
# ---------------------------------------------------------------------------


def _results(*domain_lists):
    return [
        {
            "query": "q%d" % i,
            "citation_urls": ["https://%s/x" % d for d in domains],
            "citation_domains": list(domains),
        }
        for i, domains in enumerate(domain_lists)
    ]


def test_analyse_results_citation_rate_and_rank():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["rival.com", "target.com"], ["rival.com"]),
    )
    assert summary["queries_tested"] == 2
    assert summary["queries_cited"] == 1
    assert summary["citation_rate"] == 0.5
    assert summary["per_query"][0]["citation_rank"] == 2
    assert summary["per_query"][1]["cited"] is False


def test_analyse_results_share_of_voice():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["target.com", "rival.com", "rival.com", "other.com"]),
    )
    assert summary["share_of_voice"] == 0.25
    top = summary["top_cited_domains"]
    assert top[0] == {"domain": "rival.com", "citations": 2}
    assert all(d["domain"] != "target.com" for d in top)


def test_analyse_results_competitor_hits():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["rival.com"], ["rival.com", "target.com"]),
        competitors=["www.rival.com"],
    )
    assert summary["competitor_citation_queries"]["rival.com"] == 2


def test_analyse_results_empty():
    summary = ai_visibility.analyse_results("target.com", [])
    assert summary["citation_rate"] == 0.0
    assert summary["share_of_voice"] == 0.0


# ---------------------------------------------------------------------------
# build_findings()
# ---------------------------------------------------------------------------


def test_findings_never_cited_is_p1():
    summary = ai_visibility.analyse_results(
        "target.com", _results(["a.com"], ["b.com"], ["c.com"])
    )
    findings = ai_visibility.build_findings(summary)
    p1 = [f for f in findings if f["priority"] == "P1"]
    assert len(p1) == 1
    assert "never" in p1[0]["description"]
    assert all(f["module"] == "ai_visibility" for f in findings)


def test_findings_low_rate_is_p2():
    summary = ai_visibility.analyse_results(
        "target.com", _results(["target.com"], ["b.com"], ["c.com"], ["d.com"])
    )
    findings = ai_visibility.build_findings(summary)
    assert any(f["priority"] == "P2" for f in findings)
    assert not any(f["priority"] == "P1" for f in findings)


def test_findings_healthy_rate_no_alarm():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["target.com"], ["target.com"], ["target.com", "rival.com"]),
    )
    findings = ai_visibility.build_findings(summary)
    assert not any(f["priority"] in ("P1", "P2") for f in findings)


def test_findings_small_sample_never_p1():
    summary = ai_visibility.analyse_results("target.com", _results(["a.com"]))
    findings = ai_visibility.build_findings(summary)
    assert not any(f["priority"] == "P1" for f in findings)


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------


def test_main_no_key_exits_available_false(capsys, monkeypatch):
    monkeypatch.delenv(ai_visibility.ENV_VAR, raising=False)
    rc = ai_visibility.main(["--domain", "example.com", "--query", "test"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["available"] is False


def test_main_no_queries_exits_available_false(capsys, monkeypatch):
    monkeypatch.setenv(ai_visibility.ENV_VAR, "test-key")
    rc = ai_visibility.main(["--domain", "example.com"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["available"] is False


def test_load_queries_file_and_dedupe(tmp_path):
    qfile = tmp_path / "queries.txt"
    qfile.write_text("alpha\nbeta\nAlpha\n\n", encoding="utf-8")

    class Args:
        query = ["beta"]
        queries = str(qfile)

    assert ai_visibility.load_queries(Args()) == ["beta", "alpha"]


def test_load_queries_json_list(tmp_path):
    qfile = tmp_path / "queries.json"
    qfile.write_text(json.dumps(["one", "two"]), encoding="utf-8")

    class Args:
        query = None
        queries = str(qfile)

    assert ai_visibility.load_queries(Args()) == ["one", "two"]


def test_redact_hides_key():
    assert "sekrit" not in ai_visibility._redact("boom sekrit boom", "sekrit")


# ---------------------------------------------------------------------------
# community-channel categorisation (v3.6.0)
# ---------------------------------------------------------------------------


def test_classify_channels_splits_community_and_competitors():
    top = [
        {"domain": "reddit.com", "citations": 3},
        {"domain": "rival.com", "citations": 2},
        {"domain": "www.youtube.com", "citations": 1},
    ]
    community, competitors = ai_visibility.classify_channels(top)
    comm_domains = {c["domain"] for c in community}
    assert "reddit.com" in comm_domains
    assert any(c["domain"] == "youtube.com" for c in community) or any(
        "youtube" in c["domain"] for c in community
    )
    assert [c["domain"] for c in competitors] == ["rival.com"]
    assert community[0]["platform"] == "Reddit"


def test_summary_exposes_channel_split():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["reddit.com", "rival.com"], ["reddit.com"]),
    )
    assert any(c["domain"] == "reddit.com" for c in summary["community_channels"])
    assert any(c["domain"] == "rival.com" for c in summary["top_competitor_domains"])


def test_findings_split_competitor_and_community():
    summary = ai_visibility.analyse_results(
        "target.com",
        _results(["reddit.com", "rival.com"], ["reddit.com", "rival.com"]),
    )
    findings = ai_visibility.build_findings(summary)
    titles = " ".join(f["title"] for f in findings)
    assert "Competitor sites" in titles
    assert "Community platforms" in titles
