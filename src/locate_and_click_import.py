# -*- coding: utf-8 -*-
"""Locate Excel批量导入 by scanning green-ish icon pixels, then click."""
from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageGrab
from pywinauto import Desktop, mouse

OUT = Path(__file__).resolve().parent


def find_frame():
    return Desktop(backend="win32").windows(class_name="SunAwtFrame", visible_only=True)[0]


def dialogs():
    return [
        (w.window_text() or "", w.element_info.class_name, w.rectangle())
        for w in Desktop(backend="win32").windows(visible_only=True)
        if "SunAwt" in (w.element_info.class_name or "") or "Excel" in (w.window_text() or "")
        or "#32770" == (w.element_info.class_name or "")
    ]


def find_green_icons(img: Image.Image) -> list[tuple[int, int]]:
    """Find clusters of green pixels (Excel import arrow icon)."""
    w, h = img.size
    hits = []
    for y in range(h):
        for x in range(w):
            r, g, b = img.getpixel((x, y))[:3]
            # green arrow-ish
            if g > 120 and g > r + 40 and g > b + 20:
                hits.append((x, y))
    if not hits:
        return []
    # cluster by proximity
    clusters: list[list[tuple[int, int]]] = []
    for x, y in hits:
        placed = False
        for c in clusters:
            cx, cy = c[0]
            if abs(cx - x) < 40 and abs(cy - y) < 20:
                c.append((x, y))
                placed = True
                break
        if not placed:
            clusters.append([(x, y)])
    centers = []
    for c in clusters:
        if len(c) < 8:
            continue
        xs = [p[0] for p in c]
        ys = [p[1] for p in c]
        centers.append((sum(xs) // len(xs), sum(ys) // len(ys), len(c)))
    centers.sort(key=lambda t: t[0])
    return centers


def main() -> int:
    frame = find_frame()
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.3)
    fr = frame.rectangle()

    # band covering filter + action links + table header
    keep = None
    date = None
    for c in frame.descendants():
        try:
            n = (c.element_info.name or "").strip()
        except Exception:
            continue
        if n == "保留筛选":
            keep = c.rectangle()
        if n == "持仓日期从":
            date = c.rectangle()
    print("keep", keep, "date", date)

    top = min(date.top if date else fr.top + 100, keep.top if keep else fr.top + 100) - 10
    bot = (keep.bottom if keep else top + 80) + 80
    bbox = (fr.left, top, fr.right, bot)
    band = ImageGrab.grab(bbox=bbox)
    band.save(OUT / "locate_band.png")
    print("band", bbox)

    centers = find_green_icons(band)
    print("green clusters:", centers)

    draw = ImageDraw.Draw(band)
    for x, y, n in centers:
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), outline=(255, 0, 0), width=2)
        draw.text((x + 8, y - 8), str(n), fill=(255, 0, 0))
    band.save(OUT / "locate_band_marked.png")

    # Also find blue-ish text links row by looking for saturated blue pixels in lower half
    blue_hits = []
    w, h = band.size
    for y in range(h // 2, h):
        for x in range(0, min(w, 800)):
            r, g, b = band.getpixel((x, y))[:3]
            if b > 130 and b > r + 30 and b > g + 10:
                blue_hits.append((x, y))
    if blue_hits:
        by = sorted(set(y for _, y in blue_hits))
        # densest y
        from collections import Counter

        yc = Counter(y for _, y in blue_hits)
        best_y = yc.most_common(1)[0][0]
        xs = [x for x, y in blue_hits if abs(y - best_y) <= 3]
        print(f"blue text row y={best_y} x_range={min(xs)}..{max(xs)} count={len(xs)}")
        # split into link segments by gaps
        xs.sort()
        segs = []
        start = xs[0]
        prev = xs[0]
        for x in xs[1:]:
            if x - prev > 15:
                segs.append((start, prev))
                start = x
            prev = x
        segs.append((start, prev))
        print("blue segments:", segs)
        # second segment is likely Excel批量导入 (first=模板下载)
        for i, (a, b) in enumerate(segs):
            cx = bbox[0] + (a + b) // 2
            cy = bbox[1] + best_y
            print(f"segment[{i}] center screen=({cx},{cy})")

        if len(segs) >= 2:
            a, b = segs[1]
            cx = bbox[0] + (a + b) // 2
            cy = bbox[1] + best_y
            print(f"CLICK Excel批量导入 candidate ({cx},{cy})")
            print("windows before:", dialogs())
            mouse.click(coords=(cx, cy))
            time.sleep(1.5)
            after = dialogs()
            print("windows after:", after)
            # any new dialog?
            ImageGrab.grab(bbox=(fr.left, fr.top, fr.right, fr.bottom)).save(OUT / "after_excel_click.png")
            for t, cls, r in after:
                if "期货" in t or "导入" in t or cls == "SunAwtDialog" or cls == "#32770":
                    print("FOUND", t, cls, r)
                    ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom)).save(
                        OUT / "import_dialog_opened.png"
                    )
                    ImageGrab.grab(bbox=(cx - 80, cy - 14, cx + 80, cy + 14)).save(
                        OUT / "tpl_excel_batch_import.png"
                    )
                    return 0
            # also check all SunAwtDialog even if title empty
            for w in Desktop(backend="win32").windows(class_name="SunAwtDialog"):
                t = w.window_text() or ""
                r = w.rectangle()
                print("SunAwtDialog", repr(t), r)
                if r.width() > 100 and r.height() > 100:
                    ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom)).save(
                        OUT / "import_dialog_opened.png"
                    )
                    return 0
            print("no dialog detected")
            return 1

    print("no blue segments")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
