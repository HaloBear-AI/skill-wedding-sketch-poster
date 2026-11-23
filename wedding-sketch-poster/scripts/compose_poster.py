#!/usr/bin/env python3
"""Compose a still wedding photo, a separate illustration and a one-line title."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
import json
import os
from pathlib import Path
from random import Random
import re
from statistics import median
import sys
from tempfile import NamedTemporaryFile
import unicodedata

try:
    from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFont, ImageOps, PngImagePlugin
except ImportError as error:
    sys.exit(f"Pillow is required. Install scripts/requirements.txt: {error}")


Box = tuple[int, int, int, int]
Size = tuple[int, int]
SEED = 26
PAPER = "#FAEAD6"
INK = "#534A40"
MAX_SIDE = 10_000
MAX_PIXELS = 48_000_000
STILL_FORMATS = {"JPEG", "PNG", "WEBP"}
EIGHT_BIT_MODES = {"1", "L", "LA", "P", "RGB", "RGBA", "RGBX"}
FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
LATIN = FONTS / "CutiveMono-Regular.ttf"
CJK = FONTS / "NotoSansSC-Variable.ttf"


@dataclass(frozen=True)
class Layout:
    ratio: Size
    photo_slot: Box
    art_slot: Box


# Slots are half-open boxes in thousandths of the canvas width and height.
LAYOUTS = {
    "side-by-side": Layout((4, 3), (45, 120, 690, 880), (710, 180, 965, 820)),
    "stacked": Layout((3, 4), (60, 55, 940, 620), (240, 665, 760, 945)),
}


def box_size(box: Box) -> Size:
    return box[2] - box[0], box[3] - box[1]


def center(size: Size, slot: Box) -> Box:
    width, height = size
    slot_width, slot_height = box_size(slot)
    left = slot[0] + (slot_width - width) // 2
    top = slot[1] + (slot_height - height) // 2
    return left, top, left + width, top + height


def pixels(fraction: int, length: int) -> int:
    return (fraction * length + 500) // 1000


def slot_box(slot: Box, size: Size) -> Box:
    left, top, right, bottom = slot
    width, height = size
    return pixels(left, width), pixels(top, height), pixels(right, width), pixels(bottom, height)


def fit(source: Size, limit: Size, *, enlarge: bool) -> Size:
    width, height = source
    max_width, max_height = limit
    if not enlarge and width <= max_width and height <= max_height:
        return source
    if max_width * height <= max_height * width:
        return max_width, max(1, (height * max_width + width // 2) // width)
    return max(1, (width * max_height + height // 2) // height), max_height


def native_canvas(photo: Size, layout: Layout) -> Size:
    ratio_width, ratio_height = layout.ratio
    slot_width, slot_height = box_size(layout.photo_slot)
    unit = max(
        -(-320 // min(layout.ratio)),
        -(-(1000 * photo[0]) // (ratio_width * slot_width)),
        -(-(1000 * photo[1]) // (ratio_height * slot_height)),
    )
    return unit * ratio_width, unit * ratio_height


def valid_size(size: Size) -> bool:
    width, height = size
    return 320 <= min(size) <= max(size) <= MAX_SIDE and width * height <= MAX_PIXELS


def parse_size(value: str) -> Size:
    match = re.fullmatch(r"([0-9]{1,5})[xX]([0-9]{1,5})", value)
    if match is None:
        raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT, for example 2000x1500.")
    size = int(match[1]), int(match[2])
    if not valid_size(size):
        raise argparse.ArgumentTypeError("Use sides of 320–10000 px and at most 48 megapixels.")
    return size


def read_still(path: Path, label: str) -> Image.Image:
    with Image.open(path) as source:
        if source.format not in STILL_FORMATS or getattr(source, "n_frames", 1) != 1:
            raise ValueError(f"{label}: use a single-frame PNG, JPEG or WebP.")
        if source.width * source.height > MAX_PIXELS:
            raise ValueError(f"{label}: use an input of at most 48 megapixels.")
        if source.mode not in EIGHT_BIT_MODES:
            raise ValueError(f"{label}: export an 8-bit RGB/sRGB copy from your image editor.")
        return ImageOps.exif_transpose(source)


def rgb_profile(data: bytes | None, label: str) -> ImageCms.ImageCmsProfile | None:
    if not data:
        return None
    try:
        profile = ImageCms.getOpenProfile(BytesIO(data))
        if profile.profile.xcolor_space.strip() == "RGB":
            return profile
    except (OSError, ValueError, ImageCms.PyCMSError):
        pass
    raise ValueError(f"{label}: export an sRGB copy with a readable RGB ICC profile.")


def read_photo(path: Path) -> tuple[Image.Image, bytes | None]:
    photo = read_still(path, "Photo")
    if "A" in photo.getbands() or "transparency" in photo.info:
        if photo.convert("RGBA").getchannel("A").getextrema()[0] < 255:
            raise ValueError("Photo: supply an opaque photo or render.")
    profile = photo.info.get("icc_profile")
    rgb_profile(profile, "Photo")
    return photo.convert("RGB"), profile


def noise(size: Size, cells: Size, amplitude: int, rng: Random) -> Image.Image:
    width, height = cells
    table = [128 + (index * (2 * amplitude + 1) // 256) - amplitude for index in range(256)]
    layer = Image.frombytes("L", cells, rng.randbytes(width * height)).point(table)
    return layer.resize(size, Image.Resampling.BICUBIC)


def make_paper(size: Size, tone: str) -> Image.Image:
    width, height = size
    rng = Random(SEED)
    broad = noise(size, (width // 92 + 2, height // 92 + 2), 5, rng)
    grain = noise(size, (width // 3 + 1, height // 3 + 1), 3, rng)
    shade = ImageChops.add(broad, grain, offset=-128)
    pen = ImageDraw.Draw(shade)
    for _ in range(min(9000, width * height // 1050)):
        x, y = rng.randrange(width), rng.randrange(height)
        value = shade.getpixel((x, y)) + rng.choice((-4, -3, 2, 3))
        pen.line((x, y, x + rng.randrange(1, 5), y - rng.randrange(0, 3)), fill=value)
    channels = []
    for index in (1, 3, 5):
        offset = int(tone[index:index + 2], 16) - 128
        channels.append(shade.point([max(0, min(255, level + offset)) for level in range(256)]))
    return Image.merge("RGB", tuple(channels))


def white_matte(sketch: Image.Image) -> tuple[tuple[int, int, int], int]:
    probe = sketch.copy()
    probe.thumbnail((384, 384), Image.Resampling.BOX)
    width, height = probe.size
    band = max(1, min(probe.size) // 28)
    edges = [(0, 0, width, band), (0, height - band, width, height),
             (0, 0, band, height), (width - band, 0, width, height)]
    samples = []
    for edge in edges:
        strip = probe.crop(edge)
        near_white = [rgb for rgb in strip.get_flattened_data() if min(rgb) >= 205 and max(rgb) - min(rgb) <= 48]
        if len(near_white) * 4 < strip.width * strip.height * 3:
            raise ValueError("Sketch: use transparent PNG or keep light, even margins on all four sides.")
        samples.extend(near_white)
    base = tuple(round(median(channel)) for channel in zip(*samples))
    deviations = sorted(max(abs(value - white) for value, white in zip(rgb, base)) for rgb in samples)
    p95 = deviations[(len(deviations) - 1) * 95 // 100]
    if p95 > 12:
        raise ValueError("Sketch: use an even near-white matte. The page edges vary too much in color.")
    # Convert the tolerance from source RGB to the normalized ink scale.
    return base, max(4, (p95 * 255 + min(base) - 1) // min(base) + 2)


def trim_art(image: Image.Image, signal: Image.Image, cutoff: int, fill: str | tuple) -> Image.Image:
    histogram = signal.histogram()
    if sum(histogram[cutoff + 1:]) < max(2, image.width * image.height // 100_000):
        raise ValueError("Sketch: supply visible watercolor washes or line work.")
    bounds = signal.point([255 if value > cutoff else 0 for value in range(256)]).getbbox()
    left, top, right, bottom = bounds
    pad = max(2, pixels(10, max(right - left, bottom - top)))
    bounds = max(0, left - pad), max(0, top - pad), min(image.width, right + pad), min(image.height, bottom + pad)
    return ImageOps.expand(image.crop(bounds), border=pad, fill=fill)


def prepare_sketch(path: Path) -> tuple[Image.Image, str, str | None]:
    source = read_still(path, "Sketch")
    rgba = source.convert("RGBA")
    rgba.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    alpha = rgba.getchannel("A")
    profile = rgb_profile(source.info.get("icc_profile"), "Sketch")
    rgb = rgba.convert("RGB")
    if profile is not None:
        rgb = ImageCms.profileToProfile(rgb, profile, ImageCms.createProfile("sRGB"), outputMode="RGB")
    if sum(alpha.histogram()[:16]) >= max(1, rgba.width * rgba.height // 100):
        rgb.putalpha(alpha)
        return trim_art(rgb, alpha, 4, (0, 0, 0, 0)), "alpha", None

    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgb, (0, 0), alpha)
    base, cutoff = white_matte(white)
    channels = [band.point([min(255, (level * 255 + paper // 2) // paper) for level in range(256)])
                for band, paper in zip(white.split(), base)]
    strength = ImageChops.invert(ImageChops.darker(channels[0], ImageChops.darker(channels[1], channels[2])))
    # Ease pigment in over the next 14 levels so pale washes blend into the paper.
    opacity = []
    for level in range(256):
        t = max(0, min(14, level - cutoff))
        opacity.append((255 * t * t * (42 - 2 * t) + 1372) // 2744)
    ink = Image.composite(Image.merge("RGB", tuple(channels)), Image.new("RGB", white.size, "white"),
                          strength.point(opacity))
    effective_strength = strength.point([(level * mask + 127) // 255 for level, mask in enumerate(opacity)])
    matte = "#{:02X}{:02X}{:02X}".format(*base)
    return trim_art(ink, effective_strength, 1, "white"), "multiply", matte


def open_font(path: Path, size: int, weight: int | None) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)
    if weight is not None:
        font.set_variation_by_axes([weight])
    return font


def has_glyphs(font: ImageFont.FreeTypeFont, title: str) -> bool:
    missing = font.getmask("\U0010ffff", mode="L")
    missing_pixels = bytes(missing)
    for character in set(title):
        if not character.isspace():
            tile = font.getmask(character, mode="L")
            if tile.size == missing.size and bytes(tile) == missing_pixels:
                return False
    return True


def title_mask(title: str, font: ImageFont.FreeTypeFont, tracking: int) -> Image.Image:
    runs = []
    advance = 0
    for character in title:
        if not character.isspace():
            runs.append((advance, character, font.getbbox(character)))
        advance += round(font.getlength(character)) + tracking
    left = min(x + box[0] for x, _, box in runs)
    top = min(box[1] for _, _, box in runs)
    right = max(x + box[2] for x, _, box in runs)
    bottom = max(box[3] for _, _, box in runs)
    mask = Image.new("L", (max(1, right - left), max(1, bottom - top)))
    pen = ImageDraw.Draw(mask)
    for x, character, _ in runs:
        pen.text((x - left, -top), character, font=font, fill=255)
    bounds = mask.getbbox()
    if not bounds:
        raise ValueError("Title: use visible text with a font that covers its characters.")
    return mask.crop(bounds)


def make_title(title: str, custom_font: Path | None, canvas_width: int, limit: Size) -> tuple[Image.Image, dict]:
    if not title.strip() or not title.isprintable() or len(title) > 100:
        raise ValueError("Title: use one printable line of 1–100 characters.")
    minimum = max(10, pixels(10, canvas_width))
    size = max(minimum, pixels(19, canvas_width))
    candidates = [(custom_font, None)] if custom_font else [(LATIN, None), (CJK, 400)]
    for path, weight in candidates:
        font = open_font(path, size, weight)
        if has_glyphs(font, title):
            break
    else:
        raise ValueError("Title: supply --font with a font that covers all the title characters.")
    while size >= minimum:
        tracking = pixels(100, size)
        mask = title_mask(title, font, tracking)
        if mask.width <= limit[0] and mask.height <= limit[1]:
            return mask, {"file": path.name, "family": font.getname()[0], "size_px": size,
                          "weight": weight, "tracking_px": tracking, "ink_srgb": INK}
        size -= 1
        if size >= minimum:
            font = open_font(path, size, weight)
    raise ValueError("Title: shorten the line or use a larger canvas to keep the lettering readable.")


def save_png(poster: Image.Image, path: Path, profile: bytes | None, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Output is locked by another render: {path}") from None
    temporary = None
    try:
        if not overwrite and (path.exists() or path.is_symlink()):
            raise ValueError(f"Output already exists: {path}. Use a new path or pass --overwrite.")
        metadata = PngImagePlugin.PngInfo()
        if profile is None:
            metadata.add(b"sRGB", b"\x00")
        with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
            temporary = Path(file.name)
            poster.save(file, format="PNG", compress_level=6, pnginfo=metadata, icc_profile=profile)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.rmdir()


def compose(args: argparse.Namespace) -> dict:
    sources = [args.photo, args.sketch]
    if args.font is not None:
        sources.append(args.font)
    if args.photo.resolve() == args.sketch.resolve():
        raise ValueError("Use separate photo and illustration files.")
    if args.output.suffix.lower() != ".png" or args.output.resolve() in {path.resolve() for path in sources}:
        raise ValueError("Choose a separate .png output path.")
    photo, profile = read_photo(args.photo)
    name = args.layout
    if name == "auto":
        name = "side-by-side" if photo.width >= photo.height else "stacked"
    layout = LAYOUTS[name]
    size = args.size or native_canvas(photo.size, layout)
    if not valid_size(size):
        raise ValueError(f"Native canvas needs {size[0]}x{size[1]} px. To downsample, choose an explicit "
                         "--size within 48 megapixels and pass --photo-fit contain.")
    photo_slot = slot_box(layout.photo_slot, size)
    photo_size = fit(photo.size, box_size(photo_slot), enlarge=False)
    if args.photo_fit == "native" and photo_size != photo.size:
        raise ValueError(f"Native photo is {photo.width}x{photo.height} px. Omit --size, choose a bigger canvas, "
                         "or authorize downsampling with --photo-fit contain.")
    photo_box = center(photo_size, photo_slot)

    sketch, blend, matte = prepare_sketch(args.sketch)
    art_slot = slot_box(layout.art_slot, size)
    art_width, art_height = box_size(art_slot)
    text = unicodedata.normalize("NFC", args.title)
    title, font = make_title(text, args.font, size[0], (art_width, max(12, art_height // 3)))
    gap = max(2, pixels(22, size[1]))
    sketch_size = fit(sketch.size, (art_width, art_height - title.height - gap), enlarge=True)
    group_height = sketch_size[1] + gap + title.height
    sketch_top = art_slot[1] + (art_height - group_height) // 2
    sketch_box = center(sketch_size, (art_slot[0], sketch_top, art_slot[2], sketch_top + sketch_size[1]))
    title_top = sketch_box[3] + gap
    title_box = center(title.size, (art_slot[0], title_top, art_slot[2], title_top + title.height))

    poster = make_paper(size, args.paper)
    layer = sketch.resize(sketch_size, Image.Resampling.LANCZOS)
    if blend == "alpha":
        poster.paste(layer, sketch_box[:2], layer.getchannel("A"))
    else:
        poster.paste(ImageChops.multiply(poster.crop(sketch_box), layer), sketch_box[:2])
    poster.paste(INK, title_box, title)
    if profile is not None:
        poster = ImageCms.profileToProfile(poster, ImageCms.createProfile("sRGB"), rgb_profile(profile, "Photo"),
                                          outputMode="RGB")
    photo_resampled = photo_size != photo.size
    source_size = photo.size
    if photo_resampled:
        photo = photo.resize(photo_size, Image.Resampling.LANCZOS)
    poster.paste(photo, photo_box[:2])
    save_png(poster, args.output, profile, args.overwrite)
    return {"output": args.output.as_posix(), "size_px": size, "layout": name, "paper_srgb": args.paper,
            "seed": SEED, "profile": "source RGB ICC" if profile else "sRGB", "photo_fit": args.photo_fit,
            "photo_resampled": photo_resampled, "photo_source_size": source_size, "photo_box": photo_box,
            "art_box": sketch_box, "sketch_blend": blend, "sketch_matte_srgb": matte,
            "title_box": title_box, "title": text, "font": font}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", type=Path, required=True, help="Opaque wedding decor photo or render")
    parser.add_argument("--sketch", type=Path, required=True, help="Illustration on transparency or near-white")
    parser.add_argument("--title", required=True, help="One line of text")
    parser.add_argument("--output", type=Path, required=True, help="Output PNG path")
    parser.add_argument("--layout", choices=["auto", *LAYOUTS], default="auto")
    parser.add_argument("--size", type=parse_size, help="Canvas WIDTHxHEIGHT. Default fits the native photo.")
    parser.add_argument("--photo-fit", choices=["native", "contain"], default="native",
                        help="Native pixels by default. Contain permits proportional downsampling.")
    parser.add_argument("--paper", default=PAPER, help="Paper RGB hex color")
    parser.add_argument("--font", type=Path, help="Custom font with all the title glyphs")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output PNG")
    args = parser.parse_args()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", args.paper):
        parser.error("--paper expects an RGB hex color such as '#FAEAD6'.")
    try:
        result = compose(args)
    except (OSError, ValueError, RuntimeError, Image.DecompressionBombError, ImageCms.PyCMSError) as error:
        print(f"Poster composition failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
