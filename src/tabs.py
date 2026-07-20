# -*- coding: utf-8 -*-
"""模块内页签切换（四条链路共用；仅 OCR 目标文案不同）。"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import mouse

from erp import find_frame, focus_frame
from ocr_util import find_best_hit, normalize_text, ocr_image


def _tab_band(frame) -> tuple[int, int, int, int]:
    fr = frame.rectangle()
    return (fr.left + 5, fr.top + 40, min(fr.right, fr.left + 1200), fr.top + 170)


def _short_fallback(prefer: str, hits) -> object | None:
    """完整子签 OCR 失败时，按语义短名回退。"""
    short_hits = []
    for h in hits:
        nt = normalize_text(h.text)
        if prefer == "option":
            if "期权" in nt and (
                "持仓" in nt or "成交" in nt or "-" in h.text or "－" in h.text
            ):
                short_hits.append(h)
            elif nt.endswith("期权") or nt == "期权":
                short_hits.append(h)
        else:
            if ("期货" in nt and "掉期" in nt) or "商品衍生品" in nt:
                short_hits.append(h)
    if not short_hits:
        return None
    return max(short_hits, key=lambda x: len(x.text))


def _click_tab_by_blue_segments(prefer: str) -> bool:
    """回退：内容区顶部蓝色页签文字带（左=期货与掉期，右=期权）。"""
    frame = focus_frame()
    fr = frame.rectangle()
    top = fr.top + 55
    bot = fr.top + 120
    bbox = (fr.left + 10, top, fr.right - 10, bot)
    img = ImageGrab.grab(bbox=bbox)

    blue = []
    for y in range(img.height):
        for x in range(min(img.width, 900)):
            r, g, b = img.getpixel((x, y))[:3]
            if b > 140 and b > r + 25 and b > g + 10 and r < 140:
                blue.append((x, y))
    if not blue:
        return False

    from collections import Counter

    yc = Counter(y for _, y in blue)
    best_y = yc.most_common(1)[0][0]
    xs = sorted(x for x, y in blue if abs(y - best_y) <= 4)
    if not xs:
        return False

    segs = []
    start = prev = xs[0]
    for x in xs[1:]:
        if x - prev > 20:
            if prev - start > 30:
                segs.append((start, prev))
            start = x
        prev = x
    if prev - start > 30:
        segs.append((start, prev))

    if len(segs) < 2:
        x = fr.left + (420 if prefer == "option" else 220)
        mouse.click(coords=(x, top + (bot - top) // 2))
        time.sleep(0.5)
        return True

    idx = min(1 if prefer == "option" else 0, len(segs) - 1)
    a, b = segs[idx]
    mouse.click(coords=(bbox[0] + (a + b) // 2, bbox[1] + best_y))
    time.sleep(0.6)
    return True


def switch_tab(tab: str, *, tab_needle: str | None = None) -> None:
    """
    tab: futures_swap | option
    tab_needle: 优先 OCR 的完整子签文案（各流程在 config 里配置）
    """
    if tab not in ("futures_swap", "option"):
        raise ValueError(tab)

    frame = focus_frame()
    bbox = _tab_band(frame)
    img = ImageGrab.grab(bbox=bbox)
    img.save(Path(__file__).with_name("debug_tabs_switch.png"))
    hits = ocr_image(img)

    hit = None
    if tab_needle:
        hit = find_best_hit(hits, tab_needle, min_score=80.0)
    if hit is None:
        hit = _short_fallback(tab, hits)

    if hit is not None:
        cx, cy = hit.center
        abs_pos = (bbox[0] + cx, bbox[1] + cy)
        print(f"tab OCR click {tab} via {hit.text!r} at {abs_pos} conf={hit.conf:.2f}")
        mouse.click(coords=abs_pos)
        time.sleep(0.7)
        return

    if _click_tab_by_blue_segments(tab):
        print(f"tab blue-segment fallback for {tab}")
        return

    fr = find_frame().rectangle()
    x = fr.left + (420 if tab == "option" else 220)
    y = fr.top + 88
    print(f"tab fixed-offset fallback for {tab} at {(x, y)}")
    mouse.click(coords=(x, y))
    time.sleep(0.6)
