import os
import sys
from unittest.mock import patch, MagicMock

# add the scripts directory to sys.path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import lighthouse

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
MOCK_JSON = os.path.join(FIXTURES_DIR, "lighthouse_mock.json")


# ---------------------------------------------------------------------------
# check_lighthouse_available() tests
# ---------------------------------------------------------------------------


def test_check_lighthouse_available_returns_bool():
    result = lighthouse.check_lighthouse_available()
    assert isinstance(result, bool)


@patch("shutil.which", return_value="/usr/bin/lighthouse")
def test_check_lighthouse_available_when_installed(mock_which):
    assert lighthouse.check_lighthouse_available() is True
    mock_which.assert_called_once_with("lighthouse")


@patch("shutil.which", return_value=None)
def test_check_lighthouse_available_when_not_installed(mock_which):
    assert lighthouse.check_lighthouse_available() is False


# ---------------------------------------------------------------------------
# parse_lighthouse_results() tests — uses mock fixture
# ---------------------------------------------------------------------------


def test_parse_lighthouse_results_scores():
    result = lighthouse.parse_lighthouse_results(MOCK_JSON)
    assert result["available"] is True
    assert result["scores"]["performance"] == 92
    assert result["scores"]["accessibility"] == 88
    assert result["scores"]["best_practices"] == 95
    assert result["scores"]["seo"] == 91


def test_parse_lighthouse_results_core_web_vitals():
    result = lighthouse.parse_lighthouse_results(MOCK_JSON)
    cwv = result["core_web_vitals"]
    assert cwv["LCP"] == 1850.5
    assert cwv["CLS"] == 0.042
    assert cwv["INP"] == 180
    assert cwv["FCP"] == 1200.3
    assert cwv["TTFB"] == 320.7


def test_parse_lighthouse_results_metadata():
    result = lighthouse.parse_lighthouse_results(MOCK_JSON)
    assert result["url"] == "https://example.com"
    assert result["lighthouse_version"] == "12.0.0"


def test_parse_lighthouse_results_missing_file():
    result = lighthouse.parse_lighthouse_results("/nonexistent/path.json")
    assert result["available"] is False
    assert result["scores"]["performance"] is None
    assert result["scores"]["seo"] is None
    assert result["core_web_vitals"]["LCP"] is None


# ---------------------------------------------------------------------------
# run_lighthouse() tests — graceful fallback when not installed
# ---------------------------------------------------------------------------


@patch("shutil.which", return_value=None)
def test_run_lighthouse_not_installed(mock_which):
    result = lighthouse.run_lighthouse("https://example.com", "/tmp/out.json")
    assert result["available"] is False
    assert result["scores"]["performance"] is None
    assert result["core_web_vitals"]["LCP"] is None


@patch("shutil.which", return_value="/usr/bin/lighthouse")
@patch("subprocess.run")
@patch("lighthouse.parse_lighthouse_results")
def test_run_lighthouse_success(mock_parse, mock_run, mock_which):
    mock_run.return_value = MagicMock(returncode=0)
    mock_parse.return_value = {"available": True}

    result = lighthouse.run_lighthouse("https://example.com", "/tmp/out.json")

    # check subprocess.run was called with correct args
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "lighthouse"
    assert "https://example.com" in cmd
    assert "--output" in cmd
    assert "json" in cmd
    assert "--chrome-flags=--headless --no-sandbox" in cmd
    assert result["available"] is True


@patch("shutil.which", return_value="/usr/bin/lighthouse")
@patch("subprocess.run", side_effect=Exception("Chrome not found"))
def test_run_lighthouse_subprocess_error(mock_run, mock_which):
    result = lighthouse.run_lighthouse("https://example.com", "/tmp/out.json")
    assert result["available"] is False
    assert result["error"] is not None


# ---------------------------------------------------------------------------
# CLI arg parsing tests
# ---------------------------------------------------------------------------


def test_cli_parse_args():
    parser = lighthouse.build_arg_parser()
    args = parser.parse_args(
        ["--url", "https://example.com", "--output", "/tmp/out.json"]
    )
    assert args.url == "https://example.com"
    assert args.output == "/tmp/out.json"


def test_cli_parse_args_defaults():
    parser = lighthouse.build_arg_parser()
    args = parser.parse_args(["--url", "https://example.com"])
    assert args.url == "https://example.com"
    assert args.output is not None  # should have a default
