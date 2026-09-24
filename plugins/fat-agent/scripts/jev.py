#!/usr/bin/env python3
"""Typed-judgment layer for FAT: Jev (TypeSafe), any Jev-compatible server, or the agent.

Several FAT checks are bounded judgments that regexes approximate badly: "does
this location page carry genuinely local substance?", "does this page answer
this sub-query?". System One models such as TypeSafe's Jev answer exactly that
shape (noul = P(yes), choice, score) with calibrated confidence, fast and cheap
enough to run over every page of a crawl. This module asks those questions and
turns the answers into FAT findings.

Backends (same questions, same answer shape, so results are comparable):
- ``typesafe``  hosted Jev. Needs ``TYPESAFE_API_KEY``.
- ``local``     any Jev-wire-compatible server (e.g. OpenJev) at ``--base-url``
                / ``TYPESAFE_BASE_URL``. No key needed.
- ``agent``     no key, no install: ``--export`` writes the question batch to a
                JSON file, the agent running the audit (Claude) answers it into
                ``{id: {question_id: {"type": "noul", "noul": 0.8}}}``, and
                ``--answers`` reads it back.
``--backend auto`` picks typesafe if a key is set, else local if a base URL is
set, else agent.

Tasks:
    doorway   judge every page in a templated near-duplicate cluster for local
              substance + originality; combine with GSC (optional) into a
              keep / improve / prune triage with reasons.
    fanout    for each fan-out sub-query, shortlist candidate pages by token
              overlap and ask whether each actually answers it.

Usage:
    python scripts/jev.py ping
    python scripts/jev.py doorway --db site.db --gsc gsc_pages.json --out .fat-work/jev_doorway.json
    python scripts/jev.py fanout --db site.db --seed "seo agency melbourne" --out .fat-work/jev_fanout.json
    # keyless:
    python scripts/jev.py doorway --db site.db --backend agent --export .fat-work/jev_batch.json
    python scripts/jev.py doorway --db site.db --backend agent --answers .fat-work/jev_answers.json --out ...

Answers are cached in ``.fat-work/jev_cache.json`` (keyed by state + questions +
model), so re-runs are free. Typed output guarantees the interface, not truth:
treat these as triage-grade and route low-confidence cases to a human or Claude.
Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODULE = "jev"
DEFAULT_BASE = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
RETRY_STATUSES = {429, 529, 502, 503}
EXCERPT_CHARS = 1500
# template copy needs real search demand to be worth improving rather than pruning
IMPROVE_MIN_IMPRESSIONS = 20

# --------------------------------------------------------------------------- #
# Questions (one narrow judgment each; ids are for code, meaning is in the text)
# --------------------------------------------------------------------------- #
DOORWAY_QUESTIONS = {
    "local_substance": {
        "type": "noul",
        "instructions": "Does `page` contain genuinely location-specific substance "
        "about `page.location_hint`, beyond inserting the place name into generic "
        "copy? Substance means concrete local detail: named local clients or "
        "projects, local staff or office, suburb-specific prices, regulations, "
        "landmarks, travel or service-area specifics, or local results.",
        "criteria": {
            "true": "Has concrete facts that only apply to this location",
            "false": "Generic template copy with the place name swapped in",
        },
    },
    "originality": {
        "type": "score",
        "instructions": "How much original, useful information does `page` add "
        "for a reader, compared with a generic service page anyone could write?",
        "criteria": [
            "Boilerplate or filler; nothing specific",
            "Mostly generic with a detail or two",
            "Some specific, useful information",
            "Substantial specific information a reader would value",
            "Clearly expert, first-hand and specific throughout",
        ],
    },
}

FANOUT_QUESTION = {
    "answers_query": {
        "type": "noul",
        "instructions": "Would a searcher asking `query` find a direct, useful "
        "answer to that specific question on `page` (from its title, headings and "
        "text), not just a passing mention of the words?",
        "criteria": {
            "true": "The page directly answers the question",
            "false": "The page does not answer it, or only mentions the topic",
        },
    }
}


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class JevError(RuntimeError):
    pass


def _key(state, questions, model) -> str:
    raw = json.dumps([state, questions, model], sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JevClient:
    """Minimal client for POST /v1/systemone (TypeSafe or wire-compatible)."""

    def __init__(self, base_url=None, api_key=None, model=None, cache_path=None,
                 workers=8, timeout=30.0, retries=4):
        self.base_url = (base_url or DEFAULT_BASE).rstrip("/")
        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.workers = workers
        self.timeout = timeout
        self.retries = retries
        self.cache_path = cache_path
        self.cache = {}
        self._lock = threading.Lock()
        self.usage = {"input_tokens": 0, "requests": 0, "cached": 0}
        self.served_by = None
        if cache_path and os.path.exists(cache_path):
            try:
                self.cache = json.load(open(cache_path, encoding="utf-8"))
            except ValueError:
                self.cache = {}

    def _post(self, body) -> dict:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        delay = 1.0
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(
                f"{self.base_url}/v1/systemone", data=data, headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in RETRY_STATUSES and attempt < self.retries:
                    wait = e.headers.get("retry-after") if e.headers else None
                    try:
                        wait = float(wait)
                    except (TypeError, ValueError):
                        wait = delay
                    time.sleep(wait)
                    delay *= 2
                    continue
                detail = e.read().decode("utf-8", "replace")[:300]
                raise JevError(f"HTTP {e.code}: {detail}") from None
            except urllib.error.URLError as e:
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise JevError(f"cannot reach {self.base_url}: {e.reason}") from None
        raise JevError("retries exhausted")

    def ask(self, state, questions) -> dict:
        k = _key(state, questions, self.model)
        with self._lock:
            if k in self.cache:
                self.usage["cached"] += 1
                return self.cache[k]
        res = self._post({"state": state, "model": self.model, "questions": questions})
        answers = res.get("answers") or {}
        with self._lock:
            self.cache[k] = answers
            self.usage["requests"] += 1
            self.usage["input_tokens"] += (res.get("usage") or {}).get("input_tokens", 0)
            self.served_by = res.get("model", self.served_by)
        return answers

    def ask_many(self, items) -> dict:
        """items: [(id, state, questions)] → {id: answers}; errors → {"error": ...}."""
        out = {}

        def run(item):
            iid, state, qs = item
            try:
                return iid, self.ask(state, qs)
            except JevError as e:
                return iid, {"error": str(e)}

        with ThreadPoolExecutor(max_workers=max(1, self.workers)) as ex:
            for iid, ans in ex.map(run, items):
                out[iid] = ans
        self.save()
        return out

    def save(self):
        if self.cache_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.cache_path)), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh)


def resolve_backend(backend, base_url=None, api_key=None):
    """→ (backend, base_url, api_key)."""
    api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
    base_url = base_url or os.environ.get("TYPESAFE_BASE_URL")
    if backend == "auto":
        if api_key and not base_url:
            backend = "typesafe"
        elif base_url:
            backend = "local"
        else:
            backend = "agent"
    if backend == "typesafe":
        if not api_key:
            raise SystemExit(json.dumps({"error": "TYPESAFE_API_KEY not set (or use "
                                         "--backend local / agent)"}))
        base_url = base_url or DEFAULT_BASE
    if backend == "local" and not base_url:
        base_url = "http://localhost:8000"
    return backend, base_url, api_key


def noul(ans, qid) -> float | None:
    a = (ans or {}).get(qid) or {}
    v = a.get("noul")
    return float(v) if isinstance(v, (int, float)) else None


def score(ans, qid):
    """(score, levels-1, confidence) or (None, None, None)."""
    a = (ans or {}).get(qid) or {}
    s = a.get("score")
    if not isinstance(s, (int, float)):
        return None, None, None
    top = max((int(k) for k in (a.get("legend") or {}).keys()), default=None)
    return float(s), top, a.get("confidence")


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
def _cols(con):
    return {r[1] for r in con.execute("PRAGMA table_info(pages)")}


def _page_state(row, location_hint=""):
    url, title, h1, meta, heads, excerpt = row
    return {
        "page": {
            "url": url,
            "title": title or "",
            "h1": h1 or "",
            "meta_description": meta or "",
            "headings": (heads or "").split(" | ")[:20] if heads else [],
            "text_excerpt": (excerpt or "")[:EXCERPT_CHARS],
            "location_hint": location_hint,
        }
    }


def _location_hint(url, shape):
    """The part of the URL the template varies on (e.g. 'st-kilda-melbourne')."""
    from urllib.parse import urlparse

    path = urlparse(url).path.strip("/").split("/")
    sh = shape.strip("/").split("/")
    for seg, pat in zip(path, sh):
        if "{*}" in pat:
            pre, _, suf = pat.partition("{*}")
            core = seg[len(pre): len(seg) - len(suf) if suf else None]
            return core.replace("-", " ")
    return ""


def doorway_items(con, clusters, per_cluster=0):
    cols = _cols(con)
    if "main_excerpt" not in cols:
        raise SystemExit(json.dumps({"error": "crawl DB has no main_excerpt; re-crawl "
                                     "with sitecrawl.py v3.8+"}))
    items = []
    for c in clusters:
        urls = c["urls"]
        if per_cluster and len(urls) > per_cluster:
            step = len(urls) / per_cluster  # spread the sample across the cluster
            urls = [urls[int(i * step)] for i in range(per_cluster)]
        for url in urls:
            row = con.execute(
                "SELECT url,title,h1,meta_desc,headings,main_excerpt FROM pages WHERE url=?",
                (url,),
            ).fetchone()
            hint = _location_hint(url, c["shape"])
            if row and hint:  # no location in the URL = the hub itself, not a doorway
                items.append((url, _page_state(row, hint), DOORWAY_QUESTIONS))
    return items


def doorway_verdicts(clusters, answers, gsc=None, keep_p=0.7, prune_p=0.3):
    """Combine judgments (+ GSC) into keep / improve / prune with a reason each."""
    from sitewide import url_key

    out = []
    for c in clusters:
        rows = []
        for url in c["urls"]:
            ans = answers.get(url) or {}
            p = noul(ans, "local_substance")
            s, top, conf = score(ans, "originality")
            g = (gsc or {}).get(url_key(url)) or {}
            clicks, imps = g.get("clicks", 0), g.get("impressions", 0)
            if p is None:
                verdict, why = "unjudged", ans.get("error", "no answer")
            elif clicks >= 1 and p >= prune_p:
                verdict, why = "keep", f"{int(clicks)} clicks, local substance {p:.2f}"
            elif p >= keep_p:
                verdict, why = "keep", f"genuine local substance ({p:.2f})"
            elif clicks >= 1 or imps >= IMPROVE_MIN_IMPRESSIONS:
                verdict, why = "improve", (f"earns search visibility ({int(imps)} impr) "
                                           f"but template copy (local substance {p:.2f})")
            elif p <= prune_p:
                verdict, why = "prune", (f"template copy (local substance {p:.2f}), "
                                         f"{int(imps)} impressions, no clicks")
            else:
                verdict, why = "improve", f"borderline local substance ({p:.2f})"
            rows.append({"url": url, "verdict": verdict, "why": why,
                         "local_substance": p, "originality": s,
                         "originality_max": top, "originality_confidence": conf,
                         "clicks": clicks, "impressions": imps})
        tally = {v: sum(1 for r in rows if r["verdict"] == v)
                 for v in ("keep", "improve", "prune", "unjudged")}
        out.append({"shape": c["shape"], "size": c["size"], "tally": tally, "pages": rows})
    return out


def doorway_findings(groups):
    judged = [r for g in groups for r in g["pages"] if r["verdict"] != "unjudged"]
    if not judged:
        return []
    template = [r for r in judged if (r["local_substance"] or 0) < 0.3]
    prune = [r for r in judged if r["verdict"] == "prune"]
    lines = "; ".join(
        f"{g['shape']}: keep {g['tally']['keep']}, improve {g['tally']['improve']}, "
        f"prune {g['tally']['prune']}"
        for g in groups[:8]
    )
    return [{
        "priority": "P1" if len(template) >= 10 else "P2",
        "title": "Location pages judged as template copy (doorway risk, model-verified)",
        "description": f"{len(template)} of {len(judged)} templated pages were judged to "
        "carry no genuinely location-specific substance (place name swapped into "
        f"generic copy). Suggested: prune {len(prune)}. Per template: {lines}. "
        "Judgments are triage-grade: spot-check before deleting.",
        "fix": "Prune pages marked prune (301 to the hub or noindex), add real local "
        "substance to pages marked improve, keep the rest. Full per-URL verdicts with "
        "reasons are in the jev.py output.",
        "effort": "high",
        "module": MODULE,
        "count": len(template),
    }]


def fanout_items(con, seeds, entity="", location="", top_k=4):
    import fanout as fo

    pages = fo.load_pages(con)
    rows = {r[0]: r for r in con.execute(
        "SELECT url,title,h1,meta_desc,headings,"
        + ("main_excerpt" if "main_excerpt" in _cols(con) else "NULL")
        + " FROM pages WHERE indexable=1")}
    items, meta = [], []
    for seed in seeds:
        for sq in fo.build_fanout(seed, entity, location):
            if sq["type"] == "branded":
                continue
            q = fo.tokens(sq["query"])
            if not q:
                continue
            ranked = sorted(pages, key=lambda p: -len(q & p["all"]))[:top_k]
            for p in ranked:
                if not q & p["all"]:
                    continue
                iid = f"{sq['query']}||{p['url']}"
                state = {"query": sq["query"], **_page_state(rows[p["url"]])}
                items.append((iid, state, FANOUT_QUESTION))
                meta.append({"id": iid, "seed": seed, "query": sq["query"],
                             "type": sq["type"], "url": p["url"]})
    return items, meta


def fanout_results(meta, answers, threshold=0.6):
    best = {}
    for m in meta:
        p = noul(answers.get(m["id"]), "answers_query")
        k = (m["seed"], m["query"])
        cur = best.get(k)
        if cur is None or (p or 0) > (cur["p"] or 0):
            best[k] = {**m, "p": p}
    by_seed = {}
    for (seed, _), b in best.items():
        by_seed.setdefault(seed, []).append({
            "query": b["query"], "type": b["type"],
            "answered": (b["p"] or 0) >= threshold,
            "best_url": b["url"] if (b["p"] or 0) >= threshold else None,
            "p": b["p"],
        })
    results, findings = [], []
    for seed, subs in by_seed.items():
        n = len(subs)
        ok = sum(s["answered"] for s in subs)
        pct = round(ok / n * 100) if n else 0
        results.append({"seed": seed, "coverage_pct": pct, "subqueries": subs})
        if pct < 60:
            gaps = [s["query"] for s in subs if not s["answered"]]
            findings.append({
                "priority": "P2" if pct < 40 else "P3",
                "title": f"Fan-out sub-queries not answered (model-verified): '{seed}'",
                "description": f"Only {ok} of {n} ({pct}%) sub-queries for '{seed}' have a "
                "page judged to actually answer them. Gaps: " + "; ".join(gaps[:10]),
                "fix": "Answer the gaps with real sections (pricing, process, "
                "comparisons, proof) on the money page or one strong guide.",
                "effort": "medium",
                "module": MODULE,
            })
    return results, findings


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _run(items, args):
    """Get answers for items from whichever backend is configured."""
    backend, base_url, api_key = resolve_backend(args.backend, args.base_url, args.api_key)
    if backend == "agent":
        if args.answers:
            return json.load(open(args.answers, encoding="utf-8")), backend, None
        path = args.export or os.path.join(".fat-work", "jev_batch.json")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": i, "state": s, "questions": q} for i, s, q in items], fh,
                      indent=1)
        print(json.dumps({
            "backend": "agent", "exported": len(items), "batch": path,
            "next": "Answer each item's questions in the Jev answer shape, write "
            "{id: {question_id: answer}} JSON, then re-run with --answers <file>.",
        }))
        return None, backend, None
    client = JevClient(base_url, api_key, args.model, args.cache, workers=args.workers)
    answers = client.ask_many(items)
    return answers, backend, client


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jev / System One judgments for FAT")
    ap.add_argument("task", choices=["ping", "doorway", "fanout"])
    ap.add_argument("--db", help="sitecrawl.py site.db")
    ap.add_argument("--gsc", help="GSC page export (gsc_fetch.py) for doorway triage")
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--entity", default="")
    ap.add_argument("--location", default="")
    ap.add_argument("--limit", type=int, default=0, help="judge at most N items (sampling)")
    ap.add_argument("--per-cluster", type=int, default=None,
                    help="doorway: judge N pages per template (default: all; 5 in agent mode)")
    ap.add_argument("--backend", default="auto", choices=["auto", "typesafe", "local", "agent"])
    ap.add_argument("--base-url")
    ap.add_argument("--api-key")
    ap.add_argument("--model", default=os.environ.get("TYPESAFE_MODEL", DEFAULT_MODEL))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cache", default=os.path.join(".fat-work", "jev_cache.json"))
    ap.add_argument("--export", help="agent backend: where to write the question batch")
    ap.add_argument("--answers", help="agent backend: answers JSON to read back")
    ap.add_argument("--out", help="write full results JSON here")
    args = ap.parse_args(argv)

    if args.task == "ping":
        backend, base_url, api_key = resolve_backend(args.backend, args.base_url, args.api_key)
        if backend == "agent":
            print(json.dumps({"backend": "agent", "ok": True,
                              "note": "no key or server configured; agent mode"}))
            return 0
        c = JevClient(base_url, api_key, args.model, cache_path=None)
        t = time.time()
        try:
            a = c.ask("The page lists our Carlton office address and three Carlton "
                      "client projects.", {"q": DOORWAY_QUESTIONS["local_substance"]})
        except JevError as e:
            print(json.dumps({"backend": backend, "ok": False, "error": str(e)}))
            return 1
        print(json.dumps({"backend": backend, "ok": True, "model": c.served_by,
                          "ms": round((time.time() - t) * 1000), "answer": a}))
        return 0

    if not args.db:
        ap.error("--db is required")
    con = sqlite3.connect(args.db)

    if args.task == "doorway":
        from sitewide import load_gsc_pages, near_duplicate_clusters

        clusters = near_duplicate_clusters(con)
        per = args.per_cluster
        if per is None:  # keyless agent mode samples; model backends judge everything
            per = 5 if resolve_backend(args.backend, args.base_url, args.api_key)[0] == "agent" else 0
        items = doorway_items(con, clusters, per)
        if args.limit:
            items = items[: args.limit]
        answers, backend, client = _run(items, args)
        if answers is None:
            return 0
        gsc = load_gsc_pages(args.gsc) if args.gsc else None
        judged = {i for i, _, _ in items}
        groups = doorway_verdicts(
            [{**c, "urls": [u for u in c["urls"] if u in judged]} for c in clusters
             if any(u in judged for u in c["urls"])],
            answers, gsc)
        findings = doorway_findings(groups)
        result = {"task": "doorway", "groups": groups}
    else:
        seeds = args.seed
        if not seeds:
            ap.error("--seed is required for fanout")
        items, meta = fanout_items(con, seeds, args.entity, args.location)
        if args.limit:
            items = items[: args.limit]
            keep = {i for i, _, _ in items}
            meta = [m for m in meta if m["id"] in keep]
        answers, backend, client = _run(items, args)
        if answers is None:
            return 0
        results, findings = fanout_results(meta, answers)
        result = {"task": "fanout", "results": results}

    errors = sum(1 for a in answers.values() if isinstance(a, dict) and "error" in a)
    result.update({
        "backend": backend,
        "model": client.served_by if client else "agent",
        "usage": client.usage if client else None,
        "judged": len(items),
        "errors": errors,
        "findings": findings,
    })
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    summary = {k: result[k] for k in ("task", "backend", "model", "usage", "judged", "errors")}
    if args.task == "doorway":
        summary["groups"] = [{"shape": g["shape"], **g["tally"]} for g in result["groups"][:12]]
    else:
        summary["coverage"] = {r["seed"]: r["coverage_pct"] for r in result["results"]}
    summary["findings"] = [f["title"] for f in findings]
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
