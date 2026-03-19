# Performance Budget Configuration

Performance budgets help catch regressions by setting thresholds for key metrics.
When a budget is exceeded, FAT Agent flags it as a P2 Medium issue.

## Default Budgets

FAT Agent applies these defaults when no custom budget file is found:

| Metric | Default | Why |
|--------|---------|-----|
| HTML size | < 100 KB | Large HTML delays First Contentful Paint |
| Inline assets (total) | < 50 KB | Inline scripts/styles bypass caching |
| Render-blocking scripts | ≤ 2 | Each blocks the parser until downloaded + executed |
| Non-lazy images | ≤ 3 | Only above-fold images should load eagerly |
| External scripts | ≤ 15 | Each script is a network request + parse cost |
| External stylesheets | ≤ 5 | Stylesheets block rendering until loaded |

## Custom Budgets: `.fat-budget.json`

Create a `.fat-budget.json` file in your project root to override defaults:

```json
{
  "html_kb": 100,
  "inline_total_kb": 50,
  "render_blocking_scripts": 2,
  "images_without_lazy": 3,
  "external_scripts": 15,
  "external_stylesheets": 5
}
```

Only include the keys you want to customise — FAT Agent uses defaults for the rest.

### Usage

```bash
# Auto-detect .fat-budget.json in current directory
python scripts/analyse-html.py page.html

# Specify a custom budget file
python scripts/analyse-html.py --budget .fat-budget.json page.html
```

## Per-Page-Type Budgets

Different page types have different performance characteristics. Suggested budgets:

### Homepage / Landing Page
```json
{
  "html_kb": 80,
  "inline_total_kb": 30,
  "render_blocking_scripts": 1,
  "images_without_lazy": 2,
  "external_scripts": 10,
  "external_stylesheets": 3
}
```

### Blog Post / Article
```json
{
  "html_kb": 120,
  "inline_total_kb": 20,
  "render_blocking_scripts": 1,
  "images_without_lazy": 1,
  "external_scripts": 8,
  "external_stylesheets": 3
}
```

### Product Page (E-commerce)
```json
{
  "html_kb": 150,
  "inline_total_kb": 50,
  "render_blocking_scripts": 2,
  "images_without_lazy": 3,
  "external_scripts": 15,
  "external_stylesheets": 5
}
```

### Web App / Dashboard
```json
{
  "html_kb": 200,
  "inline_total_kb": 80,
  "render_blocking_scripts": 3,
  "images_without_lazy": 5,
  "external_scripts": 25,
  "external_stylesheets": 8
}
```

## Core Web Vitals Targets

These budgets map to Google's Core Web Vitals thresholds:

| CWV Metric | Good | Needs Improvement | Poor |
|------------|------|-------------------|------|
| LCP (Largest Contentful Paint) | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| INP (Interaction to Next Paint) | ≤ 200ms | ≤ 500ms | > 500ms |
| FCP (First Contentful Paint) | ≤ 1.8s | ≤ 3.0s | > 3.0s |
| TTFB (Time to First Byte) | ≤ 800ms | ≤ 1800ms | > 1800ms |

### How budgets relate to CWV

- **HTML size → LCP, FCP, TTFB** — Smaller HTML means faster initial render
- **Render-blocking scripts → LCP, FCP** — Each blocking script delays paint
- **Inline asset size → FCP** — Large inline code delays first render
- **Non-lazy images → CLS, LCP** — Eager-loaded off-screen images waste bandwidth
- **External scripts → INP** — More scripts = more main-thread work = slower interactions

## PageSpeed Insights Integration

FAT Agent can fetch live CWV data from the PageSpeed Insights API (no key required):

```
https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest?url={URL}&strategy=mobile
https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest?url={URL}&strategy=desktop
```

When available, CWV results are factored into the performance score:
- **Good CWV** → Bonus points added to performance score
- **Poor CWV** → Penalty applied to performance score
- **CWV summary table** included in the FAT report

## Scoring Impact

Budget violations affect the FAT performance score:
- Each violation adds a P2 Medium issue
- Violations don't directly reduce the numeric score (they're flagged for review)
- Multiple violations suggest the page needs a performance audit

## CI/CD Integration

Performance budgets work well in CI/CD pipelines:

```bash
# Fail the build if any budget is exceeded
python scripts/analyse-html.py --budget .fat-budget.json page.html \
  | python scripts/calculate-score.py \
  | python -c "
import sys, json
data = json.load(sys.stdin)
violations = data.get('summary', {}).get('medium', [])
budget_issues = [v for v in violations if 'Budget exceeded' in v]
if budget_issues:
    for issue in budget_issues:
        print(f'FAIL: {issue}', file=sys.stderr)
    sys.exit(1)
print('All budgets within limits')
"
```

See `references/ci-cd-integration.md` for complete CI/CD examples.
