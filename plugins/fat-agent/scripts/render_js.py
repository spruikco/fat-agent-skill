"""Render JavaScript-heavy pages using Playwright and return final HTML."""

import argparse
import sys


def render_page(url, timeout=30000):
    """Render a page with JavaScript and return the final HTML."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, timeout=timeout, wait_until="networkidle")
            html = page.content()
            browser.close()
            return {"html": html, "rendered": True}
    except ImportError:
        return {"html": None, "rendered": False, "error": "playwright not installed"}
    except Exception as e:
        return {"html": None, "rendered": False, "error": str(e)}


def check_available():
    """Check if Playwright is available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except ImportError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Render a page with JavaScript")
    parser.add_argument("--url", required=True, help="URL to render")
    parser.add_argument("--timeout", type=int, default=30000, help="Timeout in ms")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    result = render_page(args.url, timeout=args.timeout)

    if not result["rendered"]:
        print(f"Error: {result.get('error', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result["html"])
        print(f"Rendered HTML written to {args.output}")
    else:
        print(result["html"])


if __name__ == "__main__":
    main()
