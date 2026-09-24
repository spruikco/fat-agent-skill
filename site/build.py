#!/usr/bin/env python3
"""Build the FAT Agent site into site/dist (Netlify) from index.template.html.

Pages: /            (index.template.html + chart)
       /security/   (security deep dive)
       /dossier/    (every finding FAT can raise, pulled from the plugin source)

The dossier is generated from the finding titles in plugins/fat-agent/scripts, so
the site can never claim a check the code doesn't make.
"""
import datetime
import glob
import html
import json
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
.locks{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px}
@media (max-width:880px){.locks{grid-template-columns:repeat(2,1fr)}}
@media (max-width:560px){.locks{grid-template-columns:1fr}}
.lock-stamp{display:inline-grid;place-items:center;width:92px;height:92px;border:3.5px solid var(--stamp);border-radius:50%;color:var(--stamp);transform:rotate(-10deg);box-shadow:inset 0 0 0 5px var(--night),inset 0 0 0 7.5px var(--stamp);margin-bottom:14px}
.lock-stamp svg{width:44px;height:44px}
.lock{background:var(--manila);color:var(--manila-ink);border-radius:3px;padding:16px 18px;display:grid;gap:6px;align-content:start;box-shadow:0 8px 18px rgba(0,0,0,.3)}
.lock b{font-family:var(--display);font-weight:400;font-size:18px;line-height:1.1}
.lock span:last-child{font-size:14px;line-height:1.4;color:#3a3020}
.lock .stamp{justify-self:start}
.cta-row{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}
.cta{font-family:var(--type);font-size:16px;text-decoration:none;background:var(--stamp);color:#fff;padding:10px 18px;border-radius:3px}
.cta:hover{background:var(--stamp-soft)}
.cta.ghost{background:transparent;border:1px solid var(--chrome-dim);color:var(--chrome)}
.casefile .split{align-items:center}
.cards>*,.page-hero .wrap>*,.rules>*,.dossier-grid>*{min-width:0}
.card p,.list li,.lede{overflow-wrap:anywhere}
.sev .stamp{mix-blend-mode:normal}
html,body{overflow-x:clip}
</style>"""


def nav(active):
    items = [("/#evidence", "What he checks", "home"), ("/#platforms", "Platforms", "home"),
             ("/security/", "Security", "security"), ("/dossier/", "Full dossier", "dossier"),
             ("/#casework", "Case files", "home"), ("/pricing/", "Pricing", "pricing"), ("/#install", "Install", "home")]
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
    <span>FAT Agent is a <a href="https://www.spruik.co">Spruik</a> production. Free and open source under the MIT licence. <a href="/privacy/">Privacy</a></span>
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
      <img class="sticker" src="/assets/badge-testing.png" alt="" width="465" height="520" loading="lazy">
      <ol class="steps">
        <li><div class="cmd"><code id="cmd-1">/plugin marketplace add spruikco/fat-agent-skill</code><button type="button" data-copy="cmd-1">Copy</button></div></li>
        <li><div class="cmd"><code id="cmd-2">/plugin install fat-agent@fat-agent-marketplace</code><button type="button" data-copy="cmd-2">Copy</button></div></li>
        <li><p class="say">Run <code>/fat-audit https://your-site.com</code>, or just say "run FAT agent on my site".</p></li>
      </ol>
    </div>
  </section>"""


# Google Analytics 4. Set FAT_GA_ID=G-XXXXXXXXXX when building; empty = no tracking.
GA_ID = os.environ.get("FAT_GA_ID", "").strip()
if not GA_ID and os.path.exists(os.path.join(HERE, "ga_id.txt")):
    GA_ID = open(os.path.join(HERE, "ga_id.txt"), encoding="utf-8").read().strip()
# Consent Mode v2: denied by default where consent law requires opt-in (EEA, UK,
# Switzerland), granted elsewhere; the banner lets anyone change it. This site
# audits consent, so it has to pass its own check.
CONSENT_REGIONS = ("AT BE BG HR CY CZ DK EE FI FR DE GR HU IS IE IT LV LI LT LU MT NL "
                   "NO PL PT RO SK SI ES SE GB CH").split()


def analytics_head():
    if not GA_ID:
        return ""
    regions = ",".join(f"'{r}'" for r in CONSENT_REGIONS)
    return f"""<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied',region:[{regions}],wait_for_update:500}});
gtag('consent','default',{{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'granted'}});
try{{var c=localStorage.getItem('fat-consent');if(c){{gtag('consent','update',{{analytics_storage:c}});}}}}catch(e){{}}
gtag('js',new Date());gtag('config','{GA_ID}',{{anonymize_ip:true}});
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>"""


CONSENT_BANNER = """<div id="consent" class="consent" hidden role="region" aria-label="Cookie choice">
  <p>We use Google Analytics to count visits. No ads, no selling data. <a href="/privacy/">Privacy</a></p>
  <div class="consent-btns"><button type="button" data-consent="denied">Decline</button><button type="button" data-consent="granted">Accept</button></div>
</div>
<script>
(function(){var b=document.getElementById('consent');if(!b)return;var c=null;try{c=localStorage.getItem('fat-consent');}catch(e){}
if(!c)b.hidden=false;b.addEventListener('click',function(e){var v=e.target.getAttribute('data-consent');if(!v)return;
try{localStorage.setItem('fat-consent',v);}catch(e){}if(window.gtag)gtag('consent','update',{analytics_storage:v});b.hidden=true;});})();
</script>"""

CONSENT_CSS = """<style>
.consent{position:fixed;left:16px;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:50;max-width:560px;margin-inline:auto;background:var(--manila);color:var(--manila-ink);border-radius:4px;padding:14px 16px;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;box-shadow:0 18px 40px rgba(0,0,0,.55);font-size:15px}
.consent p{flex:1 1 260px}
.consent a{color:var(--manila-ink)}
.consent-btns{display:flex;gap:8px}
.consent button{font-family:var(--type);font-size:15px;border:2px solid var(--manila-ink);background:transparent;color:var(--manila-ink);padding:6px 14px;border-radius:3px;cursor:pointer}
.consent button[data-consent="granted"]{background:var(--stamp);border-color:var(--stamp);color:#fff}
</style>"""


SITE = os.environ.get("FAT_SITE_URL", "https://fatagent.netlify.app").rstrip("/")

ORG = {"@type": "Organization", "@id": "https://www.spruik.co/#org", "name": "Spruik",
       "url": "https://www.spruik.co", "logo": SITE + "/assets/badge-mark.png",
       "sameAs": ["https://github.com/spruikco"]}
APP = {"@type": "SoftwareApplication", "@id": SITE + "/#app", "name": "FAT Agent",
       "description": "Free, open-source website auditor for Claude Code: SEO, Google spam policies, security, accessibility and performance, with fixes and re-tests.",
       "applicationCategory": "DeveloperApplication", "operatingSystem": "Windows, macOS, Linux (Claude Code)",
       "url": SITE + "/", "downloadUrl": "https://github.com/spruikco/fat-agent-skill",
       "license": "https://opensource.org/licenses/MIT", "publisher": {"@id": "https://www.spruik.co/#org"},
       "offers": {"@type": "Offer", "price": "0", "priceCurrency": "AUD"}}
VIDEO = {"@type": "VideoObject", "name": "FAT Agent trailer",
         "description": "A 60-second noir trailer: FAT Agent investigates why an online shop's organic sales fell and finds the duplicates.",
         "thumbnailUrl": SITE + "/assets/scenes/stakeout.jpg", "contentUrl": SITE + "/assets/fat-agent-promo.mp4",
         "uploadDate": "2026-09-24", "duration": "PT1M1S", "publisher": {"@id": "https://www.spruik.co/#org"}}
HQ_OFFERS = {"@type": "SoftwareApplication", "name": "FAT HQ", "applicationCategory": "BusinessApplication",
             "operatingSystem": "Web", "url": "https://fathq.prodimus.com.au/",
             "publisher": {"@id": "https://www.spruik.co/#org"},
             "offers": [{"@type": "Offer", "name": n, "price": str(pr), "priceCurrency": "AUD"} for n, pr in (("Free", 0), ("Pro", 29), ("Agency", 99))]}


def jsonld(active):
    graph = [ORG, {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": "FAT Agent",
                   "publisher": {"@id": "https://www.spruik.co/#org"}}]
    if active == "home":
        graph += [APP, VIDEO]
    if active == "pricing":
        graph += [APP, HQ_OFFERS]
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": graph}) + "</script>"


def doc(title, desc, active, main):
    path = "/" if active == "home" else f"/{active}/"
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
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{SITE}/assets/og-card.png">
<link rel="canonical" href="{SITE}{path}">
<meta name="theme-color" content="#101319">
<link rel="apple-touch-icon" href="/assets/badge-mark.png">
{jsonld(active)}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/assets/badge-mark.png">
{analytics_head()}
{FONTS}{STYLE}
{EXTRA_CSS}<style>{HQ_CSS}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{nav(active)}
<main id="main">
{main}
</main>
{FOOTER}
{SCRIPT}
{CONSENT_BANNER if GA_ID else ""}
{CONSENT_CSS if GA_ID else ""}
</body>
</html>
"""


# ------------------------------------------------------------------ home
HQ_URL = os.environ.get("FAT_HQ_URL", "https://fathq.prodimus.com.au")

HQ_SECTION = """
  <section class="hq-band" aria-labelledby="hq-title">
    <div class="wrap">
      <div class="split">
        <div class="sec-head">
          <p class="eyebrow">FAT HQ</p>
          <h2 id="hq-title">Keep him on retainer.</h2>
          <p>The plugin is free and always will be. FAT HQ is where he keeps the case files after you close the laptop: every audit on one board, the score over time, your Search Console clicks against Google's updates, re-checks on a schedule and an email when something breaks.</p>
          <div class="cta-row"><a class="cta" href="{hq}/signup">Start free</a><a class="cta ghost" href="/pricing/">See pricing</a></div>
        </div>
        <div class="hq-shot" aria-hidden="true">
          <div class="hq-card"><span class="hq-grade">B</span><div><b>yourshop.com.au</b><small>Last audit this morning</small></div><span class="hq-score">79</span></div>
          <svg viewBox="0 0 300 90" class="hq-line"><polyline points="0,70 40,62 80,66 120,48 160,52 200,34 240,30 300,18" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/></svg>
          <ul class="hq-list"><li><span class="stamp p0">P0</span>Checkout 404s from the cart page <em>new</em></li><li><span class="stamp p1">P1</span>Missing Content-Security-Policy <em>fixed</em></li><li><span class="stamp p1">P1</span>Doorway pages <em>came back</em></li></ul>
        </div>
      </div>
      <div class="hq-feats">
        <div><b>Case files</b><span>Every audit from the plugin or HQ, with what got fixed, what's new and what came back.</span></div>
        <div><b>Search Console</b><span>Weekly clicks and impressions with Google's core and spam updates marked, so "why did we drop?" has a date.</span></div>
        <div><b>Stakeouts</b><span>Weekly or daily re-checks of the pages you pick. No laptop required.</span></div>
        <div><b>Tip-offs</b><span>An email the moment a P0 appears, a fix comes undone or the score drops five points.</span></div>
        <div><b>Client reports</b><span>A clean report link for each site. On Agency, with your name, logo and colour.</span></div>
      </div>
    </div>
  </section>
""".replace("{hq}", HQ_URL)

HQ_CSS = """
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.skip{position:absolute;left:-9999px;top:8px;z-index:50;background:var(--manila);color:var(--manila-ink);padding:8px 14px;font-family:var(--type)}.skip:focus{left:8px}
.hq-band{background:radial-gradient(ellipse 60% 70% at 80% 10%,rgba(200,16,46,.12),transparent 70%),var(--asphalt)}
.hq-shot{background:var(--manila);color:var(--manila-ink);border-radius:4px;padding:22px;box-shadow:0 24px 50px rgba(0,0,0,.45);transform:rotate(1deg);display:grid;gap:14px}
.hq-card{display:flex;align-items:center;gap:14px}.hq-card b{display:block;font-family:var(--display);font-size:18px}.hq-card small{font-size:13px;color:var(--manila-muted)}
.hq-grade{font-family:var(--display);font-size:30px;color:#2f7d4d;border:3px solid currentColor;border-radius:50%;width:54px;height:54px;display:grid;place-items:center;transform:rotate(-8deg);flex:none}
.hq-score{font-family:var(--display);font-size:38px;margin-left:auto}
.hq-line{width:100%;height:auto;color:var(--stamp)}
.hq-list{list-style:none;margin:0;padding:0;display:grid;gap:8px;font-size:15px}.hq-list li{display:flex;gap:10px;align-items:center;border-top:1px dashed var(--manila-2);padding-top:8px}
.hq-list em{margin-left:auto;font-family:var(--type);font-style:normal;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--manila-muted);white-space:nowrap}
.hq-feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:8px}
.hq-feats div{border:1px solid var(--line);border-radius:4px;padding:16px;display:grid;gap:6px;align-content:start;background:var(--night)}
.hq-feats b{font-family:var(--display);font-size:17px;color:var(--chrome)}.hq-feats span{font-size:15px;color:var(--chrome-dim)}
.plans{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;align-items:stretch}
.plan{background:var(--manila);color:var(--manila-ink);border-radius:4px;padding:26px;display:flex;flex-direction:column;gap:12px;box-shadow:0 18px 36px rgba(0,0,0,.4)}
.plan.feat{outline:3px solid var(--stamp);outline-offset:5px}
.plan h3{font-family:var(--display);font-size:28px}.plan .price{font-family:var(--display);font-size:44px;line-height:1}.plan .price small{font-family:var(--type);font-size:15px}
.plan .fine{font-size:14px;color:var(--manila-muted)}.plan ul{margin:0;padding-left:18px;flex:1;display:grid;gap:6px;align-content:start}
.plan .cta{align-self:flex-start}.plan .cta.ghost{color:var(--manila-ink);border-color:var(--manila-ink)}
.plan-tag{font-family:var(--type);font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--stamp)}
.faq{display:grid;gap:12px;max-width:820px}.faq details{border:1px solid var(--line);border-radius:4px;padding:14px 18px;background:var(--asphalt)}
.faq summary{cursor:pointer;font-family:var(--display);font-size:17px}.faq p{margin-top:10px;color:var(--chrome-dim)}
"""

PRICING = """
  <section class="page-hero" aria-labelledby="price-title">
    <div class="wrap" style="grid-template-columns:1fr">
      <div>
        <p class="eyebrow">Pricing</p>
        <h1 id="price-title">The plugin is free.<span class="red">HQ keeps watch.</span></h1>
        <p class="lede">FAT Agent runs in Claude Code at no cost, MIT licensed, every check included. FAT HQ is the optional hosted side: case files, trends, Search Console, scheduled re-checks, alerts and client reports.</p>
      </div>
    </div>
  </section>
  <section aria-labelledby="plans-title" style="padding-top:12px">
    <div class="wrap">
      <h2 id="plans-title" class="sr-only">Plans</h2>
      <div class="plans">
        <div class="plan"><p class="plan-tag">The plugin</p><h3>FAT Agent</h3><p class="price">Free</p><p class="fine">Forever. MIT licence.</p>
          <ul><li>All 222 checks, P0 to P3 punch list</li><li>Site-wide crawl, spam policy and doorway checks</li><li>Search Console, AI search and update impact</li><li>Fixes the code with you, then re-tests</li></ul>
          <a class="cta ghost" href="/#install">Install</a></div>
        <div class="plan"><p class="plan-tag">HQ</p><h3>Free</h3><p class="price">A$0</p><p class="fine">No card needed.</p>
          <ul><li>1 site</li><li>Last 5 audits kept</li><li>Score trend, punch list, what changed</li><li>Search Console chart</li></ul>
          <a class="cta" href="{hq}/signup">Start free</a></div>
        <div class="plan feat"><p class="plan-tag">HQ</p><h3>Pro</h3><p class="price">A$29<small> /month</small></p><p class="fine">US$19 outside Australia. GST included.</p>
          <ul><li>10 sites, full history</li><li>Weekly re-checks of up to 5 pages each</li><li>Email alerts: new P0s, regressions, score drops</li><li>Shareable client report links</li></ul>
          <a class="cta" href="{hq}/signup?plan=pro">Start with Pro</a></div>
        <div class="plan"><p class="plan-tag">HQ</p><h3>Agency</h3><p class="price">A$99<small> /month</small></p><p class="fine">US$69 outside Australia. GST included.</p>
          <ul><li>50 sites</li><li>Daily re-checks of up to 20 pages each</li><li>White-label reports: your name, logo and colour</li><li>Everything in Pro</li></ul>
          <a class="cta" href="{hq}/signup?plan=agency">Start with Agency</a></div>
      </div>
    </div>
  </section>
  <section aria-labelledby="faq-title">
    <div class="wrap">
      <div class="sec-head"><p class="eyebrow">Questions</p><h2 id="faq-title">Before you hire him.</h2></div>
      <div class="faq">
        <details><summary>Do I need HQ to use FAT Agent?</summary><p>No. The plugin does the whole audit, the fixes and the re-test inside Claude Code. HQ only stores results and keeps watching between sessions.</p></details>
        <details><summary>How do audits get into HQ?</summary><p>Make a plugin key in HQ, then tell FAT Agent to send the audit (or run <code>python scripts/fat_hq.py upload</code>). HQ can also check sites itself with "Check now" and on a schedule.</p></details>
        <details><summary>Does HQ get my Google login?</summary><p>No. FAT Agent pulls your Search Console export on your machine and sends only daily clicks and impressions. HQ never sees your Google account.</p></details>
        <details><summary>What do scheduled checks cover?</summary><p>The pages you choose, run through the same FAT Agent checks the plugin uses on a single page. Full site crawls stay in the plugin, where they can take as long as they need.</p></details>
        <details><summary>Can I cancel?</summary><p>Any time, from the billing page. You drop back to Free and keep your latest five audits per site.</p></details>
      </div>
    </div>
  </section>
""".replace("{hq}", HQ_URL)


def build_home():
    body = BODY.replace("{{CHART}}", chart)
    body = body[body.index("<main"):]
    main = body[body.index(">") + 1: body.index("</main>")]
    main = main.replace('src="assets/', 'src="/assets/').replace('poster="assets/', 'poster="/assets/')
    main = main.replace('href="assets/', 'href="/assets/')
    extra = """
  <section class="casefile" aria-labelledby="more-title">
    <div class="wrap">
      <div class="split">
        <div class="sec-head">
          <span class="lock-stamp weathered" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M8 10.5V7.2a4 4 0 0 1 8 0v3.3" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path fill="currentColor" fill-rule="evenodd" d="M6.5 10.5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2zM12 13.6a1.6 1.6 0 0 0-.8 3v1.9h1.6v-1.9a1.6 1.6 0 0 0-.8-3z"/></svg></span>
          <p class="eyebrow">Beyond SEO</p>
          <h2 id="more-title">He checks the locks too.</h2>
          <p>FAT Agent is a security tester as much as an SEO auditor. He looks at your site the way an attacker would, from the outside, grades every defence on quality rather than presence, and ranks what he finds from P0 to P3.</p>
          <div class="cta-row"><a class="cta" href="/security/">Open the security file</a><a class="cta ghost" href="/dossier/">All 222 checks</a></div>
        </div>
        <figure class="scene">
          <img src="/assets/scenes/raid.jpg" alt="FAT Agent kicking open a server room door as web pages with error marks fly past" width="1290" height="726" loading="lazy">
          <figcaption>Exhibit 06: the raid</figcaption>
        </figure>
      </div>
      <div class="locks">
        <div class="lock"><span class="stamp p0">P0</span><b>Leaked keys</b><span>Stripe, AWS, GitHub, Slack, Anthropic and OpenAI keys in your page source</span></div>
        <div class="lock"><span class="stamp p0">P0</span><b>Exposed files</b><span>.env, .git, database dumps and 20 more, probed only with your go-ahead</span></div>
        <div class="lock"><span class="stamp p1">P1</span><b>Security headers</b><span>CSP and HSTS graded, not just ticked</span></div>
        <div class="lock"><span class="stamp p1">P1</span><b>Email spoofing</b><span>SPF, DKIM and DMARC, so nobody phishes in your name</span></div>
        <div class="lock"><span class="stamp p1">P1</span><b>Consent</b><span>Trackers that fire before anyone says yes</span></div>
        <div class="lock"><span class="stamp p2">P2</span><b>Cookies and scripts</b><span>Secure, HttpOnly, SameSite, and third-party code without integrity checks</span></div>
      </div>
    </div>
  </section>
"""
    main = main.replace('  <section id="casework"', extra + '  <section id="casework"', 1)
    main = main.replace('  <section id="install"', HQ_SECTION + '  <section id="install"', 1)
    return doc("FAT Agent: free SEO and security auditor for Claude Code",
               "FAT Agent audits your website inside Claude Code: Google spam policies, SEO, security, accessibility and speed, then fixes what it finds. Free and open source.",
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
    return doc("FAT Agent security checks: headers, keys and exposed files",
               "FAT Agent tests your site like an attacker would: security headers graded on quality, leaked API keys, exposed .env and .git files, cookies and email spoofing.",
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
      <img class="sticker" src="/assets/badge-topsecret.png" alt="FAT Agent holding a folder stamped top secret" width="394" height="440">
    </div>
  </section>
  <section aria-label="All findings" style="padding-top:8px">
    <div class="wrap">
      <h2 class="sr-only">Checks by department</h2>
      <div class="dossier-grid">
{chr(10).join(cards)}
      </div>
      <p class="src" style="color:var(--chrome-dim);margin-top:28px">Generated from the finding titles in the plugin source on every build. Some titles include the specific value found, shown here as "…".</p>
    </div>
  </section>
"""
    return doc(f"FAT Agent dossier: all {total} website audit checks",
               f"Every one of the {total} checks FAT Agent runs on a website, grouped by department, from Google spam policies and SEO to security, accessibility and speed.",
               "dossier", main + INSTALL), total


PRIVACY = """
  <section class="page-hero" aria-labelledby="priv-title">
    <div class="wrap" style="grid-template-columns:1fr">
      <div>
        <p class="eyebrow">Privacy</p>
        <h1 id="priv-title">What we collect.<span class="red">Not much.</span></h1>
        <p class="lede">This site is run by Spruik Co Pty Ltd, Melbourne, Australia. We use Google Analytics 4 to count visits and see which pages people read. That's it: no advertising, no remarketing, and we never sell or share data.</p>
      </div>
    </div>
  </section>
  <section aria-label="Details" style="padding-top:8px">
    <div class="wrap" style="max-width:760px">
      <div class="sec-head">
        <h2>The details</h2>
        <p><b>What Google Analytics records:</b> pages viewed, rough location (country or city), device and browser type, and how you arrived. Google Analytics 4 does not store IP addresses.</p>
        <p><b>Your choice:</b> in the EU, UK and Switzerland analytics stays off until you accept. Everywhere else it is on until you decline. Change your mind any time by clearing this site's storage in your browser; the banner comes back.</p>
        <p><b>The plugin itself:</b> FAT Agent runs inside your own Claude Code session. It sends nothing to us unless you connect FAT HQ.</p>
        <p><b>FAT HQ:</b> if you make an HQ account, the audits and Search Console numbers you send are covered by the <a href="https://fathq.prodimus.com.au/privacy">FAT HQ privacy policy</a>.</p>
        <p><b>Stored in your browser:</b> one entry, your analytics choice (<code>fat-consent</code> in local storage). This site sets no cookies of its own; Google Analytics sets its cookies only when analytics is on.</p>
        <p><b>Hosting and fonts:</b> the site is served by Netlify, which keeps standard request logs (IP address, page, time) for security and uptime. Fonts load from Google Fonts, so Google sees your IP address when the page loads them.</p>
        <p><b>What we never do:</b> sell data, run advertising or remarketing, or use fingerprinting. There are no forms on this site; nothing you type here is sent anywhere.</p>
        <p><b>Your rights:</b> under the Australian Privacy Principles you can ask what we hold about you and have it corrected or deleted. If you are unhappy with our answer you can contact the Office of the Australian Information Commissioner.</p>
        <p><b>Contact:</b> hello@spruik.co</p>
      </div>
    </div>
  </section>
"""


PAGES = ("index.html", "security/index.html", "dossier/index.html", "privacy/index.html", "pricing/index.html")

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://www.google-analytics.com https://www.googletagmanager.com",
    "media-src 'self'",
    "connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com",
    "frame-ancestors 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
    "upgrade-insecure-requests",
])

NETLIFY_TOML = f"""[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=604800"
[[headers]]
  for = "/*"
  [headers.values]
    Content-Security-Policy = "{CSP}"
    Strict-Transport-Security = "max-age=31536000; includeSubDomains"
    X-Content-Type-Options = "nosniff"
    X-Frame-Options = "SAMEORIGIN"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Permissions-Policy = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    Cross-Origin-Opener-Policy = "same-origin"
"""


HEADERS_FILE = f"""/*
  Content-Security-Policy: {CSP}
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  X-Content-Type-Options: nosniff
  X-Frame-Options: SAMEORIGIN
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  Cross-Origin-Opener-Policy: same-origin
/assets/*
  Cache-Control: public, max-age=604800
"""


def main():
    os.makedirs(os.path.join(DIST, "assets"), exist_ok=True)
    for sub in ("security", "dossier", "privacy", "pricing"):
        os.makedirs(os.path.join(DIST, sub), exist_ok=True)
    open(os.path.join(DIST, "index.html"), "w", encoding="utf-8").write(build_home())
    open(os.path.join(DIST, "security", "index.html"), "w", encoding="utf-8").write(build_security())
    dossier, total = build_dossier()
    open(os.path.join(DIST, "dossier", "index.html"), "w", encoding="utf-8").write(dossier)
    open(os.path.join(DIST, "pricing", "index.html"), "w", encoding="utf-8").write(
        doc("FAT Agent pricing: free plugin, FAT HQ from A$0 a month", "The FAT Agent plugin is free and open source. FAT HQ adds case files, Search Console trends, scheduled re-checks, alerts and client reports, free for one site.", "pricing", PRICING))
    open(os.path.join(DIST, "privacy", "index.html"), "w", encoding="utf-8").write(
        doc("FAT Agent privacy: what this website and FAT HQ collect", "What the FAT Agent website records with analytics, what the open-source plugin sends (nothing, unless you connect FAT HQ), and how to ask us to delete data.", "privacy", PRIVACY))
    shutil.copytree(os.path.join(HERE, "assets"), os.path.join(DIST, "assets"),
                    dirs_exist_ok=True)
    # leave out any illustration that hasn't been added yet, rather than ship a broken image
    def have(rel):
        return os.path.exists(os.path.join(HERE, rel.lstrip("/")))

    for page in ("index.html", "security/index.html", "dossier/index.html", "privacy/index.html", "pricing/index.html"):
        path = os.path.join(DIST, page)
        txt = open(path, encoding="utf-8").read()
        txt = re.sub(r'<figure class="scene[^"]*"[^>]*>\s*<img src="(/?assets/scenes/[^"]+)".*?</figure>',
                     lambda m: m.group(0) if have(m.group(1)) else "", txt, flags=re.S)
        txt = re.sub(r'<img class="sticker" src="(/?assets/scenes/[^"]+)"[^>]*>',
                     lambda m: m.group(0) if have(m.group(1)) else "", txt)
        open(path, "w", encoding="utf-8").write(txt)
    # WebP copies of the scene illustrations (the JPEGs stay for the video poster and old browsers)
    try:
        from PIL import Image
        for png in ("badge-topsecret", "badge-testing", "agent-portrait", "badge-mark"):
            src = os.path.join(DIST, "assets", png + ".png")
            if os.path.exists(src):
                Image.open(src).save(src[:-4] + ".webp", quality=85, method=6)
        for jpg in glob.glob(os.path.join(DIST, "assets", "scenes", "*.jpg")):
            webp = jpg[:-4] + ".webp"
            if not os.path.exists(webp) or os.path.getmtime(webp) < os.path.getmtime(jpg):
                Image.open(jpg).save(webp, quality=78, method=6)
    except ImportError:
        pass
    for page in PAGES:
        path = os.path.join(DIST, page)
        txt = open(path, encoding="utf-8").read()
        # one number everywhere: the dossier's real count of checks
        txt = re.sub(r"(?<![\d,.])222(?= (?:things he checks|checks|things))", str(total), txt)
        txt = txt.replace("<b>222</b>", f"<b>{total}</b>")
        # below-the-fold images load lazily; the nav badge is the only eager one
        txt = re.sub(r'<img (?![^>]*loading=)(?![^>]*class="brand-img")([^>]*?)(/?)>',
                     lambda m: m.group(0) if 'badge-mark.png" alt="" width="38"' in m.group(0)
                     else f'<img loading="lazy" decoding="async" {m.group(1)}{m.group(2)}>', txt)
        for png in ("badge-topsecret", "badge-testing", "agent-portrait", "badge-mark"):
            if os.path.exists(os.path.join(DIST, "assets", png + ".webp")):
                txt = re.sub(r'(<img[^>]*src="/?assets/' + png + r')\.png', r"\1.webp", txt)
        if os.path.exists(os.path.join(DIST, "assets", "scenes", "stakeout.webp")):
            txt = re.sub(r'(<img[^>]*src="/?assets/scenes/[a-z-]+)\.jpg', r"\1.webp", txt)
            txt = re.sub(r'url\((/?assets/scenes/[a-z-]+)\.jpg\)', r"url(\1.webp)", txt)
        open(path, "w", encoding="utf-8").write(txt)
    today = datetime.date.today().isoformat()
    urls = ["/", "/security/", "/dossier/", "/pricing/", "/privacy/"]
    open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(DIST, "netlify.toml"), "w", encoding="utf-8").write(NETLIFY_TOML)
    open(os.path.join(DIST, "_headers"), "w", encoding="utf-8").write(HEADERS_FILE)
    for page in PAGES:
        txt = open(os.path.join(DIST, page), encoding="utf-8").read()
        assert "—" not in txt and "–" not in txt, f"dash in {page}"
    print("built; dossier findings:", total)


if __name__ == "__main__":
    main()
