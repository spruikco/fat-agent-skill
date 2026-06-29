"""AI Search / Generative Engine Optimization (GEO) audit module.

With AI Overviews now appearing on an estimated 30-40% of queries and ChatGPT /
Perplexity / Gemini / Claude surfacing citations, visibility in answer engines is
its own discipline. The most common reason a site is invisible to AI is a
robots.txt that blocks the AI crawlers. This module audits AI-search readiness
from afar:

- AI-crawler posture in robots.txt (GPTBot, OAI-SearchBot, Google-Extended,
  PerplexityBot, ClaudeBot, CCBot, Bytespider, Amazonbot, Applebot-Extended, …)
- presence of an `llms.txt` manifest
- extraction-readiness of the page (concise lead answer, Q&A, lists, tables,
  clear headings)
- entity clarity (Organization/Person + sameAs to Wikipedia/Wikidata)

Network fetches (robots.txt / llms.txt) are guarded and optional: pass
``robots_txt=`` / ``llms_txt=`` to analyse() to avoid I/O (used by tests).
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request

# AI crawlers worth reporting a posture for. (label -> user-agent token)
AI_BOTS = {
    "GPTBot": "gptbot",
    "OAI-SearchBot": "oai-searchbot",
    "ChatGPT-User": "chatgpt-user",
    "Google-Extended": "google-extended",
    "PerplexityBot": "perplexitybot",
    "ClaudeBot": "claudebot",
    "anthropic-ai": "anthropic-ai",
    "CCBot": "ccbot",
    "Bytespider": "bytespider",
    "Amazonbot": "amazonbot",
    "Applebot-Extended": "applebot-extended",
    "Meta-ExternalAgent": "meta-externalagent",
}


def parse_robots(robots_text):
    """Parse robots.txt into [(agents:set[str], rules:list[(kind, path)])]."""
    groups = []
    current_agents = set()
    current_rules = []
    started_rules = False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (p.strip() for p in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if started_rules and current_agents:
                groups.append((current_agents, current_rules))
                current_agents = set()
                current_rules = []
                started_rules = False
            current_agents.add(value.lower())
        elif field in ("allow", "disallow"):
            started_rules = True
            current_rules.append((field, value))
    if current_agents:
        groups.append((current_agents, current_rules))
    return groups


def bot_posture(robots_text, agent_token):
    """Return 'allowed' | 'blocked' | 'partial' for one bot token.

    Specific user-agent group wins over '*'. A group is 'blocked' when it
    disallows the site root with no overriding allow.
    """
    if not robots_text:
        return "allowed"  # no robots.txt → everything allowed
    groups = parse_robots(robots_text)

    def evaluate(rules):
        disallow_root = any(
            k == "disallow" and v.strip() in ("/", "/*") for k, v in rules
        )
        allow_root = any(k == "allow" and v.strip() in ("/", "/*") for k, v in rules)
        disallow_any = any(k == "disallow" and v.strip() for k, v in rules)
        if disallow_root and not allow_root:
            return "blocked"
        if disallow_any and not disallow_root:
            return "partial"
        return "allowed"

    specific = [rules for agents, rules in groups if agent_token in agents]
    if specific:
        return evaluate(specific[0])
    wildcard = [rules for agents, rules in groups if "*" in agents]
    if wildcard:
        return evaluate(wildcard[0])
    return "allowed"


def ai_bot_report(robots_text):
    return {label: bot_posture(robots_text, token) for label, token in AI_BOTS.items()}


def extraction_readiness(html):
    """Heuristic signals that AI engines can cleanly extract + cite the page."""
    low = html.lower()
    return {
        "has_faq": bool(
            re.search(r"<details", low)
            or re.search(r'"@type"\s*:\s*"faqpage"', low)
            or re.search(r"frequently asked", low)
        ),
        "has_lists": low.count("<li") >= 3,
        "has_tables": "<table" in low,
        "has_headings": len(re.findall(r"<h[2-3][\s>]", low)) >= 2,
        "has_definition_or_summary": bool(
            re.search(
                r"<dl[\s>]|<summary|class=[\"'][^\"']*(?:summary|tl;dr|key-takeaway)",
                low,
            )
        ),
    }


def entity_clarity(html):
    has_org = bool(
        re.search(r'"@type"\s*:\s*"(organization|localbusiness)"', html, re.IGNORECASE)
    )
    has_sameas = '"sameas"' in html.lower()
    has_kg_link = bool(re.search(r"wikipedia\.org|wikidata\.org", html, re.IGNORECASE))
    return {
        "organization": has_org,
        "sameAs": has_sameas,
        "knowledge_graph_link": has_kg_link,
    }


from modules import register_module  # noqa: E402
from modules.base import AuditModule  # noqa: E402


@register_module
class AISearchModule(AuditModule):
    MODULE_ID = "ai_search"
    DISPLAY_NAME = "AI Search / GEO"
    ALWAYS_ENABLED = True

    @classmethod
    def detect(cls, html: str) -> bool:
        return True

    def _fetch(self, url, path, timeout=8):
        try:
            base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(url))
            req = urllib.request.Request(
                urllib.parse.urljoin(base + "/", path),
                headers={"User-Agent": "fat-agent-aisearch/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def analyse(self, html: str, url: str = "", headers: dict = None, **kwargs) -> dict:
        robots_txt = kwargs.get("robots_txt")
        llms_txt = kwargs.get("llms_txt")
        if robots_txt is None and url:
            robots_txt = self._fetch(url, "robots.txt")
        if llms_txt is None and url:
            llms_txt = self._fetch(url, "llms.txt")

        report = ai_bot_report(robots_txt or "")
        return {
            "robots_available": robots_txt is not None,
            "ai_bots": report,
            "blocked_bots": [b for b, p in report.items() if p == "blocked"],
            "llms_txt": bool(llms_txt),
            "extraction": extraction_readiness(html),
            "entity": entity_clarity(html),
        }

    def score(self, analysis: dict) -> dict:
        total = 0
        details = {}

        blocked = analysis["blocked_bots"]
        access_pts = max(0, 45 - 9 * len(blocked))
        details["ai_crawler_access"] = {"score": access_pts, "max": 45}
        total += access_pts

        llms_pts = 10 if analysis["llms_txt"] else 0
        details["llms_txt"] = {"score": llms_pts, "max": 10}
        total += llms_pts

        ex = analysis["extraction"]
        ex_pts = sum(5 for v in ex.values() if v)
        details["extraction_readiness"] = {"score": ex_pts, "max": 25}
        total += ex_pts

        ent = analysis["entity"]
        ent_pts = (
            (8 if ent["organization"] else 0)
            + (6 if ent["sameAs"] else 0)
            + (6 if ent["knowledge_graph_link"] else 0)
        )
        details["entity_clarity"] = {"score": ent_pts, "max": 20}
        total += ent_pts

        self._findings(analysis)
        return {"total": total, "max": 100, "details": details}

    def _findings(self, a: dict):
        if a["blocked_bots"]:
            self.add_finding(
                priority="P1",
                title=f"AI crawlers blocked in robots.txt: {', '.join(a['blocked_bots'])}",
                description="These AI/answer-engine crawlers are disallowed at the site root, so "
                "your content cannot be cited in ChatGPT / Perplexity / Google AI Overviews / "
                "Gemini. A blanket block is the #1 cause of AI-search invisibility.",
                fix="Decide your posture deliberately. To be citable in AI answers, allow the "
                "search/answer bots (e.g. OAI-SearchBot, PerplexityBot, Google-Extended) in "
                "robots.txt. Block only training-only bots if that's your policy.",
                effort="low",
            )
        if not a["llms_txt"]:
            self.add_finding(
                priority="P3",
                title="No llms.txt manifest",
                description="No `/llms.txt` found. This emerging standard gives AI engines a "
                "clean, citation-ready map of your key content and entity.",
                fix="Publish an `/llms.txt` (and optionally `/llms-full.txt`) summarising your "
                "site, key pages, and entity in Markdown.",
                effort="medium",
            )
        ex = a["extraction"]
        if not (ex["has_faq"] or ex["has_definition_or_summary"]):
            self.add_finding(
                priority="P3",
                title="Low extraction-readiness for AI answers",
                description="The page lacks the structures AI engines lift most readily — a "
                "concise lead answer / summary, Q&A, or definition blocks.",
                fix="Add a concise summary or 'key takeaways' near the top and structure key "
                "points as Q&A or lists so answer engines can quote you cleanly.",
                effort="medium",
            )
        ent = a["entity"]
        if not ent["organization"]:
            self.add_finding(
                priority="P3",
                title="Weak entity signals for AI grounding",
                description="No Organization entity / `sameAs` found, so AI engines have little to "
                "ground and disambiguate your brand against.",
                fix="Add Organization schema with `sameAs` to your socials and, ideally, "
                "Wikipedia/Wikidata.",
                effort="low",
            )
