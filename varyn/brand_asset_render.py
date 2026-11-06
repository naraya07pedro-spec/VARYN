"""Build-time rasterization of properly licensed brand SVG assets.

Runs ONLY in the Linux CI icon-asset job. The packaged Windows program ships
with ordinary PNG files, never a runtime browser/Cairo or downloaded icon URLs.
Brand logos are third-party trademarks, not endorsements of VARYN.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

BRAND_COLORS = {
    "netlify": "#00C7B7",
    "hostinger_mail": "#673DE6",
    "google_docs": "#4285F4",
    "google_sheets": "#0F9D58",
    "hubspot": "#FF7A59",
    "dropbox": "#0061FF",
    "spotify": "#1DB954",
}


def render(source: Path, dest: Path):
    import cairosvg

    source = Path(source).resolve()
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted(source.glob("*.svg"))
    if not 10 <= len(files) <= 45:
        raise RuntimeError("Expected curated offline brand SVG collection")
    for path in files:
        data = path.read_text(encoding="utf-8")
        normalized = data.lstrip()
        if normalized.startswith("<?xml"):
            normalized = normalized.split("?>", 1)[-1].lstrip()
        if len(data) > 24000 or not normalized.startswith("<svg"):
            raise RuntimeError("Invalid curated icon SVG")
        # Curated SVG files are immutable inputs from the verified source
        # commits. Do not permit fetching external assets or injecting code.
        if re.search(r"(?i)<script|<!DOCTYPE|<!ENTITY|<foreignObject|<image|"
                     r"\bhref\s*=\s*['\"](?!#)|\burl\s*\(\s*['\"]?https?\s*:",
                     data):
            raise RuntimeError("Unsafe external SVG features refused: " + path.name)
        fill = BRAND_COLORS.get(path.stem)
        if fill is not None:
            # CC0 single-color Simple Icons assets inherit root fill. MIT
            # SuperTinyIcons retain their multicolor original path fills.
            data = data.replace("<svg ", '<svg fill="' + fill + '" ', 1)
        png = dest / (path.stem + ".png")
        cairosvg.svg2png(bytestring=data.encode("utf-8"),
                         write_to=str(png), output_width=48, output_height=48)
        if png.stat().st_size > 64 * 1024 or png.stat().st_size < 100:
            raise RuntimeError("Unexpected rendered PNG size")
    return len(files)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m varyn.brand_asset_render source/ target/")
    print("Rendered genuine third-party brand icon assets:", render(
        Path(sys.argv[1]), Path(sys.argv[2]),
    ))
