#!/usr/bin/env python3
"""breadth-first multi-page crawler with robots.txt support."""

import argparse
import json
import os
import re
from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

USER_AGENT = "FatAgentCrawler/1.0"
TIMEOUT = 10


def normalize_url(url):
    """normalise a url by lowercasing scheme/host, stripping fragments and trailing slashes."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path
    # strip trailing slash except for root
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # strip fragment, keep query
    return urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))


def is_same_domain(url, base_url):
    """check if url belongs to the same domain as base_url."""
    return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()


class _LinkExtractor(HTMLParser):
    """html parser that extracts href attributes from anchor tags."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def extract_links(html, base_url):
    """extract and normalise all http/https links from html content."""
    parser = _LinkExtractor()
    parser.feed(html)
    seen = set()
    result = []
    for href in parser.links:
        # skip non-http schemes
        if href.startswith(("mailto:", "tel:", "javascript:", "data:", "ftp:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        normalised = normalize_url(absolute)
        if normalised and normalised not in seen:
            seen.add(normalised)
            result.append(normalised)
    return result


def is_allowed_by_robots(path, robots_txt):
    """basic robots.txt check: returns false if path matches a disallow rule for *."""
    if not robots_txt:
        return True
    in_wildcard = False
    disallowed = []
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            in_wildcard = agent == "*"
        elif in_wildcard and line.lower().startswith("disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule:
                disallowed.append(rule)
    for rule in disallowed:
        if path.startswith(rule):
            return False
    return True


def build_crawl_plan(start_url, link_map, max_depth=2, max_pages=10):
    """generate a bfs crawl plan from a pre-computed link map (for testing)."""
    start = normalize_url(start_url)
    visited = set()
    result = []
    queue = deque([(start, 0)])
    visited.add(start)

    while queue and len(result) < max_pages:
        url, depth = queue.popleft()
        if not is_same_domain(url, start):
            continue
        result.append(url)
        if depth >= max_depth:
            continue
        for link in link_map.get(url, []):
            normalised = normalize_url(link)
            if normalised not in visited and is_same_domain(normalised, start):
                visited.add(normalised)
                queue.append((normalised, depth + 1))

    return result


def _fetch_url(url):
    """fetch a url and return (status_code, content_string)."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urlopen(req, timeout=TIMEOUT)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, ""
    except (URLError, OSError):
        return 0, ""


def _fetch_robots(base_url):
    """fetch robots.txt for the given base url."""
    robots_url = urlparse(base_url)
    robots_url = urlunparse(
        (robots_url.scheme, robots_url.netloc, "/robots.txt", "", "", "")
    )
    status, content = _fetch_url(robots_url)
    if status == 200:
        return content
    return ""


def _head_request(url):
    """send a head request and return the status code."""
    req = Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        resp = urlopen(req, timeout=TIMEOUT)
        return resp.status
    except HTTPError as e:
        return e.code
    except (URLError, OSError):
        return 0


def crawl(start_url, max_depth=2, max_pages=10, output_dir=None, check_links=False):
    """crawl starting from start_url using breadth-first search."""
    start = normalize_url(start_url)
    robots_txt = _fetch_robots(start)

    visited = set()
    crawled = []
    all_links = {}
    queue = deque([(start, 0)])
    visited.add(start)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    while queue and len(crawled) < max_pages:
        url, depth = queue.popleft()
        path = urlparse(url).path or "/"
        if not is_allowed_by_robots(path, robots_txt):
            continue

        status, html = _fetch_url(url)
        if status == 0:
            continue

        page_entry = {"url": url, "status": status, "depth": depth}

        if output_dir and html:
            safe_name = re.sub(r"[^\w\-.]", "_", urlparse(url).path or "index")
            if safe_name.startswith("_"):
                safe_name = safe_name[1:]
            if not safe_name:
                safe_name = "index"
            filename = f"{safe_name}.html"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            page_entry["file"] = filename

        links = extract_links(html, url)
        all_links[url] = links
        page_entry["links_found"] = len(links)
        crawled.append(page_entry)

        if depth < max_depth:
            for link in links:
                if link not in visited and is_same_domain(link, start):
                    visited.add(link)
                    queue.append((link, depth + 1))

    manifest = {"start_url": start, "pages_crawled": len(crawled), "pages": crawled}

    if check_links:
        # collect all unique links found across all pages
        unique_links = set()
        for page_links in all_links.values():
            unique_links.update(page_links)
        link_statuses = []
        for link in sorted(unique_links):
            code = _head_request(link)
            link_statuses.append({"url": link, "status": code})
        manifest["link_check"] = {
            "total": len(link_statuses),
            "results": link_statuses,
        }

    return manifest


def main():
    parser = argparse.ArgumentParser(description="breadth-first multi-page crawler")
    parser.add_argument("--url", required=True, help="start url to crawl")
    parser.add_argument(
        "--depth", type=int, default=2, help="max crawl depth (default: 2)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=10, help="max pages to crawl (default: 10)"
    )
    parser.add_argument(
        "--output-dir", default=None, help="directory to save html files"
    )
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="check all found links with head requests",
    )
    args = parser.parse_args()

    manifest = crawl(
        start_url=args.url,
        max_depth=args.depth,
        max_pages=args.max_pages,
        output_dir=args.output_dir,
        check_links=args.check_links,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
