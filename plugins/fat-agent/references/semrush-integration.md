# SEMrush Integration (Optional)

FAT Agent can enrich the SEO audit with real SEMrush data — domain authority,
organic keyword and traffic figures, the historical trend, and top keyword
positions. This powers the domain-intelligence charts and the SEMrush section of
the Word/PowerPoint/HTML reports.

SEMrush enrichment is **entirely optional** and **off by default**. The audit
runs fully without it; SEMrush data simply adds an extra layer when available.

## Security: bring your own key

> **Your API key is never stored in this skill or committed to any repository.**

`semrush.py` reads the key from the **`SEMRUSH_API_KEY` environment variable** at
runtime (or the `--api-key` flag for ad-hoc use). The key:

- is never hardcoded in the skill,
- is never written into `semrush.json` or any report,
- is redacted from every error message (the request URL, which embeds the key,
  is never surfaced).

If no key is present, the script prints `{"available": false}` and exits cleanly
so the audit pipeline continues unaffected.

### Setting your key

Use **your own** SEMrush API key (Account → Subscription info → API units).

```bash
# macOS / Linux (current shell)
export SEMRUSH_API_KEY="your-key-here"

# Windows PowerShell (current session)
$env:SEMRUSH_API_KEY = "your-key-here"
```

To persist it, add it to your shell profile, or set it for Claude Code via an
`env` entry in your settings (see `.env.example` for the variable name). Do **not**
commit a real key — `.env` files are gitignored.

## Usage

```bash
python scripts/semrush.py --domain example.com --database au --output /tmp/semrush.json
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--domain` | (required) | Domain to analyse, e.g. `example.com` |
| `--database` | `au` | SEMrush database code (`au`, `us`, `uk`, ...) — match the site's market |
| `--api-key` | `$SEMRUSH_API_KEY` | Key override; defaults to the environment variable |
| `--history-limit` | `24` | Number of historical periods for the trend |
| `--keyword-limit` | `30` | Number of top keywords to pull |
| `--output` | stdout | Write `semrush.json` to this path |

The resulting `semrush.json` is consumed directly by the chart and report steps:

```bash
python scripts/generate-charts.py --scores /tmp/scores.json --semrush /tmp/semrush.json --output-dir /tmp/charts
python scripts/generate-report.py  --scores /tmp/scores.json --semrush /tmp/semrush.json --url example.com --charts-dir /tmp/charts --output-dir ./reports
```

## API endpoints used

All on the SEMrush Analytics API with the same key:

| Report | Endpoint `type` | Provides |
|--------|-----------------|----------|
| Domain overview | `domain_ranks` | organic keywords, organic traffic, traffic cost |
| Rank history | `domain_rank_history` | traffic & keyword trend, MoM change |
| Organic positions | `domain_organic` | top keywords, position distribution |
| Backlinks overview | `backlinks_overview` | authority score, backlinks, referring domains (best-effort) |

Each call consumes SEMrush API units. History and keyword/backlink calls are
best-effort: if one fails (e.g. plan limits), that section is left empty rather
than failing the whole audit.

## Output schema

`semrush.json` matches the format documented in the `generate-charts.py` docstring:

```json
{
  "available": true,
  "domain": "example.com",
  "authority_score": 22,
  "organic_traffic": 1200,
  "traffic_change": "-12%",
  "organic_keywords": 641,
  "keywords_change": "-2.7%",
  "referring_domains": 164,
  "backlinks": 1300,
  "traffic_cost": 2000,
  "traffic_trend": [{"month": "Apr 24", "organic": 800, "paid": 0, "branded": 0}],
  "keywords_trend": [{"month": "Apr 24", "total": 500}],
  "position_distribution": {"top3": 86, "4-10": 73, "11-20": 132, "21-50": 323, "51-100": 27},
  "top_keywords": [{"keyword": "example query", "position": 1, "volume": 720, "traffic_pct": "14.7%"}]
}
```

## Alternatives to an API key

- **SEMrush MCP server** — if connected, FAT Agent can use its tools to gather the
  same fields and write `semrush.json`.
- **Browser automation** — if browser tools are available, FAT Agent can read the
  figures from the SEMrush web UI as a fallback.
