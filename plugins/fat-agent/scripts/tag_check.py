#!/usr/bin/env python3
"""Rendered tag check — what tracking actually FIRES, not what the HTML says.

analyse-html.py reads the raw HTML, so anything injected by Google Tag
Manager (very often the Meta Pixel, Google Ads, LinkedIn) or by a client-side
app is invisible to it, and "tag present" never proved "tag working". This
script loads each page in headless Chrome/Edge over the DevTools Protocol,
records every request the page makes, and reports:

  loaded vs firing     each tag that loaded, and whether it sent any hits
  render-only tags     tags you'd never see in the raw HTML (GTM-injected)
  double counting      the same GA4 ID or Meta Pixel sending page_view twice
  dead tags            Universal Analytics still firing (retired July 2024)
  consent              GA4 Consent Mode state on the hits (gcs)
  conversions          on thank-you pages (--pages), did a conversion fire?

By default the tracking hits are BLOCKED at the browser after being recorded,
so an audit never adds fake visits or conversions to the client's GA4, Ads or
Meta data. Pass --allow-hits to let them through (e.g. to watch GA4 DebugView).

Stdlib only: drives an installed Chrome, Edge or Chromium (set FAT_CHROME to
point at one). No browser found → exits 2 with a clear message; fall back to
the manual browser check in SKILL.md 1.8b.

Usage:
    python scripts/tag_check.py --url https://x.com
        [--pages /thank-you /contact/thanks ...] [--wait 6] [--allow-hits]
        [--public-only] [--json]

--public-only is for running on a server against URLs other people supply
(FAT HQ does): every browser request goes through a built-in proxy that
resolves the host itself, refuses private, loopback and link-local addresses
and ports other than 80/443, and connects only to the address it checked.
FAT_CHROME_FLAGS adds browser flags (e.g. --no-sandbox in a container).
"""

import argparse
import base64
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

MODULE = "tag_check"

# Beacon endpoints only (never the tag libraries themselves, or the tags
# would not run). Recorded by requestWillBeSent, then failed by the browser.
HIT_BLOCK_PATTERNS = [
    "*/g/collect*",
    "*google-analytics.com/collect*",
    "*google-analytics.com/r/collect*",
    "*google-analytics.com/j/collect*",
    "*analytics.google.com/g/collect*",
    "*facebook.com/tr*",
    "*googleadservices.com/pagead/conversion*",
    "*google.com/pagead/1p-conversion*",
    "*google.com/pagead/1p-user-list*",
    "*googleads.g.doubleclick.net/pagead/viewthroughconversion*",
    "*px.ads.linkedin.com/*",
    "*analytics.tiktok.com/api/*",
    "*bat.bing.com/action/*",
    "*ct.pinterest.com/*",
    "*tr.snapchat.com/*",
    "*.clarity.ms/collect*",
]

# Events that fire on every page by themselves; anything else counts as a
# conversion-like signal on a thank-you page.
GA4_AMBIENT = {
    "page_view",
    "user_engagement",
    "scroll",
    "session_start",
    "first_visit",
    "form_start",
    "click",
    "view_search_results",
    "video_start",
    "video_progress",
    "video_complete",
    "file_download",
}
META_AMBIENT = {
    "PageView",
    "ViewContent",
    "Microdata",
    "SubscribedButtonClick",
    "AddToCart",
    "AddToWishlist",
    "Search",
    "InitiateCheckout",
    "AddPaymentInfo",
}
TIKTOK_AMBIENT = {"Pageview", "PageView", "LandingPageView", "ViewContent", "ClickButton"}

# Containers and session tools: loading is the job, hits are not expected
LOAD_ONLY_VENDORS = {"Google Tag Manager", "Google tag", "Floodlight", "Hotjar", "Microsoft Clarity"}

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
CHROME_NAMES = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "msedge",
    "microsoft-edge",
]

# What the page itself knows: GTM/gtag registry, gtag calls, pixel ids.
PAGE_STATE_JS = r"""
(() => {
  const out = {gtm: [], gtag: [], dataLayerEvents: [], fbPixels: [], forms: 0};
  try {
    out.gtm = Object.keys(window.google_tag_manager || {})
      .filter(k => /^(GTM|G|AW|GT|DC|UA)-/.test(k));
  } catch (e) {}
  try {
    for (const e of (window.dataLayer || []).slice(0, 200)) {
      if (e && typeof e === 'object' && typeof e.length === 'number') {
        const a = Array.prototype.slice.call(e, 0, 3);
        const call = [String(a[0]), typeof a[1] === 'object' ? '' : String(a[1] || '')];
        if (a[0] === 'consent' && a[2] && typeof a[2] === 'object') {
          call.push(JSON.stringify(a[2]).slice(0, 300));
        }
        out.gtag.push(call);
      } else if (e && typeof e === 'object' && e.event) {
        out.dataLayerEvents.push(String(e.event).slice(0, 80));
      }
    }
  } catch (e) {}
  try {
    if (window.fbq && fbq.getState) out.fbPixels = fbq.getState().pixels.map(p => String(p.id));
  } catch (e) {}
  try { out.forms = document.forms.length; } catch (e) {}
  return JSON.stringify(out);
})()
"""


FLUSH_JS = (
    "Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>'hidden'});"
    "Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});"
    "document.dispatchEvent(new Event('visibilitychange'));"
    "window.dispatchEvent(new Event('pagehide'));"
)


class CDPError(Exception):
    pass


# ---------------------------------------------------------------- browser


def find_browser():
    env = os.environ.get("FAT_CHROME")
    if env and os.path.exists(env):
        return env
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def private_address(ip):
    """True for loopback, private, link-local, CGNAT, multicast and reserved addresses."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return True
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return (
        a.is_private
        or a.is_loopback
        or a.is_link_local
        or a.is_multicast
        or a.is_reserved
        or a.is_unspecified
        or a in ipaddress.ip_network("100.64.0.0/10")
    )


class PublicOnlyProxy:
    """Forward proxy that only connects to public addresses on ports 80/443.

    For server-side runs (--public-only): every request Chrome makes, including
    WebSockets and redirects, goes through here. The proxy resolves the host
    itself and connects to the address it vetted, so a page cannot steer the
    browser at the machine's own network, and DNS rebinding cannot swap the
    address between the check and the connection.
    """

    PORTS = (80, 443)

    def __init__(self):
        self.blocked = []
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(64)
        self.port = self.srv.getsockname()[1]
        self.alive = True
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self):
        self.alive = False
        try:
            self.srv.close()
        except OSError:
            pass

    def _accept(self):
        while self.alive:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def vet(self, host, port):
        """A public address to connect to, or None (recorded as blocked)."""
        if port not in self.PORTS:
            self.blocked.append(f"{host}:{port}")
            return None
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError:
            return None
        addrs = [i[4][0] for i in infos]
        if not addrs or any(private_address(a) for a in addrs):
            self.blocked.append(f"{host}:{port}")
            return None
        return addrs[0]

    def _handle(self, conn):
        upstream = None
        try:
            conn.settimeout(30)
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = conn.recv(65536)
                if not chunk or len(head) > 65536:
                    return
                head += chunk
            line, rest = head.split(b"\r\n", 1)
            method, target, version = line.decode("latin-1").split(" ", 2)
            if method == "CONNECT":
                host, _, port = target.rpartition(":")
                host, port = host.strip("[]"), int(port or 443)
                payload = head.split(b"\r\n\r\n", 1)[1]
            else:
                u = urllib.parse.urlsplit(target)
                if u.scheme != "http" or not u.hostname:
                    conn.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                    return
                host, port = u.hostname, u.port or 80
                path = urllib.parse.urlunsplit(("", "", u.path or "/", u.query, ""))
                # one request per connection: a reused keep-alive connection
                # would carry the next request past the check
                hdrs, _, body = rest.partition(b"\r\n\r\n")
                kept = [
                    h for h in hdrs.split(b"\r\n")
                    if h and not h.lower().startswith((b"connection:", b"proxy-connection:", b"keep-alive:"))
                ]
                payload = (
                    f"{method} {path} {version}\r\n".encode("latin-1")
                    + b"\r\n".join(kept + [b"Connection: close"])
                    + b"\r\n\r\n"
                    + body
                )
            ip = self.vet(host, port)
            if not ip:
                conn.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
                return
            upstream = socket.create_connection((ip, port), timeout=30)
            if method == "CONNECT":
                conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            if payload:
                upstream.sendall(payload)
            self._pipe(conn, upstream)
        except (OSError, ValueError):
            pass
        finally:
            for s in (conn, upstream):
                if s:
                    try:
                        s.close()
                    except OSError:
                        pass

    @staticmethod
    def _pipe(a, b):
        def copy(src, dst):
            try:
                while True:
                    data = src.recv(65536)
                    if not data:
                        break
                    dst.sendall(data)
            except OSError:
                pass
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        t = threading.Thread(target=copy, args=(b, a), daemon=True)
        t.start()
        copy(a, b)
        t.join(35)


def launch_browser(browser, user_dir, timeout=20, extra_args=()):
    """Start headless Chrome on a free port; return (proc, page websocket url)."""
    args = [
        browser,
        "--headless=new",
        "--remote-debugging-port=0",
        f"--user-data-dir={user_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--disable-extensions",
        "--window-size=1366,900",
        *extra_args,
        # FAT_CHROME_FLAGS: e.g. "--no-sandbox --disable-dev-shm-usage" in a container
        *os.environ.get("FAT_CHROME_FLAGS", "").split(),
        "about:blank",
    ]
    if hasattr(os, "geteuid") and os.geteuid() == 0 and "--no-sandbox" not in args:
        args.insert(1, "--no-sandbox")
    proc = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    port_file = os.path.join(user_dir, "DevToolsActivePort")
    deadline = time.time() + timeout
    port = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise CDPError(f"browser exited early (code {proc.returncode})")
        try:
            with open(port_file, "r", encoding="utf-8") as f:
                first = f.readline().strip()
            if first.isdigit():
                port = int(first)
                break
        except OSError:
            pass
        time.sleep(0.1)
    if not port:
        proc.kill()
        raise CDPError("browser did not open a DevTools port")
    # never send the DevTools request through an HTTP_PROXY from the environment
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.time() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
                targets = json.loads(r.read().decode("utf-8"))
            for t in targets:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return proc, t["webSocketDebuggerUrl"]
        except OSError:
            pass
        time.sleep(0.2)
    proc.kill()
    raise CDPError("no page target found")


class CDP:
    """Minimal DevTools Protocol client over a hand-rolled WebSocket."""

    def __init__(self, ws_url, timeout=10):
        u = urllib.parse.urlparse(ws_url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise CDPError("websocket handshake failed")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101" not in head.split(b"\r\n", 1)[0]:
            raise CDPError("websocket upgrade refused")
        self.next_id = 0
        self.events = []

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _send_frame(self, payload, opcode=0x1):
        mask = os.urandom(4)
        n = len(payload)
        header = bytearray([0x80 | opcode])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + mask + masked)

    def _frame(self):
        """Pop one complete frame from the buffer, or None if incomplete."""
        b = self.buf
        if len(b) < 2:
            return None
        n = b[1] & 0x7F
        pos = 2
        if n == 126:
            if len(b) < 4:
                return None
            n = struct.unpack(">H", b[2:4])[0]
            pos = 4
        elif n == 127:
            if len(b) < 10:
                return None
            n = struct.unpack(">Q", b[2:10])[0]
            pos = 10
        masked = b[1] & 0x80
        if masked:
            pos += 4
        if len(b) < pos + n:
            return None
        data = b[pos : pos + n]
        if masked:
            m = b[pos - 4 : pos]
            data = bytes(x ^ m[i % 4] for i, x in enumerate(data))
        self.buf = b[pos + n :]
        return b[0] & 0x80, b[0] & 0x0F, data

    def _recv(self, deadline):
        """Next JSON message, or None when the deadline passes."""
        parts = []
        while True:
            fr = self._frame()
            if fr is None:
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                self.sock.settimeout(remaining)
                try:
                    chunk = self.sock.recv(65536)
                except socket.timeout:
                    return None
                if not chunk:
                    raise CDPError("browser closed the connection")
                self.buf += chunk
                continue
            fin, op, data = fr
            if op == 0x8:
                raise CDPError("browser closed the connection")
            if op == 0x9:
                self._send_frame(data, opcode=0xA)
                continue
            if op == 0xA:
                continue
            parts.append(data)
            if fin:
                return json.loads(b"".join(parts).decode("utf-8", "replace"))

    def call(self, method, params=None, timeout=15):
        self.next_id += 1
        mid = self.next_id
        self._send_frame(
            json.dumps({"id": mid, "method": method, "params": params or {}}).encode()
        )
        deadline = time.time() + timeout
        while True:
            msg = self._recv(deadline)
            if msg is None:
                raise CDPError(f"{method} timed out")
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def pump(self, seconds):
        deadline = time.time() + seconds
        while True:
            msg = self._recv(deadline)
            if msg is None:
                return
            if "method" in msg:
                self.events.append(msg)

    def wait_for(self, method, seconds):
        deadline = time.time() + seconds
        if any(e.get("method") == method for e in self.events):
            return True
        while True:
            msg = self._recv(deadline)
            if msg is None:
                return False
            if "method" in msg:
                self.events.append(msg)
                if msg["method"] == method:
                    return True


# ---------------------------------------------------------- classification


def _qs(s):
    return {k: v[0] for k, v in urllib.parse.parse_qs(s, keep_blank_values=True).items()}


def _multipart_field(body, name):
    m = re.search(
        r'name="%s"\r?\n\r?\n([^\r\n]*)' % re.escape(name), body or ""
    )
    return m.group(1) if m else ""


def classify(url, method="GET", body=""):
    """Turn one request into zero or more tag records.

    Each record: {"vendor", "id", "kind": "load"|"hit", "event", "consent"}.
    Pure function, no network: the unit tests drive it directly.
    """
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return []
    host = (u.hostname or "").lower()
    path = u.path or ""
    q = _qs(u.query)
    body = body or ""
    out = []

    def rec(vendor, tag_id, kind, event="", consent="", key=None):
        out.append(
            {
                "vendor": vendor,
                "id": tag_id or "",
                "kind": kind,
                "event": event or "",
                "consent": consent or "",
                # identical requests are one hit: a blocked beacon is retried
                "key": key or f"{method} {url} {body}|{len(out)}",
            }
        )

    # --- Google: loads ---
    if host.endswith("googletagmanager.com") or path.endswith(("/gtm.js", "/gtag/js")):
        tid = q.get("id", "")
        if path.endswith("/gtm.js") and tid:
            rec("Google Tag Manager", tid, "load")
            return out
        if path.endswith("/gtag/js") and tid:
            vendor = {
                "G-": "GA4",
                "AW": "Google Ads",
                "GT": "Google tag",
                "UA": "Universal Analytics",
                "DC": "Floodlight",
            }.get(tid[:2], "Google tag")
            rec(vendor, tid, "load")
            return out

    # --- GA4 hits (also server-side GTM on a custom domain) ---
    if path.endswith("/g/collect") and q.get("tid", "").startswith("G-"):
        tid = q["tid"]
        consent = q.get("gcs", "")
        lines = [ln for ln in re.split(r"\r?\n", body) if ln.strip()]
        events = []
        for ln in lines:
            ev = _qs(ln).get("en", "")
            if ev:
                events.append((ev, ln))
        if not events and q.get("en"):
            events = [(q["en"], "")]
        # GA4 retries a failed batch with the same page id (_p) and hit
        # sequence (_s); without this, blocking hits would fake double counts
        if q.get("_p"):
            base = f"GA4|{tid}|{q['_p']}|{q.get('_s', '')}|{q.get('en', '')}"
        else:
            base = f"{method} {url} {body}"
        for i, (ev, ln) in enumerate(events or [("", "")]):
            rec("GA4", tid, "hit", ev, consent, key=f"{base}|{i}|{ln}")
        return out

    # --- Universal Analytics hits ---
    if path.endswith(("/collect", "/r/collect", "/j/collect")) and (
        "google-analytics.com" in host
    ):
        params = dict(q)
        if body and "tid=" in body:
            params.update(_qs(body.splitlines()[0]))
        if params.get("tid", "").startswith("UA-"):
            rec("Universal Analytics", params["tid"], "hit", params.get("t", ""))
        return out

    # --- Google Ads conversions and remarketing ---
    m = re.search(r"/pagead/(?:1p-)?(conversion|viewthroughconversion|user-list)/(\d+)", path)
    if m and (
        "googleadservices.com" in host
        or "doubleclick.net" in host
        or host.endswith("google.com")
    ):
        label = q.get("label", "")
        kind = m.group(1)
        if label and kind != "user-list":
            rec("Google Ads", "AW-" + m.group(2), "hit", "conversion:" + label)
        else:
            rec("Google Ads", "AW-" + m.group(2), "hit", "remarketing")
        return out

    # --- Meta Pixel ---
    if host.endswith("connect.facebook.net"):
        m = re.search(r"/signals/config/(\d+)", path)
        if m:
            rec("Meta Pixel", m.group(1), "load")
        elif path.endswith("/fbevents.js"):
            rec("Meta Pixel", "", "load")
        return out
    if host.endswith("facebook.com") and path.rstrip("/") == "/tr":
        pid = q.get("id", "") or _qs(body).get("id", "") or _multipart_field(body, "id")
        ev = q.get("ev", "") or _qs(body).get("ev", "") or _multipart_field(body, "ev")
        rec("Meta Pixel", pid, "hit", ev)
        return out

    # --- LinkedIn Insight ---
    if host.endswith("snap.licdn.com") and "insight" in path:
        rec("LinkedIn Insight", "", "load")
        return out
    if host == "px.ads.linkedin.com":
        pid = q.get("pid", "")
        conv = q.get("conversionId", "")
        if not pid and body.startswith("{"):
            try:
                j = json.loads(body)
                pid = str(j.get("pids", [""])[0] if j.get("pids") else j.get("pid", ""))
                conv = str(j.get("conversionId", "") or "")
            except (ValueError, AttributeError):
                pass
        rec("LinkedIn Insight", pid, "hit", "conversion:" + conv if conv else "pageview")
        return out

    # --- TikTok ---
    if host.endswith("analytics.tiktok.com"):
        if "/pixel/events.js" in path:
            rec("TikTok Pixel", q.get("sdkid", ""), "load")
        elif path.startswith("/api/"):
            code, events = "", []
            try:
                j = json.loads(body) if body.startswith(("{", "[")) else {}
                batch = j.get("batch") if isinstance(j, dict) else None
                for item in batch or [j]:
                    if isinstance(item, dict):
                        events.append(str(item.get("event", "")))
                        code = code or str(
                            ((item.get("context") or {}).get("pixel") or {}).get("code", "")
                        )
            except (ValueError, AttributeError):
                pass
            for ev in events or [""]:
                rec("TikTok Pixel", code, "hit", ev)
        return out

    # --- Microsoft Ads UET ---
    if host == "bat.bing.com":
        if path.endswith("/bat.js"):
            rec("Microsoft Ads UET", "", "load")
        elif path.startswith("/action/"):
            ev = q.get("evt", "")
            if ev == "custom" and q.get("ea"):
                ev = "custom:" + q["ea"]
            rec("Microsoft Ads UET", q.get("ti", ""), "hit", ev)
        return out

    # --- Pinterest ---
    if host == "s.pinimg.com" and "/ct/" in path:
        rec("Pinterest Tag", "", "load")
        return out
    if host == "ct.pinterest.com":
        rec("Pinterest Tag", q.get("tid", ""), "hit", q.get("event", ""))
        return out

    # --- Snapchat ---
    if host == "sc-static.net" and "scevent" in path:
        rec("Snapchat Pixel", "", "load")
        return out
    if host == "tr.snapchat.com":
        rec("Snapchat Pixel", q.get("pid", ""), "hit", q.get("ev", ""))
        return out

    # --- Microsoft Clarity / Hotjar (session tools; loads are what matter) ---
    if host.endswith("clarity.ms"):
        m = re.match(r"/tag/([a-z0-9]+)", path)
        if m:
            rec("Microsoft Clarity", m.group(1), "load")
        elif path.endswith("/collect"):
            rec("Microsoft Clarity", "", "hit", "collect")
        return out
    m = re.search(r"/c/hotjar-(\d+)\.js", path)
    if host.endswith("hotjar.com") and m:
        rec("Hotjar", m.group(1), "load")
        return out

    return out


def is_conversion(rec):
    """Would this hit count as a conversion signal on a thank-you page?"""
    if rec["kind"] != "hit" or not rec["event"]:
        return False
    v, ev = rec["vendor"], rec["event"]
    if v == "GA4":
        return ev not in GA4_AMBIENT
    if v == "Meta Pixel":
        return ev not in META_AMBIENT
    if v == "TikTok Pixel":
        return ev not in TIKTOK_AMBIENT
    if v in ("Google Ads", "LinkedIn Insight"):
        return ev.startswith("conversion:")
    if v == "Microsoft Ads UET":
        return ev.startswith("custom:")
    if v == "Pinterest Tag":
        return ev.lower() in ("checkout", "lead", "signup")
    return False


# ------------------------------------------------------------------ capture


def capture_page(cdp, url, wait=6.0, scroll=True):
    """Load one URL; return its tag records, page state and raw HTML."""
    cdp.events = []
    cdp.call("Page.navigate", {"url": url})
    cdp.wait_for("Page.loadEventFired", 30)
    cdp.pump(wait)
    if scroll:
        try:
            cdp.call(
                "Runtime.evaluate",
                {"expression": "window.scrollTo(0, document.body.scrollHeight)"},
            )
            cdp.pump(2)
        except CDPError:
            pass

    state = {}
    try:
        res = cdp.call(
            "Runtime.evaluate", {"expression": PAGE_STATE_JS, "returnByValue": True}
        )
        state = json.loads(res.get("result", {}).get("value") or "{}")
    except (CDPError, ValueError):
        state = {}
    # GA4 batches events and flushes when the tab is hidden; a real visitor
    # leaving does this, so do it too before reading the requests
    try:
        cdp.call("Runtime.evaluate", {"expression": FLUSH_JS})
        cdp.pump(1.5)
    except CDPError:
        pass

    records, doc_id, requests = [], None, 0
    for e in list(cdp.events):
        if e.get("method") != "Network.requestWillBeSent":
            continue
        p = e.get("params", {})
        req = p.get("request", {})
        requests += 1
        if p.get("type") == "Document" and doc_id is None:
            doc_id = p.get("requestId")
        body = req.get("postData") or ""
        if not body and req.get("postDataEntries"):
            chunks = []
            for ent in req["postDataEntries"]:
                try:
                    chunks.append(base64.b64decode(ent.get("bytes", "")).decode("utf-8", "replace"))
                except ValueError:
                    pass
            body = "".join(chunks)
        if not body and req.get("hasPostData"):
            try:
                body = cdp.call(
                    "Network.getRequestPostData", {"requestId": p.get("requestId")}, 5
                ).get("postData", "")
            except CDPError:
                body = ""
        records.extend(classify(req.get("url", ""), req.get("method", "GET"), body))

    raw_html = ""
    if doc_id:
        try:
            res = cdp.call("Network.getResponseBody", {"requestId": doc_id}, 10)
            raw_html = res.get("body", "")
            if res.get("base64Encoded"):
                raw_html = base64.b64decode(raw_html).decode("utf-8", "replace")
        except (CDPError, ValueError):
            raw_html = ""
    return {"url": url, "records": records, "state": state, "raw_html": raw_html, "requests": requests}


def _undo_msys_path(p):
    """Git Bash rewrites '/thank-you' to 'C:/Program Files/Git/thank-you'."""
    m = re.match(r"^[A-Za-z]:[\\/].*?[\\/]Git[\\/](.*)$", p)
    return "/" + m.group(1).replace("\\", "/") if m else p


def run(url, pages=(), wait=6.0, allow_hits=False, browser=None, public_only=False):
    browser = browser or find_browser()
    if not browser:
        raise CDPError(
            "No Chrome, Edge or Chromium found. Install one or set FAT_CHROME "
            "to its path, or use the manual browser check (SKILL.md 1.8b)."
        )
    user_dir = tempfile.mkdtemp(prefix="fat-tag-check-")
    proc = None
    cdp = None
    proxy = PublicOnlyProxy() if public_only else None
    extra = []
    if proxy:
        extra = [
            f"--proxy-server=http://127.0.0.1:{proxy.port}",
            # route loopback through the proxy too (Chrome bypasses it by default)
            "--proxy-bypass-list=<-loopback>",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--disable-quic",
        ]
    try:
        proc, ws = launch_browser(browser, user_dir, extra_args=extra)
        cdp = CDP(ws)
        cdp.call("Network.enable", {"maxPostDataSize": 65536})
        cdp.call("Page.enable")
        ua = cdp.call("Runtime.evaluate", {"expression": "navigator.userAgent", "returnByValue": True})
        ua = ua.get("result", {}).get("value", "")
        if "Headless" in ua:
            # Some GTM triggers and bot filters skip HeadlessChrome
            cdp.call("Network.setUserAgentOverride", {"userAgent": ua.replace("HeadlessChrome", "Chrome")})
        if not allow_hits:
            cdp.call("Network.setBlockedURLs", {"urls": HIT_BLOCK_PATTERNS})
        captured = [capture_page(cdp, url, wait)]
        for extra in pages:
            target = urllib.parse.urljoin(url, _undo_msys_path(extra))
            captured.append(capture_page(cdp, target, wait))
            captured[-1]["conversion_page"] = True
        if proxy and captured:
            captured[0]["blocked"] = sorted(set(proxy.blocked))
        return captured
    finally:
        if proxy:
            proxy.close()
        if cdp:
            cdp.close()
        if proc:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(user_dir, ignore_errors=True)


# ----------------------------------------------------------------- analysis


def _registry_vendor(key):
    for prefix, vendor in (
        ("GTM-", "Google Tag Manager"),
        ("G-", "GA4"),
        ("AW-", "Google Ads"),
        ("UA-", "Universal Analytics"),
        ("DC-", "Floodlight"),
    ):
        if key.startswith(prefix):
            return vendor
    return "Google tag"


def _consent_denied(state):
    for call in state.get("gtag", []):
        if call[:2] == ["consent", "default"] and len(call) > 2:
            if '"analytics_storage":"denied"' in call[2].replace(" ", ""):
                return True
    return False


def analyse_page(page):
    """Summarise one captured page (pure: tests feed it records directly)."""
    recs = page.get("records", [])
    state = page.get("state", {}) or {}
    raw = page.get("raw_html", "") or ""

    # source: "load" = the tag's own script was requested; "registry" = only
    # named in window.google_tag_manager / fbq state (a destination GTM knows
    # about, which may legitimately send nothing on this page)
    loaded = {}
    for r in recs:
        if r["kind"] == "load":
            loaded[(r["vendor"], r["id"])] = "load"
    for pid in state.get("fbPixels", []) or []:
        loaded.setdefault(("Meta Pixel", str(pid)), "load")
    for key in state.get("gtm", []) or []:
        loaded.setdefault((_registry_vendor(key), key), "registry")

    seen, hits = set(), []
    for r in recs:
        if r["kind"] != "hit":
            continue
        k = r.get("key") or id(r)
        if k in seen:
            continue
        seen.add(k)
        hits.append(r)

    # an id-less record (fbevents.js, a beacon without its id) belongs to the
    # vendor's only id'd tag when there is exactly one
    def owner(v, i):
        if i:
            return i
        ids = {i2 for (v2, i2) in loaded if v2 == v and i2} | {
            h["id"] for h in hits if h["vendor"] == v and h["id"]
        }
        return ids.pop() if len(ids) == 1 else ""

    merged = {}
    for (v, i), src in loaded.items():
        o = owner(v, i)
        if (v, o) not in merged or src == "load":
            merged[(v, o)] = src
    events, fired = {}, set()
    for h in hits:
        key = (h["vendor"], owner(h["vendor"], h["id"]))
        fired.add(key)
        events.setdefault(key, [])
        if h["event"]:
            events[key].append(h["event"])
    # an id-less load row is redundant once any id'd row of that vendor exists
    for (v, i) in list(merged):
        if not i and any(v2 == v and i2 for (v2, i2) in set(merged) | fired):
            del merged[(v, i)]

    tags = []
    for (v, i) in sorted(set(merged) | fired):
        tags.append(
            {
                "vendor": v,
                "id": i,
                "source": merged.get((v, i), "hit"),
                "fired": (v, i) in fired,
                "events": events.get((v, i), []),
                "in_raw_html": bool(i) and i in raw,
            }
        )

    consents = sorted({r["consent"] for r in hits if r["vendor"] == "GA4" and r["consent"]})
    gtag_configs = {}
    for call in state.get("gtag", []):
        if call[0] == "config" and call[1]:
            gtag_configs[call[1]] = gtag_configs.get(call[1], 0) + 1

    return {
        "url": page.get("url", ""),
        "conversion_page": bool(page.get("conversion_page")),
        "tags": tags,
        "hits": len(hits),
        # unique: Google Ads sends each conversion to two endpoints
        "conversions": list(dict.fromkeys(
            f"{r['vendor']} {r['id']} {r['event']}".strip() for r in hits if is_conversion(r)
        )),
        "ga4_consent": consents,
        "consent_default_denied": _consent_denied(state),
        "gtag_configs": gtag_configs,
        "datalayer_events": (state.get("dataLayerEvents") or [])[:30],
        "forms": state.get("forms", 0),
        "requests": page.get("requests", 0),
    }


def _finding(priority, title, description, fix, effort="low", page=""):
    f = {
        "priority": priority,
        "title": title,
        "description": description,
        "fix": fix,
        "effort": effort,
        "module": MODULE,
    }
    if page:
        f["page"] = page
    return f


def as_findings(summaries):
    findings = []
    for s in summaries:
        url = s["url"]
        tags = s["tags"]
        waiting = s["consent_default_denied"] or any(
            c.startswith("G1") and c != "G111" for c in s["ga4_consent"]
        )
        analytics = [t for t in tags if t["vendor"] not in LOAD_ONLY_VENDORS]

        if not s["conversion_page"] and not any(t["fired"] for t in tags):
            if s["consent_default_denied"]:
                findings.append(
                    _finding(
                        "P2",
                        "No tracking fires before cookie consent",
                        "Consent Mode defaults analytics_storage to denied and no hits "
                        "were sent on load. Correct for strict consent regions, but "
                        "Australian sites usually lose most of their data this way.",
                        "Accept the banner and re-test, or enable Consent Mode "
                        "advanced (cookieless pings) so GA4 can model the gap.",
                        page=url,
                    )
                )
            elif any(t["source"] == "load" for t in analytics):
                pass  # covered by the loaded-but-silent findings below
            else:
                findings.append(
                    _finding(
                        "P1",
                        "No analytics hits fired",
                        "The rendered page sent no requests to any analytics or ad "
                        "platform. Traffic, leads and ad conversions are not being "
                        "measured.",
                        "Install GA4 (directly or via GTM) and confirm page_view in "
                        "GA4 DebugView.",
                        effort="medium",
                        page=url,
                    )
                )

        for t in tags:
            label = f"{t['vendor']} {t['id']}".strip()
            if t["vendor"] == "Universal Analytics":
                findings.append(
                    _finding(
                        "P2",
                        f"Universal Analytics {t['id']} still installed",
                        "Universal Analytics stopped processing data on 1 July 2024. "
                        "This tag "
                        + ("sends hits nobody records" if t["fired"] else "is still configured")
                        + " and only adds page weight.",
                        "Remove the UA tag (theme code, plugin or GTM).",
                        page=url,
                    )
                )
                continue
            if t["vendor"] in LOAD_ONLY_VENDORS:
                continue
            if t["vendor"] == "Google Ads" and not s["conversion_page"]:
                continue  # Ads tags often only send on conversion
            if not t["fired"] and t["source"] == "load":
                meta = t["vendor"] == "Meta Pixel"
                findings.append(
                    _finding(
                        "P2" if waiting or not meta else "P1",
                        f"{label} loads but sends nothing",
                        f"The {t['vendor']} tag loaded on {url} but sent no hits "
                        "during the visit"
                        + (
                            ". Consent Mode is holding it, so this may just be waiting on the banner."
                            if waiting
                            else ", so its data is missing for this page."
                        ),
                        "Check the tag's trigger and ID in GTM Preview / Tag "
                        "Assistant and re-test.",
                        page=url,
                    )
                )

            if t["vendor"] == "GA4" and t["fired"] and "page_view" not in t["events"] and not waiting:
                others = ", ".join(sorted(set(t["events"]) - {""})) or "unnamed hits"
                findings.append(
                    _finding(
                        "P1",
                        f"GA4 {t['id']} records no page views on {url}",
                        f"The property received {others} but no page_view. Pages, "
                        "landing-page and session reports undercount this page, and "
                        "sessions start on a later event instead.",
                        "Check the GA4 config (send_page_view not false) and the "
                        "Google tag / GA4 Event tags in GTM; confirm page_view in "
                        "GA4 DebugView or Realtime.",
                        page=url,
                    )
                )

            if t["vendor"] == "GA4":
                pv = t["events"].count("page_view")
                if pv > 1:
                    findings.append(
                        _finding(
                            "P1",
                            f"GA4 {t['id']} counts every page view {pv} times",
                            f"One load of {url} sent {pv} page_view events to the same "
                            "property. Usually gtag.js hard-coded AND a GA4 tag in GTM, "
                            "or two GTM tags. Sessions, bounce and conversion rates are "
                            "all wrong.",
                            "Keep one install (GTM or gtag, not both) and confirm a "
                            "single page_view in GA4 DebugView.",
                            page=url,
                        )
                    )
            if t["vendor"] == "Meta Pixel":
                pv = t["events"].count("PageView")
                if pv > 1:
                    findings.append(
                        _finding(
                            "P1",
                            f"Meta Pixel {t['id']} fires PageView {pv} times",
                            "The pixel is installed twice (theme or plugin plus GTM, or "
                            "a duplicate fbq('init')). Meta's optimisation and "
                            "audience sizes are skewed.",
                            "Remove one install; check with Meta Pixel Helper.",
                            page=url,
                        )
                    )

        ga4_ids = sorted({t["id"] for t in tags if t["vendor"] == "GA4" and "page_view" in t["events"]})
        if len(ga4_ids) > 1:
            findings.append(
                _finding(
                    "P3",
                    f"{len(ga4_ids)} GA4 properties collecting ({', '.join(ga4_ids)})",
                    "Fine if intentional (e.g. an agency roll-up), otherwise one is a "
                    "stray from an old install or a template.",
                    "Confirm every ID belongs to this business; remove strays.",
                    page=url,
                )
            )

        for gid, n in s["gtag_configs"].items():
            if n > 1 and gid.startswith("G-"):
                findings.append(
                    _finding(
                        "P2",
                        f"gtag config for {gid} runs {n} times",
                        "The same gtag('config') call is on the page more than once, "
                        "which double-sends page views in most setups.",
                        "Remove the duplicate snippet.",
                        page=url,
                    )
                )

        if s["conversion_page"] and not s["conversions"]:
            findings.append(
                _finding(
                    "P1",
                    f"No conversion event fires on {url}",
                    "This thank-you page loaded with page views only. Leads or sales "
                    "that land here are not counted as conversions in GA4, Google Ads "
                    "or Meta, so ad bidding is flying blind.",
                    "Fire a GA4 key event (e.g. generate_lead / purchase) and the "
                    "Google Ads / Meta conversion on this page, then re-run.",
                    effort="medium",
                    page=url,
                )
            )
    return findings


def build_report(captured):
    summaries = [analyse_page(p) for p in captured]
    findings = as_findings(summaries)
    render_only = sorted(
        {
            f"{t['vendor']} {t['id']}"
            for s in summaries
            for t in s["tags"]
            if t["id"] and not t["in_raw_html"] and t["vendor"] != "Google Tag Manager"
        }
    )
    return {
        "findings": findings,
        "pages": summaries,
        "module_scores": {
            MODULE: {
                "pages": len(summaries),
                "tags": len({(t["vendor"], t["id"]) for s in summaries for t in s["tags"]}),
                "hits": sum(s["hits"] for s in summaries),
                "render_only_tags": len(render_only),
                "conversions": sum(len(s["conversions"]) for s in summaries),
            }
        },
        "summary": {
            "render_only_tags": render_only,
            # --public-only: hosts the page tried to reach that were refused
            "blocked_private": sorted({b for p in captured for b in p.get("blocked", [])}),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Rendered analytics/pixel tag check")
    ap.add_argument("--url", required=True, help="page to load (usually the home page)")
    ap.add_argument(
        "--pages",
        nargs="*",
        default=[],
        help="thank-you / confirmation pages (paths or URLs) that should fire a conversion",
    )
    ap.add_argument("--wait", type=float, default=6.0, help="seconds to wait after load")
    ap.add_argument(
        "--allow-hits",
        action="store_true",
        help="let tracking hits reach the vendors (default: record then block)",
    )
    ap.add_argument(
        "--public-only",
        action="store_true",
        help="server-side runs: refuse private/loopback addresses and ports other than 80/443",
    )
    ap.add_argument("--json", action="store_true", help="emit punchlist-ready JSON")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    try:
        captured = run(args.url, args.pages, args.wait, args.allow_hits, public_only=args.public_only)
    except (CDPError, OSError) as e:
        print(f"tag_check: {e}", file=sys.stderr)
        return 2
    report = build_report(captured)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    for s in report["pages"]:
        tag = " (conversion page)" if s["conversion_page"] else ""
        print(f"\n{s['url']}{tag}: {s['hits']} tracking hits")
        for t in s["tags"]:
            if t["fired"]:
                state = "fires"
            elif t["vendor"] in LOAD_ONLY_VENDORS:
                state = "loaded"
            elif t["source"] == "registry":
                state = "config"
            else:
                state = "SILENT"
            where = "" if t["in_raw_html"] or not t["id"] else "  [render-only]"
            evs = ", ".join(sorted(set(t["events"])))
            print(f"  {state:6}  {t['vendor']} {t['id']}{where}" + (f"  ({evs})" if evs else ""))
        if s["ga4_consent"]:
            print(f"  GA4 consent (gcs): {', '.join(s['ga4_consent'])}")
        if s["conversion_page"]:
            print(f"  conversions: {', '.join(s['conversions']) or 'NONE'}")
    if report["summary"]["render_only_tags"]:
        print(
            "\nOnly visible after render (static HTML check misses these): "
            + ", ".join(report["summary"]["render_only_tags"])
        )
    for f in report["findings"]:
        print(f"\n{f['priority']} — {f['title']}")
        print(f"  {f['description']}")
    if not args.allow_hits:
        print("\n(hits recorded then blocked: nothing was sent to the vendors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
