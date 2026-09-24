#!/usr/bin/env python3
"""Build the FAT Agent site into site/dist (Netlify) from index.template.html.

Pages: /            (index.template.html + chart)
       /security/   (security deep dive)
       /dossier/    (every finding FAT can raise, pulled from the plugin source)

The dossier is generated from the finding titles in plugins/fat-agent/scripts, so
the site can never claim a check the code doesn't make.
"""
import glob
import html
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "plugins", "fat-agent", "scripts")
DIST = os.path.join(HERE, "dist")

tpl = open(os.path.join(HERE, "index.template.html"), encoding="utf-8").read()
chart = open(os.path.join(HERE, "chart.svg.part"), encoding="utf-8").read()
STYLE = tpl[tpl.index("<style>"): tpl.index("</style>") + len("</style>")].replace("url(assets/", "url(/assets/")
FONTS = tpl[tpl.index('<link rel="preconnect"'): tpl.index("<style>")]
BODY = tpl[tpl.index("</style>") + len("</style>"):]
SCRIPT = BODY[BODY.index("<script>"):]

EXTRA_CSS = """<style>
.page-hero{padding-block:clamp(48px,7vw,88px) clamp(32px,5vw,56px);background:
  radial-gradient(ellipse 45% 70% at 80% 30%,rgba(200,16,46,.12),transparent 70%),linear-gradient(180deg,var(--night),#0c0e13)}
.page-hero .wrap{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}
@media (max-width:880px){.page-hero .wrap{grid-template-columns:1fr}}
.page-hero h1{font-family:var(--display);font-weight:400;font-size:clamp(44px,7vw,92px);line-height:.95;margin:12px 0 18px}
.page-hero h1 .red{color:var(--stamp-soft);display:block}
.page-hero .wrap>img{width:min(100%,300px);justify-self:center;height:auto}
.page-hero .scene img{width:100%}
.counters{display:flex;flex-wrap:wrap;gap:12px 30px;margin-top:26px;font-family:var(--type);color:var(--chrome-dim)}
.counters b{font-family:var(--display);font-weight:400;font-size:30px;color:var(--chrome);margin-right:8px}
.nav nav a[aria-current="page"]{color:var(--chrome);text-decoration:underline;text-underline-offset:6px}
.list{list-style:none;margin:10px 0 0;padding:0;display:grid;gap:6px}
.list li{font-family:var(--type);font-size:14px;line-height:1.4;padding-left:18px;position:relative;color:#3a3020}
.list li::before{content:"";position:absolute;left:2px;top:.55em;width:7px;height:7px;border:2px solid var(--stamp);border-radius:1px;transform:rotate(45deg)}
.paths{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.paths code{font-family:var(--mono);font-size:12.5px;background:rgba(43,36,24,.1);border:1px solid rgba(43,36,24,.25);padding:2px 6px;border-radius:3px;color:var(--manila-ink)}
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0;border:1px solid var(--line);border-radius:4px;overflow:hidden}
.rule{padding:24px 22px;background:var(--asphalt);display:grid;gap:8px;align-content:start}
.rule+.rule{border-left:1px solid var(--line)}
@media (max-width:860px){.rule+.rule{border-left:0;border-top:1px solid var(--line)}}
.rule h3{font-family:var(--type);font-weight:400;font-size:17px;letter-spacing:.12em;text-transform:uppercase;color:var(--manila)}
.rule p{color:#bfc5ce;font-size:16px}
.sev{width:100%;border-collapse:collapse;font-size:16px;min-width:560px}
.sev th,.sev td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}
.sev th{font-family:var(--type);font-weight:400;letter-spacing:.1em;text-transform:uppercase;color:var(--manila-2);font-size:14px}
.sev td:first-child{white-space:nowrap}
.table-box{overflow-x:auto;border:1px solid var(--line);border-radius:4px;background:var(--asphalt)}
.dossier-grid{columns:3 320px;column-gap:22px}
.dossier-grid .card{break-inside:avoid;margin:34px 0 0;display:block}
.dossier-grid .card h3{display:flex;justify-content:space-between;gap:10px;align-items:baseline}
.dossier-grid .card h3 small{font-family:var(--type);font-size:14px;color:var(--manila-muted)}
.src{font-family:var(--type);font-size:12px;color:var(--manila-muted);margin-top:10px}
.cards>*,.page-hero .wrap>*,.rules>*,.dossier-grid>*{min-width:0}
.card p,.list li,.lede{overflow-wrap:anywhere}
.sev .stamp{mix-blend-mode:normal}
html,body{overflow-x:clip}
</style>"""


def nav(active):
    items = [("/#evidence", "What he checks", "home"), ("/#platforms", "Platforms", "home"),
             ("/security/", "Security", "security"), ("/dossier/", "Full dossier", "dossier"),
             ("/#casework", "Case files", "home"), ("/#install", "Install", "home")]
    links = "\n      ".join(
        f'<a href="{h}"{" aria-current=\"page\"" if a == active and h.startswith("/" + a) else ""}>{t}</a>'
        for h, t, a in items)
    return f"""<header class="nav">
  <div class="wrap">
    <a class="brand" href="/"><img src="/assets/badge-mark.png" alt="" width="38" height="42">FAT Agent</a>
    <nav aria-label="Sections">
      {links}
    </nav>
    <a class="btn-gh" href="https://github.com/spruikco/fat-agent-skill">GitHub</a>
  </div>
</header>"""


FOOTER = """<footer>
  <div class="wrap">
    <span>FAT Agent is a <a href="https://www.spruik.co">Spruik</a> production. Free and open source under the MIT licence.</span>
    <a href="https://github.com/spruikco/fat-agent-skill">github.com/spruikco/fat-agent-skill</a>
  </div>
</footer>"""

INSTALL = """<section id="install" class="install" aria-labelledby="install-title">
    <div class="wrap">
      <div class="sec-head">
        <p class="eyebrow">Install</p>
        <h2 id="install-title">Put him on the case.</h2>
        <p>Inside Claude Code, run these two lines. Then point him at a site.</p>
      </div>
      <img class="sticker" src="/assets/scenes/pose-thumbs.png" alt="" width="400" height="600" loading="lazy">
      <ol class="steps">
        <li><div class="cmd"><code id="cmd-1">/plugin marketplace add spruikco/fat-agent-skill</code><button type="button" data-copy="cmd-1">Copy</button></div></li>
        <li><div class="cmd"><code id="cmd-2">/plugin install fat-agent@fat-agent-marketplace</code><button type="button" data-copy="cmd-2">Copy</button></div></li>
        <li><p class="say">Run <code>/fat-audit https://your-site.com</code>, or just say "run FAT agent on my site".</p></li>
      </ol>
    </div>
  </section>"""


def doc(title, desc, active, main):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:image" content="/assets/og-card.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/assets/badge-mark.png">
{FONTS}{STYLE}
{EXTRA_CSS}
</head>
<body>
{nav(active)}
<main id="top">
{main}
</main>
{FOOTER}
{SCRIPT}
</body>
</html>
"""


# ------------------------------------------------------------------ home
def build_home():
    body = BODY.replace("{{CHART}}", chart)
    body = body[body.index("<main"):]
    main = body[body.index(">") + 1: body.index("</main>")]
    main = main.replace('src="assets/', 'src="/assets/').replace('poster="assets/', 'poster="/assets/')
    main = main.replace('href="assets/', 'href="/assets/')
    extra = """
  <section aria-labelledby="more-title" style="padding-block:clamp(40px,6vw,72px)">
    <div class="wrap">
      <div class="sec-head">
        <p class="eyebrow">Beyond SEO</p>
        <h2 id="more-title">He checks the locks too.</h2>
        <p>Security headers, leaked keys, exposed files, cookies, TLS, email spoofing and consent. Read the <a href="/security/">security file</a>, or see <a href="/dossier/">every check he makes</a>.</p>
      </div>
    </div>
  </section>
"""
    main = main.replace('  <section id="casework"', extra + '  <section id="casework"', 1)
    return doc("FAT Agent", "The heavyweight website auditor for Claude Code. Fix. Audit. Test.",
               "home", main)


# ------------------------------------------------------------------ security
SECURITY = """
  <section class="page-hero" aria-labelledby="sec-title">
    <div class="wrap">
      <div>
        <p class="eyebrow">Internal affairs</p>
        <h1 id="sec-title">He checks<span class="red">the locks too.</span></h1>
        <p class="lede">FAT Agent is a security tester as much as an SEO auditor. He looks at your site the way an attacker would, from the outside: headers, leaked keys, exposed files, cookies, certificates, DNS, email spoofing and consent. Then he tells you exactly what to change.</p>
        <div class="counters" aria-label="At a glance">
          <span><b>8</b>secret types</span><span><b>24</b>sensitive paths</span><span><b>40+</b>security checks</span>
        </div>
      </div>
      <figure class="scene" style="margin:0"><img src="/assets/scenes/raid.jpg" alt="FAT Agent kicking open a server room door as web pages with error marks fly past" width="1672" height="940"><figcaption>Exhibit 06: the raid</figcaption></figure>
    </div>
  </section>

  <section aria-labelledby="sec-checks">
    <div class="wrap">
      <div class="sec-head">
        <p class="eyebrow">What he checks</p>
        <h2 id="sec-checks">Every door, every window.</h2>
        <p>Presence is not enough. A Content-Security-Policy full of 'unsafe-inline' is a lock with the key in it, so he grades the quality of each defence, not just whether it exists.</p>
      </div>
      <div class="cards">
        <article class="card" data-tab="Headers">
          <h3>Security headers</h3>
          <p>Content-Security-Policy, Strict-Transport-Security, X-Frame-Options, Referrer-Policy, Permissions-Policy and X-Content-Type-Options.</p>
          <ul class="list"><li>CSP weakened by 'unsafe-inline', 'unsafe-eval' or wildcard sources</li><li>HSTS max-age too short, or missing includeSubDomains</li><li>Framing protection through frame-ancestors or X-Frame-Options</li></ul>
          <p class="finding"><span class="stamp p1">P1</span>Missing Content-Security-Policy header</p>
        </article>
        <article class="card" data-tab="Secrets">
          <h3>Keys left in the open</h3>
          <p>He reads your page source and inline scripts for credentials that should never ship to a browser.</p>
          <ul class="list"><li>Stripe live secret keys</li><li>AWS access key IDs</li><li>GitHub and Slack tokens</li><li>Anthropic and OpenAI API keys</li><li>Private key blocks</li><li>Google API keys (flagged to check restrictions)</li></ul>
          <p class="finding"><span class="stamp p0">P0</span>Secret exposed in page source</p>
        </article>
        <article class="card" data-tab="Exposed files">
          <h3>The back door</h3>
          <p>An opt-in probe for files that leak from misconfigured servers. It is same-origin only, makes one request per path, and runs only with your go-ahead.</p>
          <div class="paths"><code>.env</code><code>.env.local</code><code>.env.production</code><code>.git/config</code><code>.git/HEAD</code><code>.svn/entries</code><code>.hg/requires</code><code>wp-config.php.bak</code><code>config.php.bak</code><code>.aws/credentials</code><code>.npmrc</code><code>.dockerenv</code><code>docker-compose.yml</code><code>backup.zip</code><code>backup.sql</code><code>db.sql</code><code>dump.sql</code><code>phpinfo.php</code><code>info.php</code><code>server-status</code><code>.DS_Store</code><code>.vscode/settings.json</code><code>config.json</code><code>security.txt</code></div>
          <p class="finding"><span class="stamp p0">P0</span>Exposed sensitive path: /.env</p>
        </article>
        <article class="card" data-tab="Cookies">
          <h3>Cookie flags</h3>
          <p>Every Set-Cookie header is checked for the three flags that stop theft and cross-site abuse.</p>
          <ul class="list"><li>Secure: never sent over plain HTTP</li><li>HttpOnly: out of reach of injected scripts</li><li>SameSite: blocks cross-site request forgery</li></ul>
          <p class="finding"><span class="stamp p2">P2</span>Cookies set without HttpOnly</p>
        </article>
        <article class="card" data-tab="Supply chain">
          <h3>Other people's code</h3>
          <p>Third-party scripts are the most common way into a modern site. He checks what you load and what you leak about your stack.</p>
          <ul class="list"><li>Cross-origin scripts without Subresource Integrity</li><li>Source maps shipped to production</li><li>Server version disclosed in headers</li><li>Mixed content on HTTPS pages</li><li>target="_blank" links without noopener</li></ul>
          <p class="finding"><span class="stamp p2">P2</span>Cross-origin scripts without Subresource Integrity</p>
        </article>
        <article class="card" data-tab="TLS &amp; DNS">
          <h3>The foundations</h3>
          <p>The certificate and DNS records that everything else trusts.</p>
          <ul class="list"><li>SSL certificate invalid, missing or expiring soon</li><li>DNSSEC not enabled</li><li>No CAA record restricting who may issue certificates</li><li>HTTP/2 and CDN presence</li></ul>
          <p class="finding"><span class="stamp p0">P0</span>SSL certificate invalid or missing</p>
        </article>
        <article class="card" data-tab="Email">
          <h3>Spoofing protection</h3>
          <p>If your domain can be spoofed, your customers can be phished in your name.</p>
          <ul class="list"><li>SPF record</li><li>DKIM record</li><li>DMARC record, and a DMARC policy stuck on none</li></ul>
          <p class="finding"><span class="stamp p1">P1</span>Missing DMARC record</p>
        </article>
        <article class="card" data-tab="Privacy">
          <h3>Consent and privacy</h3>
          <p>Trackers that fire before consent are a legal risk as well as a trust one.</p>
          <ul class="list"><li>Tracking that loads before consent</li><li>No consent banner, privacy policy or cookie policy</li><li>No data controller information</li></ul>
          <p class="finding"><span class="stamp p1">P1</span>Tracking may load before consent</p>
        </article>
        <article class="card" data-tab="Hacked?">
          <h3>Signs of a break-in</h3>
          <p>With Search Console connected he reads Google's own verdicts, and the page checks catch the tricks hacked sites get used for.</p>
          <ul class="list"><li>Search Console security issues and manual actions</li><li>Sneaky, conditional JavaScript redirects</li><li>Back button hijacking</li><li>Hidden text and injected spam</li></ul>
          <p class="finding"><span class="stamp p0">P0</span>Security issue reported by Google</p>
        </article>
      </div>
    </div>
  </section>

  <section class="casefile" aria-labelledby="sec-rules">
    <div class="wrap">
      <div class="sec-head">
        <p class="eyebrow">Rules of engagement</p>
        <h2 id="sec-rules">A tester, not a burglar.</h2>
        <p>Everything runs from the outside, the way a visitor or attacker sees your site, and nothing he does changes it.</p>
      </div>
      <div class="rules">
        <div class="rule"><h3>Passive by default</h3><p>Headers, page source, certificates and DNS come from normal requests. No logins, no form submissions, no load testing.</p></div>
        <div class="rule"><h3>Probes on request</h3><p>The exposed-files check only runs when you confirm it, for sites you own or are authorised to test. It never fuzzes: a fixed list, one request each.</p></div>
        <div class="rule"><h3>Guard rails</h3><p>Requests to private networks, localhost and cloud metadata addresses are blocked, so the crawler can't be turned against your own infrastructure.</p></div>
        <div class="rule"><h3>Honest about limits</h3><p>On Shopify or Wix you can't set security headers. He says so, scores it as a platform limit and tells you what you can do instead.</p></div>
      </div>
    </div>
  </section>

  <section aria-labelledby="sec-sev">
    <div class="wrap">
      <div class="sec-head">
        <p class="eyebrow">Priorities</p>
        <h2 id="sec-sev">What gets fixed first.</h2>
      </div>
      <div class="table-box">
        <table class="sev">
          <thead><tr><th>Priority</th><th>Means</th><th>Security examples</th></tr></thead>
          <tbody>
            <tr><td><span class="stamp p0">P0</span></td><td>Drop everything</td><td>Live secret key in page source, exposed .env or .git, invalid certificate, Google-reported security issue</td></tr>
            <tr><td><span class="stamp p1">P1</span></td><td>This week</td><td>No CSP or HSTS, no DMARC, tracking before consent, sneaky redirects</td></tr>
            <tr><td><span class="stamp p2">P2</span></td><td>This month</td><td>Weak CSP, cookies without HttpOnly or SameSite, scripts without SRI, source maps in production</td></tr>
            <tr><td><span class="stamp p3">P3</span></td><td>Polish</td><td>Server version disclosed, no security.txt, missing CAA record</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
"""


def build_security():
    return doc("FAT Agent Security",
               "FAT Agent's security checks: headers, leaked secrets, exposed files, cookies, TLS, DNS, email spoofing and consent.",
               "security", SECURITY + INSTALL)


# ------------------------------------------------------------------ dossier
GROUPS = [
    ("Google's rulebook", ["google_guidelines.py"], "Spam policies and current Search guidance."),
    ("Site-wide crawl", ["sitewide.py"], "Patterns only a full crawl can see."),
    ("SEO essentials", ["seo.py", "technical_seo.py", "crawlability.py", "sitemap.py"], "Indexing, crawling and the basics."),
    ("Structured data", ["schema_validator.py", "video.py"], "Schema validity and rich-result eligibility."),
    ("Content and trust", ["content_quality.py", "content_depth.py", "eeat.py"], "Quality signals and E-E-A-T."),
    ("AI search", ["ai_search.py", "ai_visibility.py", "ai_crawler_logs.py", "fanout.py"], "Answer engines, citations and query fan-out."),
    ("Security", ["security.py", "exposed_paths.py"], "Headers, secrets and exposed files."),
    ("Infrastructure", ["dns_infra.py", "email_deliverability.py"], "TLS, DNS and email authentication."),
    ("Privacy and consent", ["cookie_gdpr.py"], "Consent and policy coverage."),
    ("Accessibility", ["accessibility.py"], "Can everyone use it."),
    ("Performance", ["performance.py", "js_bundle.py", "pwa.py"], "Speed, scripts and app readiness."),
    ("Links", ["links.py", "link_opportunities.py"], "Link health and money-page linking."),
    ("Local business", ["local_seo.py"], "Main-street visibility."),
    ("E-commerce", ["ecommerce.py"], "Product pages and store trust."),
    ("International", ["i18n.py"], "Languages and hreflang."),
    ("Search Console and data", ["gsc_health.py", "update_impact.py", "jev.py"], "Google's own data, update timing and model-verified triage."),
]


READABLE = [  # prefix of the raw title -> the wording shown on the site
    ("VideoObject missing required", "VideoObject missing required properties"),
    ("… empty paragraph", "Empty paragraphs found"),
    ("Outdated copyright year", "Outdated copyright year"),
    ("Trust page(s) not linked", "Trust pages (About, Contact, Privacy) not linked"),
    ("AI answer engines blocked", "AI answer engines blocked in robots.txt"),
    ("AI training bots blocked", "AI training bots blocked (deliberate opt-out?)"),
    ("Low AI citation rate", "Low AI citation rate across tested queries"),
    ("Some answer engines not yet", "Some answer engines not yet crawling"),
    ("… mostly hitting errors", "AI crawler mostly hitting errors (4xx/5xx)"),
    ("Low query fan-out coverage", "Low query fan-out coverage"),
    ("Secret exposed in page source", "Secret exposed in page source (Stripe, AWS, GitHub, Slack, Anthropic, OpenAI, private keys)"),
    ("CSP present but weakened", "CSP present but weakened (unsafe-inline, unsafe-eval, wildcards)"),
    ("HSTS max-age too short", "HSTS max-age too short"),
    ("Cookies set without", "Cookies set without Secure, HttpOnly or SameSite"),
    ("… cross-origin script", "Cross-origin scripts without Subresource Integrity"),
    ("Exposed sensitive path", "Exposed sensitive path (.env, .git, dumps and more)"),
    ("Money-page link gap", "Money-page link gap"),
    ("Manual action", "Manual action in Search Console"),
    ("Security issue", "Security issue reported by Google"),
    ("… rich-result error", "Rich-result errors in Search Console"),
    ("Affiliate/paid links missing rel", 'Affiliate or paid links missing rel="sponsored"'),
    ("External links missing rel", 'External links missing rel="noopener"'),
    ("HTML exceeds Googlebot", "HTML exceeds Googlebot's 2MB indexing limit"),
    ("RTL language detected without dir", 'RTL language detected without dir="rtl"'),
    ("robots.txt blocks render resources", "robots.txt blocks render resources (CSS, JS)"),
    ("Traffic drop across the", "Traffic drop across a Google core or spam update"),
    ("Server version disclosed", "Server version disclosed"),
    ("Fan-out sub-queries not answered", "Fan-out sub-queries not answered (model-verified)"),
    ("Location pages judged as template", "Location pages judged as template copy (model-verified)"),
]


def readable(t):
    for pre, nice in READABLE:
        if t.startswith(pre):
            return nice
    t = t.replace("%%", "%")
    t = re.sub(r"\s*[:(]?\s*…\s*\)?\s*$", "", t)
    t = re.sub(r"^…\s*", "", t)
    return t.replace(" …", "").strip(" :(")


def finding_titles(fname):
    path = os.path.join(SCRIPTS, "modules", fname)
    if not os.path.exists(path):
        path = os.path.join(SCRIPTS, fname)
    if not os.path.exists(path):
        return []
    s = open(path, encoding="utf-8").read()
    raw = re.findall(r'title\s*=\s*f?["\']([^"\']{6,140})["\']', s)
    raw += re.findall(r'"title"\s*:\s*f?"([^"]{6,140})"', s)
    raw += [m[2] for m in re.findall(r'\(\s*"([a-z_0-9]+)",\s*"(P\d)",\s*"([^"]{6,140})"', s)]
    out = []
    for t in raw:
        t = re.sub(r"\{[^}]*\}?|%[sd]", "…", t)
        t = t.replace("\\", "").replace("—", ":").strip(" :")
        t = re.sub(r"(…\s*)+", "… ", t).strip()
        t = re.sub(r"\(\s*…\s*\)", "", t).strip()
        if t.endswith("…") and len(t) < 12:
            continue
        t = readable(t)
        if t and t not in out:
            out.append(t)
    return out


def build_dossier():
    total = 0
    cards = []
    for name, files, blurb in GROUPS:
        items = []
        for f in files:
            items += [x for x in finding_titles(f) if x not in items]
        if not items:
            continue
        total += len(items)
        lis = "".join(f"<li>{html.escape(x)}</li>" for x in items)
        cards.append(f"""        <article class="card" data-tab="{html.escape(name)}">
          <h3>{html.escape(name)} <small>{len(items)}</small></h3>
          <p>{html.escape(blurb)}</p>
          <ul class="list">{lis}</ul>
        </article>""")
    main = f"""
  <section class="page-hero" aria-labelledby="dos-title">
    <div class="wrap">
      <div>
        <p class="eyebrow">The full dossier</p>
        <h1 id="dos-title">Everything<span class="red">he checks.</span></h1>
        <p class="lede">Every finding FAT Agent can raise, pulled straight from the plugin's source code. If it's on this page, he checks it. If it isn't, he doesn't, and we won't pretend otherwise.</p>
        <div class="counters" aria-label="At a glance">
          <span><b>{total}</b>distinct findings</span><span><b>{len(cards)}</b>departments</span><span><b>P0 to P3</b>ranked</span>
        </div>
      </div>
      <img class="sticker" src="/assets/scenes/pose-magnifier.png" alt="FAT Agent peering through a magnifying glass" width="400" height="600">
    </div>
  </section>
  <section aria-label="All findings" style="padding-top:8px">
    <div class="wrap">
      <div class="dossier-grid">
{chr(10).join(cards)}
      </div>
      <p class="src" style="color:var(--chrome-dim);margin-top:28px">Generated from the finding titles in the plugin source on every build. Some titles include the specific value found, shown here as "…".</p>
    </div>
  </section>
"""
    return doc("FAT Agent Dossier", f"All {total} checks FAT Agent makes, grouped by department.",
               "dossier", main + INSTALL), total


def main():
    os.makedirs(os.path.join(DIST, "assets"), exist_ok=True)
    for sub in ("security", "dossier"):
        os.makedirs(os.path.join(DIST, sub), exist_ok=True)
    open(os.path.join(DIST, "index.html"), "w", encoding="utf-8").write(build_home())
    open(os.path.join(DIST, "security", "index.html"), "w", encoding="utf-8").write(build_security())
    dossier, total = build_dossier()
    open(os.path.join(DIST, "dossier", "index.html"), "w", encoding="utf-8").write(dossier)
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(DIST, "assets"),
                    dirs_exist_ok=True)
    # leave out any illustration that hasn't been added yet, rather than ship a broken image
    def have(rel):
        return os.path.exists(os.path.join(HERE, rel.lstrip("/")))

    for page in ("index.html", "security/index.html", "dossier/index.html"):
        path = os.path.join(DIST, page)
        txt = open(path, encoding="utf-8").read()
        txt = re.sub(r'<figure class="scene[^"]*"[^>]*>\s*<img src="(/?assets/scenes/[^"]+)".*?</figure>',
                     lambda m: m.group(0) if have(m.group(1)) else "", txt, flags=re.S)
        txt = re.sub(r'<img class="sticker" src="(/?assets/scenes/[^"]+)"[^>]*>',
                     lambda m: m.group(0) if have(m.group(1)) else "", txt)
        open(path, "w", encoding="utf-8").write(txt)
    for page in ("index.html", "security/index.html", "dossier/index.html"):
        txt = open(os.path.join(DIST, page), encoding="utf-8").read()
        assert "—" not in txt and "–" not in txt, f"dash in {page}"
    print("built; dossier findings:", total)


if __name__ == "__main__":
    main()
