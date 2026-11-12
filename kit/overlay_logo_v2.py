"""Place the official logo unchanged (only scaled, proportions kept) top-right.
Usage: python3 overlay_logo_v2.py logo.png in_dir out_dir [size=200] [margin=30]
"""
import sys, os
from pathlib import Path
from PIL import Image

def main(logo_path, in_dir, out_dir, size=200, margin=30):
    size, margin = int(size), int(margin)
    os.makedirs(out_dir, exist_ok=True)
    logo = Image.open(logo_path).convert("RGBA")
    logo.thumbnail((size, size), Image.LANCZOS)
    for p in sorted(Path(in_dir).glob("*.png")):
        slide = Image.open(p).convert("RGBA")
        slide.alpha_composite(logo, (slide.width - margin - logo.width, margin))
        slide.convert("RGB").save(Path(out_dir) / p.name, "PNG", optimize=True)
        print("logo added", p.name)

if __name__ == "__main__":
    main(*sys.argv[1:])
