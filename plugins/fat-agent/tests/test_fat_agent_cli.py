"""tests for fat_agent_cli.py — arg parsing and orchestration logic."""

import json
import os
import sys
import tempfile
from unittest import mock

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "scripts"),
)

from fat_agent_cli import (
    build_parser,
    main,
    cmd_audit,
    cmd_crawl,
    cmd_bulk,
    cmd_gate,
)

# ---------------------------------------------------------------------------
# arg parsing
# ---------------------------------------------------------------------------


class TestArgParsing:
    """verify subcommand arg parsing produces expected namespace values."""

    def test_audit_basic(self):
        parser = build_parser()
        args = parser.parse_args(["audit", "https://example.com"])
        assert args.command == "audit"
        assert args.url == "https://example.com"
        assert args.profile == "full"
        assert args.output_dir is None
        assert args.format is None

    def test_audit_all_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "audit",
                "https://example.com",
                "--profile",
                "quick",
                "--output-dir",
                "./reports",
                "--format",
                "html",
            ]
        )
        assert args.profile == "quick"
        assert args.output_dir == "./reports"
        assert args.format == "html"

    def test_crawl_basic(self):
        parser = build_parser()
        args = parser.parse_args(["crawl", "https://example.com"])
        assert args.command == "crawl"
        assert args.url == "https://example.com"
        assert args.depth == 2
        assert args.max_pages == 10

    def test_crawl_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "crawl",
                "https://example.com",
                "--depth",
                "3",
                "--max-pages",
                "20",
                "--output-dir",
                "/tmp/crawl",
            ]
        )
        assert args.depth == 3
        assert args.max_pages == 20
        assert args.output_dir == "/tmp/crawl"

    def test_bulk_basic(self):
        parser = build_parser()
        args = parser.parse_args(["bulk", "sites.json"])
        assert args.command == "bulk"
        assert args.sites_file == "sites.json"
        assert args.profile == "full"

    def test_bulk_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "bulk",
                "sites.json",
                "--profile",
                "local",
                "--output-dir",
                "./reports",
            ]
        )
        assert args.profile == "local"
        assert args.output_dir == "./reports"

    def test_gate_basic(self):
        parser = build_parser()
        args = parser.parse_args(["gate", "scores.json"])
        assert args.command == "gate"
        assert args.scores_file == "scores.json"
        assert args.threshold == 70
        assert args.fail_on is None

    def test_gate_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "gate",
                "scores.json",
                "--threshold",
                "80",
                "--fail-on",
                "P0",
            ]
        )
        assert args.threshold == 80
        assert args.fail_on == "P0"

    def test_no_command_returns_2(self):
        assert main([]) == 2

    def test_audit_invalid_profile(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["audit", "https://example.com", "--profile", "nonexistent"]
            )

    def test_audit_invalid_format(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["audit", "https://example.com", "--format", "csv"])


# ---------------------------------------------------------------------------
# orchestration — audit
# ---------------------------------------------------------------------------


class TestCmdAudit:
    """test cmd_audit orchestration with mocked subprocess and fetch."""

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_happy_path(self, mock_fetch, mock_run):
        mock_fetch.return_value = (
            "<html><head><title>test</title></head></html>",
            {"content-type": "text/html"},
        )

        analyse_output = json.dumps({"seo": {}, "security": {}})
        score_output = json.dumps(
            {
                "overall_score": 75,
                "seo": {"score": 80},
                "security": {"score": 70},
                "accessibility": {"score": 60},
                "performance": {"score": 90},
            }
        )

        mock_run.side_effect = [
            (0, analyse_output, ""),
            (0, score_output, ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = build_parser()
            args = parser.parse_args(
                ["audit", "https://example.com", "--output-dir", tmpdir]
            )
            rc = cmd_audit(args)

            assert rc == 0
            assert os.path.exists(os.path.join(tmpdir, "scores.json"))

            mock_fetch.assert_called_once_with("https://example.com")
            assert mock_run.call_count == 2

    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_fetch_failure(self, mock_fetch):
        mock_fetch.side_effect = OSError("connection refused")

        parser = build_parser()
        args = parser.parse_args(["audit", "https://example.com"])
        rc = cmd_audit(args)
        assert rc == 1

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_analyse_failure(self, mock_fetch, mock_run):
        mock_fetch.return_value = ("<html></html>", {})
        mock_run.return_value = (1, "", "error in analysis")

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = build_parser()
            args = parser.parse_args(
                ["audit", "https://example.com", "--output-dir", tmpdir]
            )
            rc = cmd_audit(args)
            assert rc == 1

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_low_score_returns_1(self, mock_fetch, mock_run):
        mock_fetch.return_value = ("<html></html>", {})

        analyse_output = json.dumps({"seo": {}})
        score_output = json.dumps(
            {
                "overall_score": 30,
                "seo": {"score": 30},
                "security": {"score": 30},
                "accessibility": {"score": 30},
                "performance": {"score": 30},
            }
        )
        mock_run.side_effect = [
            (0, analyse_output, ""),
            (0, score_output, ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = build_parser()
            args = parser.parse_args(
                ["audit", "https://example.com", "--output-dir", tmpdir]
            )
            rc = cmd_audit(args)
            assert rc == 1

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_with_format_html(self, mock_fetch, mock_run):
        mock_fetch.return_value = ("<html></html>", {})

        analyse_output = json.dumps({"seo": {}})
        score_output = json.dumps(
            {
                "overall_score": 80,
                "seo": {"score": 80},
                "security": {"score": 80},
                "accessibility": {"score": 80},
                "performance": {"score": 80},
            }
        )

        # analyse, score, then html dashboard
        mock_run.side_effect = [
            (0, analyse_output, ""),
            (0, score_output, ""),
            (0, "", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = build_parser()
            args = parser.parse_args(
                [
                    "audit",
                    "https://example.com",
                    "--output-dir",
                    tmpdir,
                    "--format",
                    "html",
                ]
            )
            rc = cmd_audit(args)
            assert rc == 0
            assert mock_run.call_count == 3

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_audit_score_parse_failure(self, mock_fetch, mock_run):
        mock_fetch.return_value = ("<html></html>", {})
        mock_run.side_effect = [
            (0, json.dumps({"seo": {}}), ""),
            (0, "not valid json", ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = build_parser()
            args = parser.parse_args(
                ["audit", "https://example.com", "--output-dir", tmpdir]
            )
            rc = cmd_audit(args)
            assert rc == 1


# ---------------------------------------------------------------------------
# orchestration — crawl
# ---------------------------------------------------------------------------


class TestCmdCrawl:
    """test cmd_crawl delegates correctly to crawl.py."""

    @mock.patch("fat_agent_cli._run_script")
    def test_crawl_delegates(self, mock_run):
        mock_run.return_value = (0, '{"pages": []}', "")

        parser = build_parser()
        args = parser.parse_args(
            ["crawl", "https://example.com", "--depth", "3", "--max-pages", "5"]
        )
        rc = cmd_crawl(args)

        assert rc == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0]
        assert call_args[0] == "crawl.py"
        assert "--url" in call_args[1]
        assert "https://example.com" in call_args[1]
        assert "--depth" in call_args[1]
        assert "3" in call_args[1]
        assert "--max-pages" in call_args[1]
        assert "5" in call_args[1]

    @mock.patch("fat_agent_cli._run_script")
    def test_crawl_with_output_dir(self, mock_run):
        mock_run.return_value = (0, "", "")

        parser = build_parser()
        args = parser.parse_args(
            ["crawl", "https://example.com", "--output-dir", "/tmp/out"]
        )
        cmd_crawl(args)

        call_args = mock_run.call_args[0][1]
        assert "--output-dir" in call_args
        assert "/tmp/out" in call_args


# ---------------------------------------------------------------------------
# orchestration — bulk
# ---------------------------------------------------------------------------


class TestCmdBulk:
    """test cmd_bulk delegates correctly to bulk_audit.py."""

    @mock.patch("fat_agent_cli._run_script")
    def test_bulk_delegates(self, mock_run):
        mock_run.return_value = (0, "summary output", "")

        parser = build_parser()
        args = parser.parse_args(
            ["bulk", "sites.json", "--profile", "local", "--output-dir", "./out"]
        )
        rc = cmd_bulk(args)

        assert rc == 0
        call_args = mock_run.call_args[0]
        assert call_args[0] == "bulk_audit.py"
        assert "--sites" in call_args[1]
        assert "sites.json" in call_args[1]
        assert "--profile" in call_args[1]
        assert "local" in call_args[1]
        assert "--output-dir" in call_args[1]

    @mock.patch("fat_agent_cli._run_script")
    def test_bulk_propagates_exit_code(self, mock_run):
        mock_run.return_value = (1, "", "error")

        parser = build_parser()
        args = parser.parse_args(["bulk", "sites.json"])
        rc = cmd_bulk(args)
        assert rc == 1


# ---------------------------------------------------------------------------
# orchestration — gate
# ---------------------------------------------------------------------------


class TestCmdGate:
    """test cmd_gate delegates correctly to ci_gate.py."""

    @mock.patch("fat_agent_cli._run_script")
    def test_gate_delegates(self, mock_run):
        mock_run.return_value = (0, "PASS", "")

        parser = build_parser()
        args = parser.parse_args(
            ["gate", "scores.json", "--threshold", "80", "--fail-on", "P0"]
        )
        rc = cmd_gate(args)

        assert rc == 0
        call_args = mock_run.call_args[0]
        assert call_args[0] == "ci_gate.py"
        assert "--scores" in call_args[1]
        assert "scores.json" in call_args[1]
        assert "--threshold" in call_args[1]
        assert "80" in call_args[1]
        assert "--fail-on" in call_args[1]
        assert "P0" in call_args[1]

    @mock.patch("fat_agent_cli._run_script")
    def test_gate_propagates_failure(self, mock_run):
        mock_run.return_value = (2, "", "priority findings")

        parser = build_parser()
        args = parser.parse_args(["gate", "scores.json"])
        rc = cmd_gate(args)
        assert rc == 2


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------


class TestMain:
    """test the main() dispatch."""

    @mock.patch("fat_agent_cli._run_script")
    @mock.patch("fat_agent_cli.fetch_url")
    def test_main_dispatches_audit(self, mock_fetch, mock_run):
        mock_fetch.return_value = ("<html></html>", {})
        score_data = json.dumps(
            {
                "overall_score": 80,
                "seo": {"score": 80},
                "security": {"score": 80},
                "accessibility": {"score": 80},
                "performance": {"score": 80},
            }
        )
        mock_run.side_effect = [
            (0, json.dumps({"seo": {}}), ""),
            (0, score_data, ""),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            rc = main(["audit", "https://example.com", "--output-dir", tmpdir])
            assert rc == 0

    @mock.patch("fat_agent_cli._run_script")
    def test_main_dispatches_gate(self, mock_run):
        mock_run.return_value = (0, "PASS", "")
        rc = main(["gate", "scores.json", "--threshold", "50"])
        assert rc == 0
