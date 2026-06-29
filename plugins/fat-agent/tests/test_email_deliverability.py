import os
import sys

# add the scripts directory to sys.path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.email_deliverability import EmailDeliverabilityModule

# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


def test_detect_returns_true_for_form_with_email_input():
    html = '<html><body><form action="/contact"><input type="email" name="email"></form></body></html>'
    assert EmailDeliverabilityModule.detect(html) is True


def test_detect_returns_false_without_form():
    html = '<html><body><input type="email" name="email"></body></html>'
    assert EmailDeliverabilityModule.detect(html) is False


def test_detect_returns_false_without_email_input():
    html = '<html><body><form action="/search"><input type="text" name="q"></form></body></html>'
    assert EmailDeliverabilityModule.detect(html) is False


def test_detect_case_insensitive():
    html = '<html><body><FORM action="/contact"><INPUT TYPE="EMAIL" name="email"></FORM></body></html>'
    assert EmailDeliverabilityModule.detect(html) is True


# ---------------------------------------------------------------------------
# score() tests - pre-built analysis dicts, no DNS
# ---------------------------------------------------------------------------


def test_score_perfect():
    """All records present with strict DMARC policy."""
    analysis = {
        "contact_form": True,
        "spf": {"found": True, "record": "v=spf1 include:_spf.google.com ~all"},
        "dkim": {
            "found": True,
            "selector": "google",
            "record": "v=DKIM1; k=rsa; p=MIIBIjAN...",
        },
        "dmarc": {
            "found": True,
            "record": "v=DMARC1; p=reject; rua=mailto:d@example.com",
            "policy": "reject",
        },
    }
    mod = EmailDeliverabilityModule()
    result = mod.score(analysis)
    assert result["total"] == 100
    assert result["spf"] == 30
    assert result["dkim"] == 30
    assert result["dmarc"] == 30
    assert result["contact_form"] == 10


def test_score_dmarc_quarantine():
    analysis = {
        "contact_form": True,
        "spf": {"found": True, "record": "v=spf1 include:_spf.google.com ~all"},
        "dkim": {
            "found": True,
            "selector": "default",
            "record": "v=DKIM1; k=rsa; p=...",
        },
        "dmarc": {
            "found": True,
            "record": "v=DMARC1; p=quarantine;",
            "policy": "quarantine",
        },
    }
    mod = EmailDeliverabilityModule()
    result = mod.score(analysis)
    assert result["dmarc"] == 20
    assert result["total"] == 30 + 30 + 20 + 10


def test_score_dmarc_none():
    analysis = {
        "contact_form": False,
        "spf": {"found": True, "record": "v=spf1 include:_spf.google.com ~all"},
        "dkim": {
            "found": True,
            "selector": "default",
            "record": "v=DKIM1; k=rsa; p=...",
        },
        "dmarc": {"found": True, "record": "v=DMARC1; p=none;", "policy": "none"},
    }
    mod = EmailDeliverabilityModule()
    result = mod.score(analysis)
    assert result["dmarc"] == 10
    assert result["contact_form"] == 0
    assert result["total"] == 30 + 30 + 10 + 0


def test_score_no_records():
    analysis = {
        "contact_form": False,
        "spf": {"found": False},
        "dkim": {"found": False},
        "dmarc": {"found": False},
    }
    mod = EmailDeliverabilityModule()
    result = mod.score(analysis)
    assert result["total"] == 0
    assert result["spf"] == 0
    assert result["dkim"] == 0
    assert result["dmarc"] == 0
    assert result["contact_form"] == 0


def test_score_spf_only():
    analysis = {
        "contact_form": True,
        "spf": {"found": True, "record": "v=spf1 -all"},
        "dkim": {"found": False},
        "dmarc": {"found": False},
    }
    mod = EmailDeliverabilityModule()
    result = mod.score(analysis)
    assert result["spf"] == 30
    assert result["dkim"] == 0
    assert result["dmarc"] == 0
    assert result["contact_form"] == 10
    assert result["total"] == 40


def test_score_generates_findings_for_missing_records():
    analysis = {
        "contact_form": True,
        "spf": {"found": False},
        "dkim": {"found": False},
        "dmarc": {"found": False},
    }
    mod = EmailDeliverabilityModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any("SPF" in t for t in titles)
    assert any("DKIM" in t for t in titles)
    assert any("DMARC" in t for t in titles)


def test_score_generates_finding_for_weak_dmarc():
    analysis = {
        "contact_form": True,
        "spf": {"found": True, "record": "v=spf1 -all"},
        "dkim": {
            "found": True,
            "selector": "google",
            "record": "v=DKIM1; k=rsa; p=...",
        },
        "dmarc": {"found": True, "record": "v=DMARC1; p=none;", "policy": "none"},
    }
    mod = EmailDeliverabilityModule()
    mod.score(analysis)
    titles = [f["title"] for f in mod.findings]
    assert any(
        "DMARC" in t
        and ("weak" in t.lower() or "none" in t.lower() or "policy" in t.lower())
        for t in titles
    )


# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------


def test_module_id():
    assert EmailDeliverabilityModule.MODULE_ID == "email_deliverability"


def test_display_name():
    assert EmailDeliverabilityModule.DISPLAY_NAME != ""
