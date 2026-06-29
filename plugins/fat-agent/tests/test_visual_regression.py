"""Tests for visual regression screenshot comparison tool."""

import os
import shutil
import sys
import tempfile
import unittest

# ensure scripts dir is importable
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "scripts"),
)


class TestCheckPlaywrightAvailable(unittest.TestCase):
    """Test that check_playwright_available returns a bool."""

    def test_returns_bool(self):
        from visual_regression import check_playwright_available

        result = check_playwright_available()
        self.assertIsInstance(result, bool)


class TestViewportParsing(unittest.TestCase):
    """Test viewport string parsing."""

    def test_default_viewports(self):
        from visual_regression import parse_viewports

        result = parse_viewports("375,1440")
        self.assertEqual(result, [375, 1440])

    def test_single_viewport(self):
        from visual_regression import parse_viewports

        result = parse_viewports("768")
        self.assertEqual(result, [768])

    def test_multiple_viewports(self):
        from visual_regression import parse_viewports

        result = parse_viewports("320,768,1024,1920")
        self.assertEqual(result, [320, 768, 1024, 1920])

    def test_whitespace_handling(self):
        from visual_regression import parse_viewports

        result = parse_viewports(" 375 , 1440 ")
        self.assertEqual(result, [375, 1440])

    def test_invalid_viewport_raises(self):
        from visual_regression import parse_viewports

        with self.assertRaises(ValueError):
            parse_viewports("abc,def")


class TestOutputDirectoryCreation(unittest.TestCase):
    """Test that output directories are created properly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_output_dir(self):
        from visual_regression import ensure_output_dir

        target = os.path.join(self.tmpdir, "screenshots")
        result = ensure_output_dir(target)
        self.assertTrue(os.path.isdir(result))

    def test_creates_nested_output_dir(self):
        from visual_regression import ensure_output_dir

        target = os.path.join(self.tmpdir, "a", "b", "c")
        result = ensure_output_dir(target)
        self.assertTrue(os.path.isdir(result))

    def test_existing_dir_no_error(self):
        from visual_regression import ensure_output_dir

        os.makedirs(os.path.join(self.tmpdir, "existing"))
        result = ensure_output_dir(os.path.join(self.tmpdir, "existing"))
        self.assertTrue(os.path.isdir(result))


class TestCalculatePixelDiff(unittest.TestCase):
    """Test pixel diff calculation using Pillow-generated test images."""

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not available")
        self.tmpdir = tempfile.mkdtemp()
        self.Image = Image

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_image(self, color, size=(100, 100)):
        """create a solid-colour test PNG."""
        img = self.Image.new("RGB", size, color)
        path = os.path.join(self.tmpdir, f"test_{color[0]}_{color[1]}_{color[2]}.png")
        img.save(path)
        return path

    def test_identical_images_zero_diff(self):
        from visual_regression import calculate_pixel_diff

        img1 = self._make_image((255, 0, 0))
        img2 = self._make_image((255, 0, 0))
        diff = calculate_pixel_diff(img1, img2)
        self.assertAlmostEqual(diff, 0.0)

    def test_completely_different_images(self):
        from visual_regression import calculate_pixel_diff

        img1 = self._make_image((0, 0, 0))
        img2 = self._make_image((255, 255, 255))
        diff = calculate_pixel_diff(img1, img2)
        self.assertGreater(diff, 0.0)
        self.assertAlmostEqual(diff, 100.0)

    def test_partially_different_images(self):
        from visual_regression import calculate_pixel_diff

        # create a 100x100 image, half red half blue
        img1 = self.Image.new("RGB", (100, 100), (255, 0, 0))
        path1 = os.path.join(self.tmpdir, "partial1.png")
        img1.save(path1)

        img2 = self.Image.new("RGB", (100, 100), (255, 0, 0))
        # make bottom half different
        for x in range(100):
            for y in range(50, 100):
                img2.putpixel((x, y), (0, 0, 255))
        path2 = os.path.join(self.tmpdir, "partial2.png")
        img2.save(path2)

        diff = calculate_pixel_diff(path1, path2)
        self.assertGreater(diff, 0.0)
        self.assertLess(diff, 100.0)
        # should be approximately 50%
        self.assertAlmostEqual(diff, 50.0, delta=1.0)

    def test_different_size_images(self):
        from visual_regression import calculate_pixel_diff

        img1 = self._make_image((255, 0, 0), size=(100, 100))
        img2 = self._make_image((255, 0, 0), size=(200, 200))
        # should handle gracefully - either resize or report difference
        diff = calculate_pixel_diff(img1, img2)
        self.assertIsInstance(diff, float)

    def test_returns_float(self):
        from visual_regression import calculate_pixel_diff

        img1 = self._make_image((128, 128, 128))
        img2 = self._make_image((129, 128, 128))
        diff = calculate_pixel_diff(img1, img2)
        self.assertIsInstance(diff, float)
        self.assertGreaterEqual(diff, 0.0)
        self.assertLessEqual(diff, 100.0)


class TestCompareScreenshots(unittest.TestCase):
    """Test comparing screenshot directories."""

    def setUp(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not available")
        self.tmpdir = tempfile.mkdtemp()
        self.Image = Image

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_compare_matching_dirs(self):
        from visual_regression import compare_screenshots

        current = os.path.join(self.tmpdir, "current")
        previous = os.path.join(self.tmpdir, "previous")
        os.makedirs(current)
        os.makedirs(previous)

        img = self.Image.new("RGB", (50, 50), (255, 0, 0))
        img.save(os.path.join(current, "375.png"))
        img.save(os.path.join(previous, "375.png"))

        results = compare_screenshots(current, previous)
        self.assertIn("375.png", results)
        self.assertAlmostEqual(results["375.png"], 0.0)

    def test_compare_missing_previous(self):
        from visual_regression import compare_screenshots

        current = os.path.join(self.tmpdir, "current")
        previous = os.path.join(self.tmpdir, "previous")
        os.makedirs(current)
        # no previous dir

        results = compare_screenshots(current, previous)
        self.assertEqual(results, {})


class TestCLIArgParsing(unittest.TestCase):
    """Test argument parser construction."""

    def test_default_args(self):
        from visual_regression import build_parser

        parser = build_parser()
        args = parser.parse_args(["--url", "https://example.com"])
        self.assertEqual(args.url, "https://example.com")
        self.assertEqual(args.output_dir, ".fat-screenshots")
        self.assertEqual(args.viewports, "375,1440")

    def test_custom_args(self):
        from visual_regression import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "--url",
                "https://test.com",
                "--output-dir",
                "/tmp/shots",
                "--viewports",
                "320,768,1920",
            ]
        )
        self.assertEqual(args.url, "https://test.com")
        self.assertEqual(args.output_dir, "/tmp/shots")
        self.assertEqual(args.viewports, "320,768,1920")

    def test_url_required(self):
        from visual_regression import build_parser

        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])


if __name__ == "__main__":
    unittest.main()
