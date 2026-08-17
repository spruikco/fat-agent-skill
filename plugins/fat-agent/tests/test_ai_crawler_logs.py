import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import ai_crawler_logs as acl  # noqa: E402

COMBINED = (
    '66.249.66.1 - - [10/Oct/2025:13:55:36 +0000] "GET /page HTTP/1.1" 200 512 '
    '"-" "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/bot)"'
)
GPTBOT = (
    '20.15.240.1 - - [11/Oct/2025:09:00:00 +0000] "GET /a HTTP/1.1" 200 100 '
    '"-" "Mozilla/5.0 (compatible; GPTBot/1.1; +https://openai.com/gptbot)"'
)
HUMAN = (
    '1.2.3.4 - - [11/Oct/2025:09:00:01 +0000] "GET /b HTTP/1.1" 200 100 '
    '"-" "Mozilla/5.0 (Windows NT 10.0) Chrome/120"'
)
CLAUDEBOT_404 = (
    '40.1.1.1 - - [12/Oct/2025:00:00:00 +0000] "GET /gone HTTP/1.1" 404 0 '
    '"-" "Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"'
)


def test_parse_matches_perplexity():
    stats, total, matched = acl.parse_lines([COMBINED])
    assert total == 1
    assert matched == 1
    assert "PerplexityBot" in stats
    assert stats["PerplexityBot"]["hits"] == 1
    assert stats["PerplexityBot"]["sample_paths"] == ["/page"]


def test_human_traffic_ignored():
    stats, total, matched = acl.parse_lines([HUMAN])
    assert total == 1
    assert matched == 0
    assert stats == {}


def test_answer_bot_seen_no_missing_all_finding():
    stats, total, matched = acl.parse_lines([COMBINED])
    report = acl.build_report(stats, total, matched)
    assert "PerplexityBot" in report["answer_bots_seen"]
    assert not any(
        "No AI answer-engine crawlers" in f["title"] for f in report["findings"]
    )


def test_no_answer_bots_flagged_p2():
    stats, total, matched = acl.parse_lines([GPTBOT, HUMAN])
    report = acl.build_report(stats, total, matched)
    # GPTBot is a training bot; no answer bot seen
    assert report["answer_bots_seen"] == []
    assert any(
        f["priority"] == "P2" and "No AI answer-engine" in f["title"]
        for f in report["findings"]
    )
    assert "GPTBot" in report["training_bots_seen"]


def test_partial_answer_coverage_p3():
    stats, total, matched = acl.parse_lines([COMBINED])
    report = acl.build_report(stats, total, matched)
    # PerplexityBot seen but OAI-SearchBot etc. missing
    assert report["answer_bots_missing"]
    assert any(f["priority"] == "P3" for f in report["findings"])


def test_error_heavy_bot_flagged():
    lines = [CLAUDEBOT_404] * 12
    stats, total, matched = acl.parse_lines(lines)
    report = acl.build_report(stats, total, matched)
    assert any(
        "mostly hitting errors" in f["title"] for f in report["findings"]
    )


def test_status_counts_tracked():
    stats, _, _ = acl.parse_lines([GPTBOT, CLAUDEBOT_404])
    assert stats["GPTBot"]["statuses"]["200"] == 1
    assert stats["ClaudeBot"]["statuses"]["404"] == 1


def test_malformed_lines_skipped():
    stats, total, matched = acl.parse_lines(["garbage", "", COMBINED])
    assert total == 3
    assert matched == 1


def test_findings_carry_module_tag():
    stats, total, matched = acl.parse_lines([GPTBOT])
    report = acl.build_report(stats, total, matched)
    assert all(f["module"] == "ai_crawler_logs" for f in report["findings"])
