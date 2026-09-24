# Google Guidelines Reference (current to Sept 2026)

What Google has changed since March 2024, which FAT check covers each change,
and how to use the list to diagnose a traffic drop. Load this when a client
asks "why did we drop?", when an audit turns up `google_guidelines` or
`sitewide` guideline findings, or before writing recommendations about
structured data, snippets or AI Overviews.

Source key: **[P]** Google primary source (Search Central docs, changelog,
Search Status Dashboard, Rater Guidelines PDF). **[S]** trade press only.
Re-verify **[S]** items before quoting them to a client.

---

## 1. Update timeline: line a drop up against this first

Always compare the date of a drop with this table **before** diagnosing
anything. Get the drop date from GSC (`scripts/gsc.py`) or the SEMrush
`domain_rank_history` report.

| Update | Start | Rollout | What it targeted |
|---|---|---|---|
| March 2024 core + spam | 5 Mar 2024 | 45 days | Helpful content system folded into core ranking, so helpfulness became **site-wide**. Scaled content, site reputation and expired domain abuse policies launched [P] |
| June 2024 spam | 20 Jun 2024 | 7 days | General spam [P] |
| August 2024 core | 15 Aug 2024 | 19 days | Broad core [P] |
| November 2024 core | 11 Nov 2024 | 23 days | Broad core. Site reputation policy tightened: first-party involvement doesn't excuse it [P] |
| December 2024 core | 12 Dec 2024 | 6 days | Broad core [P] |
| December 2024 spam | 19 Dec 2024 | 7 days | General spam [P] |
| March 2025 core | 13 Mar 2025 | 14 days | Broad core [P] |
| June 2025 core | 30 Jun 2025 | 17 days | Broad core [P] |
| August 2025 spam | 26 Aug 2025 | 26 days | General spam [P] |
| December 2025 core | 11 Dec 2025 | 18 days | Broad core. Docs now say smaller core updates also happen unannounced [P] |
| February 2026 Discover | 5 Feb 2026 | 22 days | Discover only: less clickbait, more original, local, in-depth content [P] |
| March 2026 spam | 24 Mar 2026 | <1 day | General spam [P] |
| March 2026 core | 27 Mar 2026 | 12 days | Highly volatile [S] |
| May 2026 core | 21 May 2026 | 12 days | Page type matching the query beat raw authority [S] |
| June 2026 spam | 24 Jun 2026 | 2 days | Came nine days after back button hijacking enforcement began. Not link spam or site reputation [dates P, target S] |
| August 2026 spam | 18 Aug 2026 | 3 days | Hit harder than usual: scaled AI or programmatic content, scraped content, thin affiliates [dates P, target S] |

How to read a drop:

- **Drop inside a core update window.** This is a quality reassessment, not a
  penalty. Look for site-wide low-value blocks: `sitewide` findings
  "Templated near-duplicate pages" and "Large share of site is templated
  pages". Recovery usually comes at a later core update, after the fixes.
- **Drop inside a spam update window.** Check the spam-policy findings below.
  Programmatic location/service pages are the most common hit for SMB sites.
- **Sudden total drop, no update running.** Check GSC Manual Actions,
  `noindex` (including in `<body>`), robots.txt, and a broken deploy.
- **Measure it, don't eyeball it.** `scripts/update_impact.py` takes GSC
  clicks by date (or SEMrush `domain_rank_history`) and prints the before/after
  change across every update window, worst first.
- **Keywords up, traffic down.** Lots of new low-position rankings from
  templated pages while head terms slide. This is the scaled-content shape.
  Confirm with SEMrush `domain_organic_unique`: are the ranking URLs mostly
  one URL pattern?

---

## 2. Spam policies → FAT checks

Spam policies page last updated 28 Aug 2026 [P]. Since 15 May 2026 the
policies also apply to generative AI answers in Search [P].

| Policy | FAT check | Module | Priority |
|---|---|---|---|
| Doorway abuse | Templated near-duplicate pages (simhash clusters over main content, nav/footer excluded) | `sitewide` | P1 (≥10 pages) / P2 |
| Scaled content abuse | Large share of site is templated pages (≥30% of indexable, ≥20 pages) | `sitewide` | P1 |
| Scaled content abuse | Unedited AI output (`As an AI language model`, `[City]`, `{{keyword}}`) | `google_guidelines` | P1 |
| Scaled content abuse / Lowest-rated filler | Generic filler phrasing (3+ stock phrases) | `google_guidelines` | P2 |
| Keyword stuffing | Location list stuffing (10+ comma-separated place names) | `google_guidelines` | P2 |
| Keyword stuffing | Keyword repetition in body (top term >4% of copy, P2 above 6%) | `google_guidelines` | P3 / P2 |
| Keyword stuffing | Keyword-stuffed titles / meta descriptions | `google_guidelines`, `sitewide` | P2 |
| Hidden text and links | Inline-styled hidden blocks with 25+ words (menus, modals, tabs excluded) | `google_guidelines` | P2 (verify) |
| Sneaky redirects | Conditional JS redirect on user agent / referrer | `google_guidelines` | P1 |
| **Back button hijacking** (added Apr 2026, enforced from 15 Jun 2026) | `popstate` handler that redirects or opens a page; soft note on pushState/replaceState calls | `google_guidelines` | P1 / P3 |
| Link spam | Affiliate/paid outbound links without `rel="sponsored"` or `nofollow` | `google_guidelines` | P2 |
| Site reputation abuse | Sections with coupon, gambling, loan, CBD or "best X" URL patterns | `sitewide` | P2 (verify) |
| Self-serving reviews | AggregateRating on LocalBusiness/Organization | `schema_validator` | existing |
| Expired domain abuse | Not automated. Compare Wayback topic with the current topic manually | — | manual |
| Cloaking | Not automated. Fetch with a Googlebot UA and a browser UA and diff | — | manual |

**Site reputation abuse in the EEA.** Since 30 Aug 2026 Google no longer
demotes these sections via manual action inside the EEA. It ranks them on
their own merits instead [P docs, detail S]. Australia, NZ, the UK and the
US are still fully enforced.

### What a doorway fix looks like

The doorway finding lists each cluster as a URL shape, e.g.
`/local/seo-agency-in-{*}/ (240 pages, ~450 words each)`. For each cluster:

1. **Keep** pages that earn traffic or leads (check GSC clicks) **and** can
   carry genuinely local substance: local clients and case studies, photos,
   staff, suburb-specific pricing or regulations, FAQs that differ.
2. **Merge and 301** the rest into one strong city or service hub.
3. **Noindex** while rewriting if a page must stay live for ads or links.
4. Remove them from the sitemap and the internal link blocks that list them.
5. Re-crawl. The cluster should shrink or disappear.

Don't just rewrite intros with an LLM to make the fingerprint differ. That
turns one scaled-content problem into another, and raters are told to rate
suspected scaled content Lowest "even if you are unsure of the method of
creation" [P].

---

## 3. Quality Rater Guidelines (current PDF: 11 Sep 2025) [P]

The substantive AI changes landed in January 2025. The Sept 2025 revision
was minor.

- Using generative AI "alone does not determine the level of effort or Page
  Quality rating". Low effort and no added value are what get rated down.
- **4.6.5 Scaled content abuse**: Lowest, when raters strongly suspect it.
- **4.6.6 Little effort, originality or added value**: Lowest if nearly all
  main content is copied, paraphrased, AI-generated or reposted, even with
  credit. Tells include "As an AI…" and templated Q&A built from People Also
  Ask.
- **5.2.2 Filler**: Low, when filler pushes the helpful content down.
- **Deception about purpose or ownership**: Lowest. Raters look for who runs
  the site, About, contact and customer-service details (`eeat` module).

---

## 4. Structured data: what still earns a result

| Status | Types |
|---|---|
| **Retired** (markup harmless, no rich result) | FAQPage (7 May 2026), HowTo (2023), sitelinks search box / `SearchAction` (Nov 2024), Book Actions, Course Info, ClaimReview, Estimated Salary, Learning Video, Special Announcement, Vehicle Listing (June 2025), practice problems (docs removed Jan 2026), Dataset (Dataset Search only) |
| **Still earns results** | Organization, LocalBusiness, Product / merchant listing, Review snippet (non-self-serving), Article, BreadcrumbList, Event, JobPosting, Recipe, Video, Discussion Forum, QAPage, WebSite (site name) |

FAT's `google_guidelines` module and `sitewide` flag retired markup as **P3,
informational**. Never tell a client that FAQ markup will get them stars.
`suggest_schema.py` no longer emits `SearchAction` and ranks FAQPage P3
with that caveat.

Review snippets (24 Jul 2026 guideline) [P]: no fake reviews, and no
incentivised reviews unless the incentive is clearly disclosed.

---

## 5. Snippets, titles, indexing limits

| Guidance | FAT check |
|---|---|
| Titles past about 60 characters are truncated and more often rewritten. `og:title` is now a title-link source (Aug 2024) | Title likely truncated (P3), keyword-stuffed title (P2) |
| Meta descriptions have **no length limit**. Google truncates on display, keep them unique and human-readable | Too short under 70 (P3), display truncation over 160 (P3), stuffed (P2), duplicates (`sitewide`) |
| `nosnippet` / `max-snippet:0` also remove the page from AI Overviews and AI Mode. `data-nosnippet` works only on span, div and section | Snippets suppressed (P3) |
| Robots meta tags are honoured **in the `<body>`** (Mar 2026) | noindex robots meta inside `<body>` (P0) |
| Googlebot indexes only the first **2MB** of uncompressed HTML | HTML exceeds 2MB (P1) |
| Favicon: square, at least 8x8, 48x48+ recommended. BMP, GIF, ICO, PNG, JPEG, PPM or TIFF. SVG isn't listed | No favicon / SVG-only favicon (P3) |
| Site name comes from WebSite structured data on the homepage | No WebSite site-name markup (P3) |
| Don't fake freshness | Future dates (P2), dateModified before datePublished (P3) |
| One URL per page | Same page indexable with and without trailing slash (`sitewide`, P1) |

---

## 6. AI features: what Google actually says (15 May 2026 guide) [P]

- To appear in AI Overviews or AI Mode a page must be indexed and
  snippet-eligible. There are "no additional requirements".
- Non-commodity content matters: "don't just recycle".
- No special schema is needed. `llms.txt` "neither harms nor helps" for
  Google. Chunking or "writing for AI" isn't needed.
- `Google-Extended` controls training and grounding in other Google
  products. It does **not** control inclusion in AI Overviews.
- Preferred sources: domain or subdomain sites can add the preferred-source
  button (Aug 2026) or deeplink `google.com/preferences/source?q=<site>`.

Keep FAT's `ai_search` llms.txt finding framed for **non-Google** answer
engines. Don't claim it helps Google.

### 6a. What the data shows (practitioner studies, correlation only)

Google says "no special optimisation". The studies below say what tends to
come with being cited. None of it proves cause, so treat it as direction,
not as a formula.

| Finding | Source |
|---|---|
| AI Mode and AI Overviews "may use a 'query fan-out' technique, issuing multiple related searches across subtopics" | Google AI features doc [P] |
| Patent US12158907B1 "Thematic search": summarise top results, cluster them into themes, rank themes by how many documents mention them | Google patent [P] |
| Pages ranking for fan-out sub-queries are **161% more likely** to be cited. The number of fan-outs a page ranks for correlates 0.77 with citation | Surfer, Dec 2025, 10k keywords [S] |
| Only about 38% of AI Overview citations rank top 10 for the same query, down from about 76% in mid-2025 | Ahrefs, 863k SERPs [S] |
| Brand web mentions correlate 0.66 with AI Overview visibility. Backlinks 0.22, DR 0.33 | Ahrefs, 75k brands [S] |
| YouTube mentions correlate about 0.74 across ChatGPT, AI Mode and AIO | Ahrefs follow-up [S] |
| Reddit 40%, Wikipedia 26%, YouTube 24% of AI responses cite them | Semrush, 150k citations [S] |
| Local AI answers lean on directories and review platforms: Yelp, BBB and Angi dominate in the US, with Yelp strongest in AI Mode. ChatGPT local leans on Bing Places | Foundation/AirOps 2026, Whitespark, BrightLocal [S] |
| Google recommends a Google Business Profile for local visibility in AI responses | AI optimisation guide [P] |

All of this data is US-based. In Australia the directory set differs (True
Local, Yellow Pages, hipages, Oneflare, Product Review, Word of Mouth) and
nobody has published an AU study. Test it rather than assume it.

**How FAT covers it:**
- **Fan-out coverage (on-site).** `scripts/fanout.py` builds typed sub-queries
  per seed (templates, optional Google Autocomplete, optional LLM-written
  set) and scores whether the site has a page or section for each. See
  SKILL.md 1.29.
- **Who gets cited (off-site).** Feed the fan-out set into
  `scripts/ai_visibility.py --queries` for citation rate and the competitor
  and community domains that do get cited.
- **Entity grounding.** `ai_search`: Organization/sameAs, Wikidata lookup,
  entity signals.
- **Local listings and citations.** Not automated here. Local listing and
  citation consistency is a separate workstream (use your citation tool of
  choice). Bring the results into the report by hand.

Frame it for clients like this: AI search is entity SEO with more at stake.
Be the business the web keeps mentioning (reviews, directories, Reddit,
YouTube, press, "best X" lists) and answer the whole cluster of questions
around a topic, not just the head term.

---

## 7. Wording rules for client reports

Google's third-party SEO tools guidance (5 Jun 2026) [P] says tools "don't
have access to our internal ranking data". So in reports:

- Say "consistent with the pattern Google's spam policies describe", never
  "Google has penalised you" (unless there's a Manual Action in GSC).
- Say "likely contributed", not "caused", when lining a drop up with an
  update.
- Never promise rankings or rich results.

---

## Sources

- Search Central changelog: https://developers.google.com/search/updates
- Status dashboard history: https://status.search.google.com/products/rGHU1u87FJnkP6W2GwMi/history
- Spam policies: https://developers.google.com/search/docs/essentials/spam-policies
- AI features: https://developers.google.com/search/docs/appearance/ai-features
- AI optimisation guide: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Robots meta: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Snippets: https://developers.google.com/search/docs/appearance/snippet
- Favicon: https://developers.google.com/search/docs/appearance/favicon-in-search
- Review snippet: https://developers.google.com/search/docs/appearance/structured-data/review-snippet
- Preferred sources: https://developers.google.com/search/docs/appearance/preferred-sources
- Third-party SEO: https://developers.google.com/search/docs/fundamentals/third-party-seo
- Rater Guidelines PDF: https://guidelines.raterhub.com/searchqualityevaluatorguidelines.pdf
- Thematic search patent: https://patents.google.com/patent/US12158907B1/en
- Surfer fan-out study: https://searchengineland.com/ai-overview-fan-out-rankings-boost-citation-odds-study-466426
- Ahrefs brand correlation: https://ahrefs.com/blog/ai-overview-brand-correlation/
- Semrush most-cited domains: https://www.semrush.com/blog/most-cited-domains-ai/
- iPullRank query fan-out: https://ipullrank.com/expanding-queries-with-fanout
- BrightLocal ChatGPT sources: https://www.brightlocal.com/research/uncovering-chatgpt-search-sources/
