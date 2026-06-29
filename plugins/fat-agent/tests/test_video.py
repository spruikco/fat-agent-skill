#!/usr/bin/env python3
"""Tests for the Video SEO module."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from modules.video import VideoModule

YT = '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
VO_FULL = (
    YT
    + '<script type="application/ld+json">{"@type":"VideoObject","name":"n","description":"d",'
    '"thumbnailUrl":"t.jpg","uploadDate":"2026-01-01"}</script>'
)
VO_PARTIAL = (
    YT
    + '<script type="application/ld+json">{"@type":"VideoObject","name":"n"}</script>'
)


class TestDetect(unittest.TestCase):
    def test_detect_youtube(self):
        self.assertTrue(VideoModule.detect(YT))

    def test_detect_video_tag(self):
        self.assertTrue(VideoModule.detect("<video src='a.mp4'></video>"))

    def test_no_video(self):
        self.assertFalse(VideoModule.detect("<p>no video here</p>"))


class TestAnalyseScore(unittest.TestCase):
    def test_missing_videoobject_finding(self):
        m = VideoModule()
        m.score(m.analyse(YT, "https://x.example/v"))
        self.assertTrue(any("no VideoObject" in f["title"] for f in m.findings))

    def test_partial_videoobject_lists_missing(self):
        m = VideoModule()
        a = m.analyse(VO_PARTIAL, "https://x.example/v")
        self.assertTrue(a["has_videoobject"])
        self.assertFalse(a["required_props"]["uploadDate"])
        m.score(a)
        self.assertTrue(
            any("missing required" in f["title"].lower() for f in m.findings)
        )

    def test_full_videoobject_scores_high(self):
        m = VideoModule()
        s = m.score(m.analyse(VO_FULL, "https://x.example/v"))
        self.assertGreaterEqual(s["total"], 70)
        self.assertFalse(any("no VideoObject" in f["title"] for f in m.findings))


if __name__ == "__main__":
    unittest.main()
