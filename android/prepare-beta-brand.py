#!/usr/bin/env python3
"""Derive beta launcher/store artwork from the pinned official DragonZpyder favicon.

Outputs are generated, never committed to source. This is a beta status treatment,
not a replacement of the official underlying brand. Requires Pillow==11.3.0.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "app/src/main/res/drawable-nodpi/brand_icon.png"
DEST = ROOT / "app/src/main/res/drawable-nodpi/brand_icon_beta.png"
STORE = ROOT / "play-assets"
INK = (16, 17, 20, 255)
ORANGE = (255, 139, 70, 255)
WHITE = (250, 247, 242, 255)

def font(size):
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()

def centered(draw, at, text, selected_font, fill):
    bounds = draw.textbbox((0, 0), text, font=selected_font)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.text((int(at[0] - width / 2 - bounds[0]), int(at[1] - height / 2 - bounds[1])), text, font=selected_font, fill=fill)

def badge(canvas, coords, size):
    dr = ImageDraw.Draw(canvas)
    dr.rounded_rectangle(coords, radius=round(size * 0.22), fill=ORANGE)
    centered(dr, ((coords[0] + coords[2]) // 2, (coords[1] + coords[3]) // 2), "BETA", font(round(size * 0.63)), INK)

def main():
    if not SOURCE.is_file():
        raise SystemExit("Missing pinned official brand_icon.png; run prepare-brand.sh first")
    original = Image.open(SOURCE).convert("RGBA")
    canvas = Image.new("RGBA", (512, 512), INK)
    mark = ImageOps.contain(original, (390, 390), Image.Resampling.LANCZOS)
    canvas.alpha_composite(mark, ((512 - mark.width) // 2, 34 + (360 - mark.height) // 2))
    badge(canvas, (273, 416, 477, 477), 44)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(DEST, optimize=True)
    STORE.mkdir(parents=True, exist_ok=True)
    canvas.save(STORE / "play_icon_512.png", optimize=True)

    feature = Image.new("RGBA", (1024, 500), INK)
    dr = ImageDraw.Draw(feature)
    for y in range(500):
        shade = int(y * 13 / 499)
        dr.line((0, y, 1024, y), fill=(16 + shade, 17 + shade // 2, 20 + shade // 2, 255))
    mark = ImageOps.contain(original, (345, 345), Image.Resampling.LANCZOS)
    feature.alpha_composite(mark, (71 + (345 - mark.width) // 2, 68 + (345 - mark.height) // 2))
    dr = ImageDraw.Draw(feature)
    dr.text((445, 172), "DragonZpyder", font=font(65), fill=WHITE)
    dr.text((450, 263), "PERSONAL AI  •  EARLY ACCESS", font=font(21), fill=(186, 182, 178, 255))
    badge(feature, (451, 319, 598, 369), 35)
    feature.convert("RGB").save(STORE / "feature_graphic_1024x500.png", optimize=True)
    print("Generated beta launcher icon and Play artwork from pinned official brand.")

if __name__ == "__main__":
    main()
