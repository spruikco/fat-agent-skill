"""Claude's labels (written by hand after reading every item), assembled into ground_truth.json.

doorway: substance = genuine, verifiable, location-specific substance that would justify the
page existing for that place (office/venue address, named local client or project, local
price or dated local event, or a substantial block of real local facts). One templated
'local flavour' sentence naming the region's industries, suburb lists, 'local experts'
claims and unnamed templated testimonials do NOT count.
literal = the page would pass jev.py's question AS WORDED (names at least one real,
checkable local entity: company, institution, landmark, statistic), whatever its purpose.
fanout: answers = a searcher asking the query would find a direct, useful answer on that page
(judged from the whole live page, not only the crawl excerpt).
"""
import json

L = json.load(open("label_doorway.json", encoding="utf-8"))
F = json.load(open("label_fanout.json", encoding="utf-8"))

COP = "one templated flavour sentence naming the region's industries/employers; delivered online from AU, no local client, venue or price"
TPL = "pure template: place name swapped into generic copy"
TEST = "template copy plus an unnamed templated testimonial; nothing checkable about the place"
IND = "real multi-paragraph city market block (named institutions, industries, stats) that is verifiable and specific to the city, though shared by that city's service pages"
SUB = "suburb/neighbourhood list plus unverifiable claims ('500+ businesses served')"

d = {  # index: (substance, literal, reason)
    0: (0, 1, COP + " (Capital One)"), 1: (0, 1, COP + " (BoA, Truist, Wells Fargo)"),
    2: (0, 0, COP + " (no names)"), 3: (0, 1, COP + " (Houston/Dallas/Austin sectors)"),
    4: (0, 0, COP + " (no names)"), 5: (0, 1, COP + " (State of Hawaii)"),
    6: (0, 1, COP + " (Lilly, Roche)"), 7: (0, 0, COP + " (no names)"),
    8: (0, 0, COP + " (no names)"), 9: (0, 1, COP + " (Microsoft, Amazon, Boeing)"),
    10: (0, 1, COP + " (Brown University)"), 11: (0, 1, COP + " (The Loop, West Loop)"),
    12: (0, 0, TPL), 13: (0, 0, TEST), 14: (0, 0, TPL), 15: (0, 0, TPL), 16: (0, 0, TPL),
    17: (0, 0, TPL), 18: (0, 0, TPL), 19: (0, 0, TPL), 20: (0, 0, TPL), 21: (0, 0, TPL),
    22: (0, 0, TPL), 23: (0, 0, TPL), 24: (0, 0, TPL), 25: (0, 0, TPL), 26: (0, 0, TPL),
    27: (0, 0, TPL), 28: (0, 0, TPL), 29: (0, 0, TPL), 30: (0, 0, TPL), 31: (0, 0, TPL),
    32: (0, 0, "booking shell: 'Loading upcoming workshops', no local content in the crawl"),
    33: (0, 0, "booking shell: 'Loading upcoming workshops', no local content in the crawl"),
    34: (0, 0, "'Canberra CBD' venue without an address; otherwise template"),
    35: (0, 0, "'Melbourne CBD' venue without an address; otherwise template"),
    36: (0, 0, "'Hobart CBD' only; template"), 37: (0, 0, "'Southport CBD' only; template"),
    38: (0, 0, TPL), 39: (0, 0, TPL),
    40: (1, 1, IND + " (ASX, RBA, Macquarie, population/CPC stats)"),
    41: (1, 1, IND + " (same Sydney block)"),
    42: (0, 0, TPL), 43: (0, 0, "'Hobart CBD' only; template"),
    44: (1, 1, IND + " (BAE at Osborne, AUKUS, SA wine share)"),
    45: (0, 1, "neighbourhood list and a metro population figure; no local client or venue"),
    46: (0, 1, COP + " (Raymond James, CENTCOM)"), 47: (0, 1, COP + " (Texas Medical Center)"),
    48: (0, 1, COP + " (HCA, Vanderbilt)"), 49: (0, 1, COP + " (AT&T, ExxonMobil, McKesson)"),
    50: (0, 1, COP + " (Coca-Cola, Delta, UPS)"), 51: (0, 1, COP + " (Cisco RTP, SAS)"),
    52: (1, 1, IND + " (LAND 400 at Avalon, Carbon Revolution HQ, Cotton On)"),
    53: (0, 0, SUB), 54: (0, 0, TEST),
    55: (0, 0, "garbled template (place name injected repeatedly), no local facts"),
    56: (0, 0, TEST + " ('Rachel P., Cullen Bay')"), 57: (0, 0, TEST), 58: (0, 0, TEST),
    59: (0, 0, TEST), 60: (0, 0, SUB), 61: (0, 0, SUB),
    62: (0, 1, COP + " (Beltway, federal agencies)"),
}
assert len(d) == len(L)
doorway = [{"url": r["url"], "shape": r["shape"], "substance": bool(d[i][0]),
            "literal": bool(d[i][1]), "reason": d[i][2]} for i, r in enumerate(L)]

Y = {0, 1, 2, 3, 12, 16, 17, 18, 19, 21, 22, 23, 24, 53, 59, 61, 62, 63, 64,
     65, 70, 76, 77, 78, 119, 127}
why = {
    0: "the Melbourne SEO services page", 1: "an SEO agency page for a Melbourne suburb",
    2: "an SEO agency page for a Melbourne suburb", 3: "an SEO agency page for a Melbourne suburb",
    12: "FAQ 'How long does SEO take to work in Melbourne?' with a timeline",
    13: "AI SEO timeline, a different service", 15: "answers it for Perth, not Melbourne",
    16: "FAQ gives $1,500-$5,000/month", 17: "FAQ 'from $990/month'", 18: "FAQ 'from $990/month'",
    19: "FAQ 'from $990/month'", 20: "Brisbane suburb page", 21: "FAQ gives $1,500-$5,000/month",
    22: "FAQ 'from $990/month'", 23: "FAQ 'from $990/month'", 24: "FAQ 'from $990/month'",
    53: "has a Melbourne client search case study section (borderline yes)",
    59: "Melbourne digital agency hub offering SEO, 2026 in title (weak yes)",
    61: "Melbourne SEO page", 62: "suburb SEO page", 63: "suburb SEO page", 64: "suburb SEO page",
    65: "a Claude Code training page (suburb template, weak yes)",
    66: "Copilot training, not Claude Code training", 67: "Cowork course, says it is not Claude Code",
    68: "a build agency page, not training", 70: "describes what the training covers (weak yes)",
    76: "what's included + one-day format (weak yes)", 77: "same template as Hyde Park",
    78: "same template as Hyde Park", 79: "homepage, no training duration",
    80: "Copilot tiers of 2 hours, different course", 81: "Cowork day, different course",
    83: "cost FAQ gives no price ('scoped to your team')", 84: "no price", 85: "no price", 86: "no price",
    119: "case studies page includes a Sydney Claude Code meetup (borderline yes)",
    127: "local Claude Code training page", 115: "agency page, no reviews",
}
fan = []
for i, p in enumerate(F):
    ans = i in Y
    default = ("page does not address this intent (no comparison, reviews, "
               "definition, process or price for it)")
    fan.append({"query": p["query"], "url": p["url"], "answers": ans,
                "reason": why.get(i, "answers it" if ans else default)})

notes = {
    "labeller": "Claude (Opus), reading unique text, crawl excerpt and, where the excerpt was cut, the live page",
    "doorway_rule": __doc__.split("fanout:")[0].strip(),
    "fanout_rule": "a searcher asking the query finds a direct, useful answer on that page",
    "missed_by_both_shortlists": [
        "claude code training / cost / how long: /melbourne/claude-code-training/ states "
        "A$1,095 per seat and a one-day format, and /services/claude-code-training/ is the "
        "national hub, but neither page is ever shortlisted (124 pages tie on token overlap for "
        "'claude code training cost' and 'cost' only appears in body text)"],
}
json.dump({"notes": notes, "doorway": doorway, "fanout": fan},
          open("ground_truth.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(len(doorway), sum(r["substance"] for r in doorway), sum(r["literal"] for r in doorway),
      len(fan), sum(r["answers"] for r in fan))
