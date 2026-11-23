import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from PIL import Image, ImageCms, ImageDraw, ImageOps


SCRIPT = Path(__file__).resolve().parents[1] / "wedding-sketch-poster" / "scripts" / "compose_poster.py"


class CompositionTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.photo = self.root / "场布 original.png"
        self.sketch = self.root / "sketch.png"
        self.output = self.root / "poster.png"

        self.scene = Image.new("RGB", (512, 288), (87, 124, 71))
        brush = ImageDraw.Draw(self.scene)
        brush.rectangle((0, 0, 511, 80), fill=(198, 225, 235))
        brush.ellipse((125, 28, 375, 301), outline=(246, 198, 189), width=15)
        brush.polygon([(215, 154), (292, 154), (410, 287), (102, 287)], fill=(210, 194, 150))
        self.scene.save(self.photo)

        sketch = Image.new("RGBA", (400, 300))
        brush = ImageDraw.Draw(sketch)
        brush.arc((89, 52, 307, 288), start=175, end=365, fill=(173, 136, 120, 220), width=8)
        brush.ellipse((65, 152, 134, 226), fill=(234, 163, 144, 200))
        brush.polygon([(172, 159), (235, 159), (311, 259), (92, 259)], fill=(212, 182, 124, 155))
        sketch.save(self.sketch)

    def render(self, *options, title="暮色花庭", output=None):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--photo", str(self.photo), "--sketch", str(self.sketch),
             "--title", title, "--output", str(output or self.output), *options],
            capture_output=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"},
        )

    def report(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_native_pixels_and_repeatable_png(self):
        report = self.report(self.render())
        self.assertEqual(report["layout"], "side-by-side")
        self.assertEqual(report["sketch_blend"], "alpha")
        self.assertFalse(report["photo_resampled"])
        self.assertEqual(report["font"]["weight"], 400)
        self.assertLess(report["photo_box"][2], report["art_box"][0])
        self.assertLess(report["art_box"][3], report["title_box"][1])
        with Image.open(self.output) as png:
            self.assertEqual(png.crop(report["photo_box"]).tobytes(), self.scene.tobytes())
            self.assertEqual(png.info["srgb"], 0)
            self.assertGreater(len(png.crop((0, 0, 120, 120)).getcolors()), 4)

        duplicate = self.root / "repeat.png"
        self.report(self.render(output=duplicate))
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).digest(),
                         hashlib.sha256(duplicate.read_bytes()).digest())

    def test_portrait_exif_white_matte_and_embedded_icc(self):
        exif = self.scene.getexif()
        exif[274] = 6
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.photo = self.root / "portrait.jpg"
        self.scene.save(self.photo, exif=exif, icc_profile=icc)
        with Image.open(self.sketch) as transparent:
            matte = Image.new("RGB", transparent.size, (249, 247, 239))
            matte.paste(transparent, mask=transparent.getchannel("A"))
        matte.save(self.sketch)

        report = self.report(self.render(title="Garden Vows"))
        self.assertEqual(report["layout"], "stacked")
        self.assertEqual(report["sketch_blend"], "multiply")
        self.assertEqual(report["sketch_matte_srgb"], "#F9F7EF")
        self.assertEqual(report["font"]["file"], "CutiveMono-Regular.ttf")
        self.assertLess(report["photo_box"][3], report["art_box"][1])
        with Image.open(self.output) as png, Image.open(self.photo) as original:
            self.assertEqual(png.info["icc_profile"], icc)
            self.assertEqual(png.crop(report["photo_box"]).tobytes(),
                             ImageOps.exif_transpose(original).convert("RGB").tobytes())

    def test_smaller_canvas_requires_explicit_contain(self):
        result = self.render("--size", "400x320")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--photo-fit contain", result.stderr)
        self.assertFalse(self.output.exists())

        report = self.report(self.render("--size", "400x320", "--photo-fit", "contain"))
        self.assertTrue(report["photo_resampled"])
        with Image.open(self.output) as png:
            region = png.crop(report["photo_box"])
            self.assertEqual(png.size, (400, 320))
            self.assertEqual(region.tobytes(), self.scene.resize(region.size, Image.Resampling.LANCZOS).tobytes())

    def test_failed_inputs_leave_destinations_intact(self):
        result = self.render(title="Garden\nVows")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("one printable line", result.stderr)
        self.assertFalse(self.output.exists())

        self.output.write_bytes(b"existing destination")
        with self.subTest("explicit replacement"):
            result = self.render()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(self.output.read_bytes(), b"existing destination")
            self.report(self.render("--overwrite"))

        with self.subTest("source path protection"):
            before = self.photo.read_bytes()
            result = self.render("--overwrite", output=self.photo)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.photo.read_bytes(), before)

        with self.subTest("blank illustration"):
            Image.new("RGBA", (100, 100)).save(self.sketch)
            path = self.root / "invalid.png"
            result = self.render(output=path)
            self.assertIn("visible watercolor", result.stderr)
            self.assertFalse(path.exists())

    def test_opaque_sketch_that_turns_blank_is_rejected(self):
        pale = Image.new("RGB", (160, 90), "white")
        ImageDraw.Draw(pale).ellipse((24, 18, 133, 70), fill=(253, 250, 249))
        pale.save(self.sketch)
        result = self.render()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("visible watercolor", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
