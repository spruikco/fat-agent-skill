#!/usr/bin/env python3
"""Screenshot comparison tool for visual regression testing."""

import argparse
import os
import shutil
import subprocess
import sys


def check_playwright_available():
    """check if playwright and its browsers are available."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except ImportError:
        return False


def parse_viewports(viewport_str):
    """parse comma-separated viewport widths into a list of ints."""
    parts = [p.strip() for p in viewport_str.split(",")]
    viewports = []
    for p in parts:
        try:
            viewports.append(int(p))
        except ValueError:
            raise ValueError(f"invalid viewport width: {p!r}")
    return viewports


def ensure_output_dir(path):
    """create output directory if it does not exist."""
    os.makedirs(path, exist_ok=True)
    return path


def calculate_pixel_diff(img1_path, img2_path):
    """calculate percentage of differing pixels between two images.

    returns a float between 0.0 (identical) and 100.0 (completely different).
    if images differ in size, the second is resized to match the first.
    """
    from PIL import Image

    img1 = Image.open(img1_path).convert("RGB")
    img2 = Image.open(img2_path).convert("RGB")

    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.LANCZOS)

    pixels1 = list(img1.getdata())
    pixels2 = list(img2.getdata())
    total = len(pixels1)

    if total == 0:
        return 0.0

    diff_count = sum(1 for p1, p2 in zip(pixels1, pixels2) if p1 != p2)
    return (diff_count / total) * 100.0


def compare_screenshots(current_dir, previous_dir):
    """compare screenshots in current_dir against previous_dir.

    returns a dict mapping filename to diff percentage.
    """
    if not os.path.isdir(previous_dir):
        return {}

    results = {}
    for fname in sorted(os.listdir(current_dir)):
        if not fname.lower().endswith(".png"):
            continue
        current_path = os.path.join(current_dir, fname)
        previous_path = os.path.join(previous_dir, fname)
        if os.path.exists(previous_path):
            results[fname] = calculate_pixel_diff(current_path, previous_path)
        else:
            results[fname] = -1.0  # no baseline
    return results


def take_screenshots(url, output_dir, viewports):
    """take screenshots at each viewport width.

    uses playwright if available, falls back to chromium subprocess,
    or skips with a helpful message.
    """
    ensure_output_dir(output_dir)

    previous_dir = output_dir + ".previous"

    # rotate current -> previous
    if os.path.isdir(output_dir) and os.listdir(output_dir):
        if os.path.isdir(previous_dir):
            shutil.rmtree(previous_dir)
        shutil.copytree(output_dir, previous_dir)
        for f in os.listdir(output_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(output_dir, f))

    if check_playwright_available():
        _take_with_playwright(url, output_dir, viewports)
    elif shutil.which("chromium") or shutil.which("chromium-browser"):
        _take_with_chromium_subprocess(url, output_dir, viewports)
    else:
        print(
            "neither playwright nor chromium found.\n"
            "install playwright: pip install playwright && playwright install chromium\n"
            "or install chromium: apt install chromium-browser"
        )
        return None

    # compare with previous if it exists
    if os.path.isdir(previous_dir):
        results = compare_screenshots(output_dir, previous_dir)
        return results
    return {}


def _take_with_playwright(url, output_dir, viewports):
    """capture screenshots using playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for width in viewports:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(url, wait_until="networkidle")
            page.screenshot(
                path=os.path.join(output_dir, f"{width}.png"),
                full_page=True,
            )
            page.close()
        browser.close()


def _take_with_chromium_subprocess(url, output_dir, viewports):
    """capture screenshots using chromium in headless mode."""
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    for width in viewports:
        out_path = os.path.join(output_dir, f"{width}.png")
        cmd = [
            chromium,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--window-size={width},900",
            f"--screenshot={out_path}",
            url,
        ]
        try:
            subprocess.run(cmd, check=True, timeout=30, capture_output=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"chromium screenshot failed for {width}px: {e}")


def build_parser():
    """build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="visual regression screenshot comparison tool"
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to screenshot",
    )
    parser.add_argument(
        "--output-dir",
        default=".fat-screenshots",
        help="directory for screenshots (default: .fat-screenshots)",
    )
    parser.add_argument(
        "--viewports",
        default="375,1440",
        help="comma-separated viewport widths (default: 375,1440)",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    viewports = parse_viewports(args.viewports)
    print(f"capturing {args.url} at viewports: {viewports}")

    results = take_screenshots(args.url, args.output_dir, viewports)

    if results is None:
        sys.exit(1)
    elif not results:
        print("first run - baseline screenshots saved. no comparison yet.")
    else:
        print("\nvisual regression results:")
        for fname, diff in sorted(results.items()):
            if diff < 0:
                print(f"  {fname}: NEW (no previous baseline)")
            elif diff == 0.0:
                print(f"  {fname}: identical")
            else:
                print(f"  {fname}: {diff:.2f}% pixels changed")


if __name__ == "__main__":
    main()
