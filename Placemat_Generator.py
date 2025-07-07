#!/usr/bin/env python3
"""
Generate elegant PNG place‑name tags from a simple text specification and bundle
all tags into a print‑ready PDF.

Changes from original version
-----------------------------
* **PDF output** using ReportLab instead of Word/`python‑docx`.
* Even grid layout that honours page margins (default 0.5″) and keeps tags
  inside the printable area.
* ➡Still supports two‑per‑row layout by default; customise with `--cols`,
  `--margin`, and `--page-size`.
* ✅ Dependencies: `pip install pillow reportlab`.

Typical usage
-------------
# Pastel circles background → PDF, default A4, two columns
python generate_nametags_pdf.py attendees.txt --random-bubbles

# Flowers background, Letter paper, three columns, narrow margins
python generate_nametags_pdf.py attendees.txt --flowers \
       --page-size letter --cols 3 --margin 0.25
"""
from __future__ import annotations

import argparse
import math
import random
import re
import unicodedata
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont  # type: ignore
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# --------------------------------------------------
# Colour palette
# --------------------------------------------------
PINK        = "#ffc0cb"   # bright pink (bottom-left quarter)
GOLD        = "#ffd700"   # gold (top-right quarter & border)
FAINT_PINK  = "#ffcdfe"   # soft pastel pink
FAINT_GOLD  = "#ffe493"  # soft pastel gold
FAINT_GREEN = "#cce8cf"   # soft pastel green
BLACK       = "#ffffff"
PASTELS     = [FAINT_PINK, FAINT_GOLD, FAINT_GREEN]

# --------------------------------------------------
# Text‑file parsing helper
# --------------------------------------------------

def parse_input(file_path: Path) -> List[Tuple[str, str]]:
    """Return list of (table_name, full_name) pairs."""
    results: List[Tuple[str, str]] = []
    current_table = ""
    with file_path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.lower().startswith("table"):
                current_table = line
            else:
                results.append((current_table, line))
    return results


def sanitize_filename(txt: str) -> str:
    safe = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9_\-]", "_", safe)

# --------------------------------------------------
# Motif helpers (flowers / hearts / etc.)
# --------------------------------------------------

def draw_with_tilt(base_img: Image.Image, draw_fn, cx: int, cy: int, size: int, colour: str):
    """Draw motif with random tilt and paste onto base image."""
    tilt_angle = random.uniform(-30, 30)
    bbox_size = size * 2
    temp_img = Image.new("RGBA", (bbox_size, bbox_size), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    draw_fn(temp_draw, bbox_size // 2, bbox_size // 2, size, colour)

    rotated = temp_img.rotate(tilt_angle, resample=Image.BICUBIC, expand=True)
    rx, ry = rotated.size
    px, py = cx - rx // 2, cy - ry // 2
    base_img.paste(rotated, (px, py), rotated)


def draw_flower(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, colour: str) -> None:
    """Draw a 5‑petal flower centred at (cx, cy) with outer radius r."""
    mid_angle = random.uniform(0, 360)
    half_w = r // 2
    for i in range(5):
        ang = math.radians(mid_angle + i * 72)
        left  = math.radians(mid_angle + i * 72 - 20)
        right = math.radians(mid_angle + i * 72 + 20)
        tip_x = cx + math.cos(ang) * r
        tip_y = cy + math.sin(ang) * r
        bl_x  = cx + math.cos(left)  * half_w
        bl_y  = cy + math.sin(left)  * half_w
        br_x  = cx + math.cos(right) * half_w
        br_y  = cy + math.sin(right) * half_w
        draw.polygon([(cx, cy), (bl_x, bl_y), (tip_x, tip_y), (br_x, br_y)], fill=colour)
    centre = r // 6
    draw.ellipse([(cx-centre, cy-centre), (cx+centre, cy+centre)], fill="white")


def draw_heart(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, colour: str) -> None:
    lobe_r = r * 0.3
    lobe_offset_x = r * 0.3
    lobe_offset_y = r * 0.05
    left_box = [
        (cx - lobe_offset_x - lobe_r, cy - lobe_offset_y - lobe_r),
        (cx - lobe_offset_x + lobe_r, cy - lobe_offset_y + lobe_r),
    ]
    draw.pieslice(left_box, 180, 360, fill=colour)
    right_box = [
        (cx + lobe_offset_x - lobe_r, cy - lobe_offset_y - lobe_r),
        (cx + lobe_offset_x + lobe_r, cy - lobe_offset_y + lobe_r),
    ]
    draw.pieslice(right_box, 180, 360, fill=colour)
    triangle = [
        (cx - r * 0.6, cy - r * 0.05),
        (cx + r * 0.6, cy - r * 0.05),
        (cx, cy + r),
    ]
    draw.polygon(triangle, fill=colour)


def draw_wine_glass(draw: ImageDraw.ImageDraw, cx: int, cy: int, h: int, colour: str) -> None:
    bowl_height = int(h * 0.6)
    bowl_width = h // 2
    stem_height = int(h * 0.3)
    base_width = bowl_width
    bowl_top_y = cy
    bowl_bottom_y = cy + bowl_height
    bowl = [
        (cx - bowl_width // 2, bowl_top_y),
        (cx + bowl_width // 2, bowl_top_y),
        (cx + bowl_width // 6, bowl_bottom_y),
        (cx - bowl_width // 6, bowl_bottom_y),
    ]
    draw.polygon(bowl, fill=colour)
    stem_top_y = bowl_bottom_y
    stem_bottom_y = stem_top_y + stem_height
    stem_width = h // 15
    draw.rectangle(
        [(cx - stem_width // 2, stem_top_y), (cx + stem_width // 2, stem_bottom_y)],
        fill=colour
    )
    base_top = stem_bottom_y
    base_height = h // 20
    draw.ellipse(
        [(cx - base_width // 3, base_top), (cx + base_width // 3, base_top + base_height)],
        fill=colour
    )


def draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, colour: str) -> None:
    width = r * 1.6
    height = r * 1.6
    top_y = cy - height * 0.4
    mid_y = cy
    bottom_y = cy + height * 0.5
    points = [
        (cx - width * 0.4, mid_y),
        (cx - width * 0.2, top_y),
        (cx, top_y + r * 0.05),
        (cx + width * 0.2, top_y),
        (cx + width * 0.4, mid_y),
        (cx, bottom_y),
    ]
    draw.polygon(points, fill=colour)

# --------------------------------------------------
# Tag compositor
# --------------------------------------------------

def compose_tag(
    name: str,
    *,
    font_path: str,
    size: Tuple[int, int],
    font_size: int | None = None,
    random_bubbles: bool = False,
    flowers: bool = False,
    table_label: str = "",
) -> Image.Image:
    W, H = size
    img = Image.new("RGB", size, "white")
    d   = ImageDraw.Draw(img)

    R = min(W, H) // 2
    d.pieslice([(-R, H-2*R), (R, H+R)],   90, 180, fill=PINK)        # bottom-left
    d.pieslice([(W-R, -R),   (W+R, R)],  -90,   0, fill=GOLD)        # top-right

    r_s = min(W, H) // 4
    d.pieslice([(-r_s, -r_s), (r_s, r_s)],           180, 270, fill=FAINT_PINK)
    d.pieslice([(W-r_s, -r_s), (W+r_s, r_s)],         270, 360, fill=FAINT_PINK)

    if random_bubbles or flowers:
        placed: List[Tuple[int, int, int]] = []
        for _ in range(80):
            retries = 50
            while retries:
                r = random.randint(min(W, H) // 30, min(W, H) // 15)
                cx = random.randint(r, W - r)
                cy = random.randint(r, H - r)
                if all(math.hypot(cx - x, cy - y) >= r + pr for x, y, pr in placed):
                    colour = random.choice(PASTELS)
                    if random_bubbles:
                        d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=colour)
                    if flowers:
                        motif = random.choice(("flower", "heart", "wine", "diamond"))
                        if motif == "flower":
                            draw_with_tilt(img, draw_flower, cx, cy, r, colour)
                        elif motif == "heart":
                            draw_with_tilt(img, draw_heart, cx, cy, r, colour)
                        elif motif == "wine":
                            draw_with_tilt(img, draw_wine_glass, cx, cy, r*2, colour)
                        else:
                            draw_with_tilt(img, draw_diamond, cx, cy, r, colour)
                    placed.append((cx, cy, r))
                    break
                retries -= 1

    border = max(2, min(W, H)//25)
    d.rectangle([(0,0), (W-1, H-1)], outline=BLACK, width=border)

    fs = font_size or int(H * 0.25)
    try:
        font = ImageFont.truetype(font_path, fs)
        small_font = ImageFont.truetype(font_path, int(fs * 0.7))
    except OSError:
        print(f"Font '{font_path}' not found; using default.")
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    name_tw, name_th = (lambda b: (b[2]-b[0], b[3]-b[1]))(font.getbbox(name))
    table_tw, table_th = (lambda b: (b[2]-b[0], b[3]-b[1]))(small_font.getbbox(table_label)) if table_label else (0, 0)

    total_height = name_th + (table_th if table_label else 0) + int(H * 0.05)
    name_y = (H - total_height) // 2
    table_y = name_y + name_th + int(H * 0.02)

    d.text(((W - name_tw) / 2, name_y), name, fill="black", font=font)
    if table_label:
        d.text(((W - table_tw) / 2, table_y), table_label, fill="black", font=small_font)

    return img


# --------------------------------------------------
# PDF helper
# --------------------------------------------------

def build_pdf(
    paths: List[Path],
    out_pdf: Path,
    *,
    cols: int,
    tag_size_px: Tuple[int, int],
    page_size_name: str,
    margin_inch: float,
) -> None:
    """Lay out tag PNGs onto a grid and export a single PDF."""
    if page_size_name.lower() == "a4":
        PAGE_W, PAGE_H = A4
    else:
        PAGE_W, PAGE_H = letter

    margin = margin_inch * inch
    cell_w = (PAGE_W - 2*margin) / cols
    tag_w_px, tag_h_px = tag_size_px
    aspect = tag_h_px / tag_w_px
    cell_h = cell_w * aspect

    row_gap = col_gap = 0.1 * inch  # small breathing space
    rows = int((PAGE_H - 2*margin + row_gap) // (cell_h + row_gap))
    if rows == 0:
        rows = 1

    total_per_page = cols * rows
    c = canvas.Canvas(str(out_pdf), pagesize=(PAGE_W, PAGE_H))

    for idx, p in enumerate(paths):
        page_idx = idx // total_per_page
        local_idx = idx % total_per_page
        col = local_idx % cols
        row = local_idx // cols

        x = margin + col * (cell_w + col_gap)
        y = PAGE_H - margin - (row + 1) * (cell_h + row_gap) + row_gap

        c.drawImage(str(p), x, y, width=cell_w, height=cell_h, preserveAspectRatio=True, mask='auto')

        if (idx + 1) % total_per_page == 0 and idx + 1 < len(paths):
            c.showPage()

    c.save()

# --------------------------------------------------
# CLI
# --------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate PNG name tags and bundle them into a compact PDF.")
    ap.add_argument("input", type=Path, help="Text file with TABLE … / names list")
    ap.add_argument("--font", default="GreatVibes-Regular.ttf", help="Path to .ttf script font")
    ap.add_argument("--font-size", type=int, help="Explicit font size (pt). Default scales to tag.")
    ap.add_argument("--size", default="1000x500", help="Tag size WIDTHxHEIGHT pixels (default 1000x500)")
    ap.add_argument("--random-bubbles", action="store_true", help="Add random pastel circles")
    ap.add_argument("--flowers", action="store_true", help="Add random stylised flowers")
    ap.add_argument("--page-size", choices=["letter", "a4"], default="a4", help="PDF page size")
    ap.add_argument("--cols", type=int, default=2, help="Number of columns per page (default 2)")
    ap.add_argument("--margin", type=float, default=0.5, help="Page margin in inches (default 0.5)")
    args = ap.parse_args()

    try:
        W, H = map(int, args.size.lower().split("x"))
    except ValueError:
        ap.error("--size must be WIDTHxHEIGHT (e.g. 1200x600)")

    out_dir = Path("Placemats")
    out_dir.mkdir(exist_ok=True)

    entries = parse_input(args.input)
    if not entries:
        raise SystemExit("No names found in input.")

    print("Creating tags …")
    tag_paths: List[Path] = []
    for tbl, name in entries:
        out_path = out_dir / f"{sanitize_filename(tbl+'_'+name)}.png"
        img = compose_tag(
            name,
            font_path=args.font,
            size=(W, H),
            font_size=args.font_size,
            random_bubbles=args.random_bubbles,
            flowers=args.flowers,
            table_label=tbl,  # <- this passes the table label
        )
        img.save(out_path, "PNG")
        tag_paths.append(out_path)
        print("  ✔︎", out_path)

    pdf_file = out_dir / "NameTags.pdf"
    print("Building PDF …")
    build_pdf(
        tag_paths,
        pdf_file,
        cols=args.cols,
        tag_size_px=(W, H),
        page_size_name=args.page_size,
        margin_inch=args.margin,
    )

    print("Done — PDF saved to", pdf_file)


if __name__ == "__main__":
    main()
