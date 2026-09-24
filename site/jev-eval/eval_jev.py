#!/usr/bin/env python3
"""Evaluate Jev-style judgments (OpenJev local, hosted Jev if keyed) against
careful Claude labels, for FAT's two judged tasks: doorway triage and fan-out.

Steps (each writes into this folder):
    python eval_jev.py sample        # stratified doorway sample -> label_doorway.json (blind: no model scores)
    python eval_jev.py fanout-sample # (query, page) pairs for 2 seeds -> label_fanout.json
    # Claude labels both into ground_truth.json
    python eval_jev.py timing        # 50 uncached OpenJev doorway calls on a fresh cache
    python eval_jev.py score         # all comparisons -> results.json

Stdlib only. Uses the FAT scripts unchanged (imports jev, sitewide, fanout).
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "plugins", "fat-agent", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import jev  # noqa: E402
import fanout as fo  # noqa: E402
from sitewide import load_gsc_pages, near_duplicate_clusters, triage, url_key  # noqa: E402

SCR = r"C:\Users\ryesm\AppData\Local\Temp\claude\C--Users-ryesm\6a03cf1a-71a7-43ad-acd3-edd9e1d35d07\scratchpad\spruik"
DB = os.path.join(SCR, "crawl3", "site.db")
GSC = os.path.join(SCR, "gsc_pages_full.json")
FULL_RUN = os.path.join(SCR, "jev_doorway_full.json")
CACHE = os.path.join(SCR, "jev_cache_local4.json")
BASE = "http://127.0.0.1:8000"
MODEL_KEY = "jev-latest"  # the key jev.py's cache used for the full local run
SEEDS = ["seo agency melbourne", "claude code training"]
PRICE_PER_M = 0.042  # hosted Jev, USD per million input tokens

# how many pages to draw per template (shape); OpenJev keeps are added on top
STRATA = {
    "/services/microsoft-copilot-cowork-training/{*}/": 6,
    "/services/claude-code-agency/{*}/": 6,
    "/local/claude-code-agency-in-{*}/": 5,
    "/local/claude-cowork-training-in-{*}/": 4,
    "/local/seo-agency-in-{*}/": 5,
    "/local/claude-code-training-in-{*}/": 3,
    "/local/ai-consultant-in-{*}/": 3,
    "/book/{*}/": 2,
    "/{*}/ai-engineering-workshops/": 2,
    "/{*}/ai-strategy-advisory/": 2,
    "/ai-seo-{*}/": 2,
    "/sydney/{*}/": 2,
    "/{*}/team-ai-adoption/": 1,
    "/{*}/executive-ai-training/": 1,
    "/adelaide/{*}/": 1,
    "/us/{*}/ai-seo/": 1,
}
KEEP_EXTRA_COPILOT = 6  # OpenJev-keep Copilot pages on top of the random 6


def out(name):
    return os.path.join(HERE, name)


def dump(name, obj):
    with open(out(name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)


def load(name):
    with open(out(name), encoding="utf-8") as fh:
        return json.load(fh)


def build():
    con = sqlite3.connect(DB)
    clusters = near_duplicate_clusters(con)
    items = jev.doorway_items(con, clusters)
    return con, clusters, items


def full_run_rows():
    d = json.load(open(FULL_RUN, encoding="utf-8"))
    return {r["url"]: {**r, "shape": g["shape"]} for g in d["groups"] for r in g["pages"]}


# --------------------------------------------------------------------------- #
def cmd_sample():
    con, clusters, items = build()
    by_url = {i: (s, q) for i, s, q in items}
    shape_of = {u: c["shape"] for c in clusters for u in c["urls"]}
    full = full_run_rows()
    rng = random.Random(42)
    chosen = []
    for shape, n in STRATA.items():
        pool = sorted(u for u in by_url if shape_of.get(u) == shape)
        chosen += rng.sample(pool, min(n, len(pool)))
    keeps = sorted(u for u, r in full.items() if r["verdict"] == "keep")
    cop = [u for u in keeps if "copilot" in u and u not in chosen]
    chosen += rng.sample(cop, min(KEEP_EXTRA_COPILOT, len(cop)))
    chosen += [u for u in keeps if "copilot" not in u and u not in chosen]
    rows = []
    for u in chosen:
        st, _ = by_url[u]
        r = con.execute("SELECT title,h1,main_excerpt FROM pages WHERE url=?", (u,)).fetchone()
        rows.append({
            "url": u, "shape": shape_of[u],
            "decided_by_code": st is None,
            "unique_text": st if isinstance(st, str) else "",
            "title": r[0], "h1": r[1], "main_excerpt": r[2],
        })
    dump("label_doorway.json", rows)
    print(json.dumps({"sampled": len(rows),
                      "decided_by_code": sum(r["decided_by_code"] for r in rows)}))


def cmd_fanout_sample():
    con = sqlite3.connect(DB)
    items, meta = jev.fanout_items(con, SEEDS)
    pages = fo.load_pages(con)
    rows = {r[0]: r for r in con.execute(
        "SELECT url,title,h1,headings,main_excerpt FROM pages")}
    pairs = []
    # the pair each method would credit: token-overlap best page + every jev candidate
    for seed in SEEDS:
        for sq in fo.build_fanout(seed):
            if sq["type"] == "branded":
                continue
            m = fo.match(sq["query"], pages)
            cands = [x["url"] for x in meta if x["query"] == sq["query"]]
            for u in dict.fromkeys(([m["url"]] if m["url"] else []) + cands):
                r = rows[u]
                pairs.append({"seed": seed, "query": sq["query"], "type": sq["type"],
                              "url": u, "title": r[1], "h1": r[2],
                              "headings": (r[3] or "")[:600],
                              "excerpt": (r[4] or "")[:700]})
    dump("label_fanout.json", pairs)
    print(json.dumps({"pairs": len(pairs), "jev_items": len(items)}))


def cmd_timing(n=50):
    """Fresh cache: time n real OpenJev doorway calls (sequential and 8 workers)."""
    con, clusters, items = build()
    model_items = [it for it in items if it[1] is not None]
    rng = random.Random(7)
    sub = rng.sample(model_items, n)
    res = {}
    for workers in (1, 8):
        c = jev.JevClient(BASE, None, MODEL_KEY, cache_path=None, workers=workers, timeout=120)
        t = time.time()
        if workers == 1:
            lat = []
            for iid, st, qs in sub:
                t1 = time.time()
                c.ask(st, qs)
                lat.append((time.time() - t1) * 1000)
        else:
            c.ask_many(sub)
            lat = None
        wall = time.time() - t
        res[f"workers_{workers}"] = {
            "calls": n, "wall_s": round(wall, 2), "ms_per_call": round(wall * 1000 / n),
            "input_tokens": c.usage["input_tokens"], "requests": c.usage["requests"],
            "p50_ms": round(sorted(lat)[len(lat) // 2]) if lat else None,
            "p90_ms": round(sorted(lat)[int(len(lat) * 0.9)]) if lat else None,
        }
    res["uncached_items_total"] = len(model_items)
    res["items_total"] = len(items)
    res["tokens_per_call"] = round(res["workers_1"]["input_tokens"] / n)
    dump("timing.json", res)
    print(json.dumps(res, indent=1))


# --------------------------------------------------------------------------- #
def prf(pred, truth):
    tp = sum(p and t for p, t in zip(pred, truth))
    fp = sum(p and not t for p, t in zip(pred, truth))
    fn = sum((not p) and t for p, t in zip(pred, truth))
    tn = sum((not p) and (not t) for p, t in zip(pred, truth))
    n = len(truth)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    return {"n": n, "accuracy": round((tp + tn) / n, 3) if n else None,
            "precision": round(prec, 3) if prec is not None else None,
            "recall": round(rec, 3) if rec is not None else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def auc(pairs):
    """P(score of a random positive > random negative); 0.5 = chance."""
    pos = [p for p, t in pairs if t]
    neg = [p for p, t in pairs if not t]
    if not pos or not neg:
        return None
    s = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return round(s / (len(pos) * len(neg)), 3)


def gt_verdict(substance, clicks, imps):
    if substance or clicks >= 1:
        return "keep"
    if imps < jev.IMPROVE_MIN_IMPRESSIONS:
        return "prune"
    return "improve"


def verdict_agreement(pred, truth):
    labels = ("keep", "improve", "prune")
    conf = {t: {p: 0 for p in labels} for t in labels}
    for p, t in zip(pred, truth):
        conf[t][p] += 1
    agree = sum(p == t for p, t in zip(pred, truth))
    # the costly error: pruning a page that should be kept
    wrong_prune = sum(p == "prune" and t == "keep" for p, t in zip(pred, truth))
    return {"agreement": round(agree / len(truth), 3), "confusion_truth_by_pred": conf,
            "prunes_a_keeper": wrong_prune,
            "counts": {l: sum(p == l for p in pred) for l in labels}}


def cmd_score():
    gt = load("ground_truth.json")
    gsc = load_gsc_pages(GSC)
    full = full_run_rows()
    con, clusters, items = build()
    item_state = {i: s for i, s, _ in items}

    # ---- doorway -------------------------------------------------------------
    D = gt["doorway"]
    urls = [r["url"] for r in D]
    truth = [bool(r["substance"]) for r in D]
    literal = [bool(r["literal"]) for r in D]
    g = [gsc.get(url_key(u)) or {"clicks": 0, "impressions": 0} for u in urls]
    clicks = [x["clicks"] for x in g]
    imps = [x["impressions"] for x in g]
    t = triage(urls, gsc)
    gsc_only = ["keep" if u in t["keep"] else "improve" if u in t["improve"] else "prune"
                for u in urls]
    ojp = [full[u]["local_substance"] for u in urls]
    oj_pred = [p >= 0.7 for p in ojp]
    oj_pred_05 = [p >= 0.5 for p in ojp]
    oj_verdict = [full[u]["verdict"] for u in urls]
    truth_verdict = [gt_verdict(s, c, i) for s, c, i in zip(truth, clicks, imps)]
    # code-diff step alone: "has unique text" as the substance signal
    code_pred = [item_state.get(u) is not None for u in urls]

    by_shape = {}
    for r, tr, pr in zip(D, truth, oj_pred):
        s = by_shape.setdefault(r["shape"], {"n": 0, "truth_yes": 0, "openjev_yes": 0,
                                              "agree": 0})
        s["n"] += 1
        s["truth_yes"] += tr
        s["openjev_yes"] += pr
        s["agree"] += tr == pr

    disagreements = [{
        "url": u, "truth": tr, "openjev_p": round(p, 3), "reason": r["reason"],
        "clicks": c, "impressions": i, "openjev_verdict": v, "truth_verdict": tv,
        "unique_text": (item_state.get(u) or "")[:400]}
        for u, r, tr, p, c, i, v, tv in zip(urls, D, truth, ojp, clicks, imps, oj_verdict,
                                            truth_verdict) if tr != (p >= 0.7) or v != tv]
    per_page = [{"url": u, "truth": tr, "literal": li, "openjev_p": round(p, 3),
                 "openjev_verdict": v, "gsc_only_verdict": gv, "truth_verdict": tv,
                 "clicks": c, "impressions": i}
                for u, tr, li, p, v, gv, tv, c, i in zip(urls, truth, literal, ojp, oj_verdict,
                                                         gsc_only, truth_verdict, clicks, imps)]

    oj_keep = [v == "keep" for v in oj_verdict]
    doorway = {
        "sample_size": len(D),
        "truth_substance_yes": sum(truth),
        "truth_literal_yes": sum(literal),
        "openjev_keeps_in_sample": sum(oj_keep),
        "openjev_keeps_with_real_substance": sum(k and t for k, t in zip(oj_keep, truth)),
        "openjev_keeps_with_clicks": sum(k and c >= 1 for k, c in zip(oj_keep, clicks)),
        "literal_question_classification (does OpenJev answer the question as worded?)": {
            "openjev (noul >= 0.7)": prf(oj_pred, literal),
            "openjev (noul >= 0.5)": prf(oj_pred_05, literal),
            "code_diff_only": prf(code_pred, literal),
        },
        "substance_classification": {
            "no_judge_text_similarity (every templated page = template)":
                prf([False] * len(D), truth),
            "code_diff_only (any unique sentence = substance)": prf(code_pred, truth),
            "openjev (noul >= 0.7, jev.py keep threshold)": prf(oj_pred, truth),
            "openjev (noul >= 0.5)": prf(oj_pred_05, truth),
        },
        "verdicts_vs_truth_derived": {
            "no_judge_gsc_only (sitewide.triage)": verdict_agreement(gsc_only, truth_verdict),
            "no_judge_jev_rule (substance assumed false everywhere, same GSC thresholds)":
                verdict_agreement([gt_verdict(False, c, i) for c, i in zip(clicks, imps)],
                                  truth_verdict),
            "openjev_full_pipeline (jev.py doorway)": verdict_agreement(oj_verdict, truth_verdict),
            "truth_derived": {"counts": {l: truth_verdict.count(l)
                                         for l in ("keep", "improve", "prune")}},
        },
        "by_template": by_shape,
        "disagreements": disagreements,
        "per_page": per_page,
        "hosted_jev": "not evaluated: TYPESAFE_API_KEY not set in user env",
    }

    # ---- fan-out -------------------------------------------------------------
    F = gt["fanout"]
    pages = fo.load_pages(con)
    items_f, meta = jev.fanout_items(con, SEEDS)
    cache = json.load(open(os.path.join(HERE, "jev_cache_fanout.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(HERE, "jev_cache_fanout.json")) else {}
    client = jev.JevClient(BASE, None, MODEL_KEY,
                           cache_path=os.path.join(HERE, "jev_cache_fanout.json"), workers=1,
                           timeout=120)
    t0 = time.time()
    ans = client.ask_many(items_f)
    fan_wall = time.time() - t0
    if client.usage["requests"]:  # first, uncached run: record the real cost
        dump("fanout_timing.json", {"note": "first (uncached) OpenJev fan-out run, workers=1",
                                    "requests": client.usage["requests"],
                                    "input_tokens": client.usage["input_tokens"],
                                    "wall_s": round(fan_wall, 1)})
    ft = load("fanout_timing.json")
    lab = {(r["query"], r["url"]): bool(r["answers"]) for r in F}
    reason = {(r["query"], r["url"]): r["reason"] for r in F}
    # pair-level: token overlap level of THIS page for the query vs OpenJev p for the pair
    def tok_level(query, url):
        p = next(x for x in pages if x["url"] == url)
        return fo.match(query, [p])["level"]
    pair_truth, pair_tok, pair_oj, pair_rows = [], [], [], []
    pmap = {}
    for m in meta:
        pmap[(m["query"], m["url"])] = jev.noul(ans.get(m["id"]), "answers_query")
    for (q, u), tr in lab.items():
        lvl = tok_level(q, u)
        p = pmap.get((q, u))
        pair_truth.append(tr)
        pair_tok.append(lvl in ("page", "section"))
        pair_oj.append((p or 0) >= 0.6)
        pair_rows.append({"query": q, "url": u, "truth": tr, "token_level": lvl,
                          "openjev_p": None if p is None else round(p, 3),
                          "reason": reason[(q, u)]})
    # query-level: is the sub-query answered anywhere on the site?
    q_truth = {}
    for (q, u), tr in lab.items():
        q_truth[q] = q_truth.get(q, False) or tr
    tok_q, oj_q = {}, {}
    for seed in SEEDS:
        for sq in fo.build_fanout(seed):
            if sq["type"] == "branded":
                continue
            m = fo.match(sq["query"], pages)
            tok_q[sq["query"]] = (m["level"] in ("page", "section"), m["url"])
    res_f, _ = jev.fanout_results(meta, ans)
    for r in res_f:
        for s in r["subqueries"]:
            oj_q[s["query"]] = (s["answered"], s["best_url"])
    qs = [q for q in q_truth if q in tok_q and q in oj_q]
    # a method is only right on an "answered" query if the page it credits is a real answer
    def credited_ok(method, q):
        ans_, url = method[q]
        if not ans_:
            return not q_truth[q]
        return lab.get((q, url), False)
    fanout = {
        "pairs_labelled": len(pair_truth),
        "pair_level": {
            "token_overlap (page/section = answered)": prf(pair_tok, pair_truth),
            "openjev (noul >= 0.6)": prf(pair_oj, pair_truth),
        },
        "query_level": {
            "n_queries": len(qs),
            "truth_answered": sum(q_truth[q] for q in qs),
            "token_overlap_claims_answered": sum(tok_q[q][0] for q in qs),
            "openjev_claims_answered": sum(oj_q[q][0] for q in qs),
            "token_overlap_correct": sum(credited_ok(tok_q, q) for q in qs),
            "openjev_correct": sum(credited_ok(oj_q, q) for q in qs),
        },
        "coverage_pct": {
            "token_overlap": {s: None for s in SEEDS},
            "openjev": {r["seed"]: r["coverage_pct"] for r in res_f},
        },
        "pairs": pair_rows,
        "openjev_calls": {"requests": ft["requests"], "input_tokens": ft["input_tokens"]},
        "openjev_wall_s": ft["wall_s"],
        "openjev_ms_per_call": round(ft["wall_s"] * 1000 / ft["requests"]),
        "openjev_items": len(items_f),
    }
    # branded sub-queries (jev.py skips these; token overlap still "credits" a page)
    fanout["branded_token_overlap_examples"] = {
        q: fo.match(q, pages) for q in ("spruik reviews", "is spruik any good",
                                        "spruik pricing", "spruik alternatives")}
    tokres = fo.analyse(SEEDS, pages)
    fanout["coverage_pct"]["token_overlap"] = {r["seed"]: r["coverage_pct"]
                                               for r in tokres["results"]}

    # ---- speed / cost ----------------------------------------------------------
    timing = load("timing.json") if os.path.exists(out("timing.json")) else {}
    n_items = len(items)
    n_model = sum(1 for _, s, _ in items if s is not None)
    tpc = timing.get("tokens_per_call")
    speed = {
        "doorway_pages": n_items,
        "decided_by_code_no_model_call": n_items - n_model,
        "model_calls_needed": n_model,
        "timing_sample": timing,
    }
    if timing:
        ms1 = timing["workers_1"]["ms_per_call"]
        ms8 = timing["workers_8"]["ms_per_call"]
        speed["est_full_run_wall_s_sequential"] = round(n_model * ms1 / 1000)
        speed["est_full_run_wall_s_8_workers"] = round(n_model * ms8 / 1000)
        speed["est_without_code_diff_wall_s_8_workers"] = round(n_items * ms8 / 1000)
    if tpc:
        # token counts come from OpenJev's usage field, the same field TypeSafe reports
        speed["hosted_jev_est_cost_usd_full_doorway"] = round(n_model * tpc * PRICE_PER_M / 1e6, 5)
        speed["hosted_jev_est_cost_usd_without_code_diff"] = round(
            n_items * tpc * 3 * PRICE_PER_M / 1e6, 5)  # whole page ~3x the unique text (rough)
        speed["note"] = ("without-code-diff cost assumes a full page state is ~3x the "
                         "tokens of the unique-sentence state; rough")
    if fanout["openjev_calls"]["input_tokens"] and fanout["openjev_calls"]["requests"]:
        fpt = fanout["openjev_calls"]["input_tokens"] / fanout["openjev_calls"]["requests"]
        speed["fanout_tokens_per_call"] = round(fpt)
        speed["hosted_jev_est_cost_usd_fanout_2_seeds"] = round(
            len(items_f) * fpt * PRICE_PER_M / 1e6, 6)

    judged = [(p, t, li) for p, t, li, u in zip(ojp, truth, literal, urls)
              if item_state.get(u) is not None]
    fj = [r for r in pair_rows if r["openjev_p"] is not None]
    results_auc = {
        "doorway_all_63 (strict)": auc(list(zip(ojp, truth))),
        "doorway_all_63 (literal)": auc(list(zip(ojp, literal))),
        "doorway_model_judged_only (strict)": auc([(p, t) for p, t, _ in judged]),
        "doorway_model_judged_only (literal)": auc([(p, li) for p, _, li in judged]),
        "doorway_model_judged_n": len(judged),
        "fanout_judged_pairs": auc([(r["openjev_p"], r["truth"]) for r in fj]),
        "fanout_judged_pairs_n": len(fj),
        "note": "0.5 = coin toss; below 0.5 = ranks the wrong way round",
    }
    results = {"auc_openjev": results_auc, "doorway": doorway, "fanout": fanout, "speed_cost": speed,
               "model": "OpenJev on Qwen2.5-3B-Instruct bf16, RTX 4060 (local)",
               "reference": "Claude (Opus) labels, ground_truth.json"}
    dump("results.json", results)
    print(json.dumps({k: v for k, v in doorway.items()
                      if k in ("substance_classification",)}, indent=1))
    print(json.dumps({k: v["agreement"] for k, v in doorway["verdicts_vs_truth_derived"].items()
                      if "agreement" in v}, indent=1))
    print(json.dumps({k: fanout[k] for k in ("pair_level", "query_level", "coverage_pct")},
                     indent=1))
    print(json.dumps(speed, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "score"
    {"sample": cmd_sample, "fanout-sample": cmd_fanout_sample, "timing": cmd_timing,
     "score": cmd_score}[cmd]()
