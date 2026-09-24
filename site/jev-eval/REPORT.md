# Do Jev-style judgements improve FAT? An honest test on spruik.co

24 September 2026. Site: spruik.co (crawl3, 659 templated pages in 39 near-duplicate clusters, full GSC page export). Judge under test: OpenJev on Qwen2.5-3B-Instruct (bf16, RTX 4060), run through `scripts/jev.py` exactly as shipped in v3.8.4. Reference: Claude (Opus) labels, written by hand after reading every item. Hosted TypeSafe Jev was not evaluated (no `TYPESAFE_API_KEY` set).

## Headline

| Measure | No judge | OpenJev (local, 3B) | Hosted Jev | Claude (reference) |
|---|---|---|---|---|
| Doorway: pages with real local substance found (of 4) | 0 of 4 | 1 of 4 | not tested | 4 of 4 |
| Doorway: template pages wrongly called "local substance" (of 59) | 0 | 15 | not tested | 0 |
| Doorway: substance accuracy (63 pages) | 93.7% | 71.4% | not tested | 100% |
| Doorway: ranking quality on judged pages (AUC, 0.5 = coin toss) | n/a | 0.24 (purpose), 0.40 (question as worded) | not tested | n/a |
| Keep/improve/prune agreement with ground truth | 61.9% (GSC only); **95.2%** (jev.py rule, no model) | 57.1% | not tested | 100% |
| Template pages it would tell you to keep | 0 | 14 | not tested | 0 |
| Fan-out: (query, page) accuracy, 132 pairs | **76.5%** (token overlap) | 70.5% | not tested | 100% |
| Fan-out: ranking quality (AUC) | n/a | 0.52 | not tested | n/a |
| Fan-out: sub-queries handled correctly (of 32) | 21 | 16 | not tested | 32 |
| Speed | instant | 1.1 s per doorway judgement, 8.0 s per fan-out judgement | not tested | minutes of reading |
| Cost for this site | $0 | $0 (local GPU) | est. US$0.006 doorway + US$0.004 fan-out | a Claude session |

## Key finding

On this site the local OpenJev judge made FAT's results worse, not better. For doorway triage it ranked pages below coin-toss (AUC 0.24) and would have kept 14 template pages. The full pipeline with the model agreed with ground truth less often (57%) than a plain GSC triage (62%) and far less than jev.py's own verdict rule with the model switched off (95%). The deterministic code diff did the useful work: 388 of 659 pages (59%) decided without a model call, with no page of real substance wrongly dismissed in the sample. For fan-out, OpenJev performed at chance (AUC 0.52) and lost to token overlap.

## Examples

1. `/hobart-digital-marketing-agency/` scored 0.986 and was kept on the strength of a suburb list and "500+ Hobart Businesses Served". Zero clicks, zero impressions. Ground truth: prune.
2. `/local/seo-agency-in-port-adelaide-adelaide/` scored 0.905 from an unnamed templated testimonial, the exact pattern the question says to ignore.
3. `/services/microsoft-copilot-cowork-training/atlanta/` scored 0.905 for one templated sentence naming local employers. Near-identical Texas and Rhode Island pages scored 0.08 and 0.00.
4. `/sydney/email-marketing/` has a genuine Sydney market block, but its cluster varies by service, so the diff compared it with another Sydney page, stripped the Sydney content and asked the model about "email marketing" as if it were the location. Pruned; should be kept. (Fixed in v3.8.5.)
5. Fan-out: `/melbourne/seo-services/` scored 0.000 for "seo agency melbourne" and for a cost query it answers ("$1,500-$5,000/month"), while Box Hill template pages scored 0.95.
6. Where token overlap was wrong and OpenJev right: FAQ headings "How much does a claude code training cost in Hyde Park?" with no price in the answer. One pattern, not a trend.

## What System One judging is good for in FAT (on this evidence)

- Cheap, typed yes/no plumbing: the wire format, caching and agent fallback all work; a whole-site hosted pass costs well under a cent.
- The architecture: decide everything possible in code first, send only the remainder to a judge.

Not good for, with Qwen2.5-3B via OpenJev: purpose-level judgements ("is this a doorway page"), fan-out answer matching, or replacing GSC and the code diff.

## Limitations

One labeller (Claude); only 4 positives in the doorway sample; sample enriched with OpenJev keeps (AUC unaffected); verdict agreement shares GSC thresholds with the baselines; fan-out recall not measured; one site, one small model. Hosted Jev may behave very differently.

## What changed as a result (v3.8.5)

- Model verdicts from local or hosted judges are advisory by default. They only change keep/improve/prune with `--trust-judge`, after validating on your own labelled sample. Claude (agent mode) answers are trusted.
- Default `--workers 1` for local servers (one GPU queues requests).
- The diff now skips clusters whose varying URL segment is a service rather than a place.

Files: `eval_jev.py`, `make_ground_truth.py`, `ground_truth.json`, `results.json`, timing files. Re-score hosted Jev by setting `TYPESAFE_API_KEY`, running `jev.py doorway --backend typesafe`, then `python eval_jev.py score`.
