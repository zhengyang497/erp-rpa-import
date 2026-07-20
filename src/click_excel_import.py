# -*- coding: utf-8 -*-
"""
在已打开的「境外与场外衍生品持仓明细（RPA）」模块中，
点击「Excel批量导入」，打开「境外场外期货」对话框。

工具栏链接对 win32 不可见：在过滤行下方扫描黄色图标，点击第 2 个
（第 1 个是「Excel导入模板下载」，第 2 个是「Excel批量导入」）。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from PIL import Image, ImageGrab
from pywinauto import Desktop, mouse

OUT = Path(__file__).resolve().parent
DIALOG_TITLE = "境外场外期货"


def find_frame():
    frames = Desktop(backend="win32").windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        raise RuntimeError("未找到 ERP 主窗口")
    return frames[0]


def find_named_rect(frame, name: str):
    for c in frame.descendants():
        try:
            n = (c.element_info.name or "").strip()
        except Exception:
            continue
        if n == name:
            return c.rectangle()
    return None


def list_import_dialogs():
    out = []
    for w in Desktop(backend="win32").windows(class_name="SunAwtDialog", visible_only=False):
        try:
            t = w.window_text() or ""
            r = w.rectangle()
        except Exception:
            continue
        if DIALOG_TITLE in t and r.width() > 200 and r.height() > 200:
            out.append((t, r, w.handle))
    return out


def yellow_icon_centers(img: Image.Image) -> list[tuple[int, int]]:
    """相对坐标：过滤行下方工具链接上的黄色小图标中心。"""
    pts = []
    for y in range(img.height):
        for x in range(min(img.width, 800)):
            r, g, b = img.getpixel((x, y))[:3]
            if r > 200 and g > 180 and b < 120 and r > b + 40:
                pts.append((x, y))
    if not pts:
        return []
    pts.sort()
    clusters: list[list[tuple[int, int]]] = []
    cur = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - cur[-1][0]) <= 25 and abs(p[1] - cur[-1][1]) <= 15:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    centers = []
    for c in clusters:
        if len(c) < 5:
            continue
        xs = [p[0] for p in c]
        ys = [p[1] for p in c]
        centers.append((sum(xs) // len(xs), sum(ys) // len(ys)))
    centers.sort(key=lambda t: t[0])
    return centers


def click_excel_batch_import(*, timeout: float = 8.0, icon_index: int = 1) -> bool:
    """
    icon_index: 0=模板下载, 1=批量导入, 2=分析模板(若同色)
    """
    frame = find_frame()
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.25)

    if list_import_dialogs():
        print("import dialog already open")
        return True

    date = find_named_rect(frame, "持仓日期从")
    keep = find_named_rect(frame, "保留筛选")
    fr = frame.rectangle()
    if date is None and keep is None:
        raise RuntimeError("未找到过滤行锚点，请先打开持仓明细（RPA）模块")

    top = (date.top if date else keep.top) - 5
    bot = (keep.bottom if keep else date.bottom) + 90
    bbox = (fr.left, top, fr.right, bot)
    band = ImageGrab.grab(bbox=bbox)
    band.save(OUT / "action_band_live.png")

    centers = yellow_icon_centers(band)
    print(f"yellow icons (rel): {centers}")
    if len(centers) <= icon_index:
        raise RuntimeError(f"只找到 {len(centers)} 个黄图标，无法点第 {icon_index + 1} 个")

    rx, ry = centers[icon_index]
    cx, cy = bbox[0] + rx, bbox[1] + ry
    print(f"click Excel批量导入 icon at ({cx},{cy})")
    mouse.click(coords=(cx, cy))

    deadline = time.time() + timeout
    while time.time() < deadline:
        ds = list_import_dialogs()
        if ds:
            t, r, h = ds[0]
            print(f"OK dialog {t!r} hwnd={h} rect={r}")
            ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom)).save(
                OUT / "import_dialog_opened.png"
            )
            ImageGrab.grab(bbox=(cx - 70, cy - 12, cx + 90, cy + 12)).save(
                OUT / "tpl_excel_batch_import.png"
            )
            return True
        time.sleep(0.25)

    print("FAILED: dialog not opened")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="点击 Excel批量导入，打开境外场外期货对话框")
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()
    return 0 if click_excel_batch_import(timeout=args.timeout) else 1


if __name__ == "__main__":
    raise SystemExit(main())
