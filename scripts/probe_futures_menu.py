# -*- coding: utf-8 -*-
"""
从 ERP 主菜单开始探测：点击「期货管理」，截取下拉菜单。
不做导入对话框内操作。
"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop
from pywinauto import mouse

OUT = Path(__file__).resolve().parent
REPORT = OUT / "probe_futures_menu.txt"
SHOT_BEFORE = OUT / "menu_before_futures.png"
SHOT_AFTER = OUT / "menu_after_futures_click.png"
SHOT_DROP = OUT / "futures_dropdown.png"


def find_frame():
    desk = Desktop(backend="uia")
    frames = desk.windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        raise RuntimeError("未找到 ERP 主窗口 SunAwtFrame")
    return frames[0]


def find_menubar(frame):
    for c in frame.children():
        info = c.element_info
        if getattr(info, "control_type", None) == "MenuBar" or (info.name or "") == "应用程序":
            return c
    raise RuntimeError("未找到应用程序菜单栏")


def main() -> None:
    lines: list[str] = []
    frame = find_frame()
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.3)

    menubar = find_menubar(frame)
    items = list(menubar.children())
    lines.append(f"frame={frame.window_text()!r}")
    lines.append(f"menubar_rect={menubar.rectangle()}")
    lines.append(f"menu_item_count={len(items)}")

    # 根据此前 OCR：index 4 = 期货管理（系统=0 … 期货管理=4）
    TARGET_INDEX = 4
    if TARGET_INDEX >= len(items):
        raise RuntimeError(f"菜单项不足: {len(items)}")

    target = items[TARGET_INDEX]
    tr = target.rectangle()
    cx, cy = (tr.left + tr.right) // 2, (tr.top + tr.bottom) // 2
    lines.append(f"target_index={TARGET_INDEX} rect={tr} click=({cx},{cy})")

    fr = frame.rectangle()
    ImageGrab.grab(bbox=(fr.left, fr.top, fr.right, fr.top + 80)).save(SHOT_BEFORE)

    # 先点一下空白客户区关掉可能已开的菜单，再点期货管理
    mouse.click(coords=((fr.left + fr.right) // 2, fr.top + 120))
    time.sleep(0.2)
    mouse.click(coords=(cx, cy))
    time.sleep(0.5)

    ImageGrab.grab(bbox=(fr.left, fr.top, fr.right, fr.top + 80)).save(SHOT_AFTER)
    # 下拉区域：菜单正下方一大块
    drop_bbox = (tr.left - 20, tr.bottom, tr.left + 420, tr.bottom + 520)
    ImageGrab.grab(bbox=drop_bbox).save(SHOT_DROP)
    lines.append(f"saved {SHOT_BEFORE.name}, {SHOT_AFTER.name}, {SHOT_DROP.name}")
    lines.append(f"dropdown_bbox={drop_bbox}")

    # 点开后扫描是否出现新的 SunAwtWindow（Swing 弹出菜单常是这种）
    desk_w = Desktop(backend="win32")
    lines.append("SunAwtWindow after click:")
    for w in desk_w.windows(class_name="SunAwtWindow", visible_only=True):
        try:
            r = w.rectangle()
            title = w.window_text() or ""
        except Exception as e:
            lines.append(f"  err {e}")
            continue
        if r.width() < 5 or r.height() < 5:
            continue
        lines.append(f"  hwnd={w.handle} title={title!r} rect={r}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
