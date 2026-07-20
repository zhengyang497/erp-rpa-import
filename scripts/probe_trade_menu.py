# -*- coding: utf-8 -*-
"""探测：期货管理 → 境外&场外衍生品 → 成交数据 子菜单。"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop, keyboard, mouse

OUT = Path(__file__).resolve().parent
FUTURES_MENU_INDEX = 4
# 境外&场外衍生品 = 第 21 项（此前探测）
OTC_DERIV_DOWN = 21
# 子菜单：成交数据 / 持仓数据 / 资金数据 — 成交数据为第 1 项（RIGHT 后默认）
# 再 RIGHT 展开成交数据下级


def find_frame():
    frames = Desktop(backend="win32").windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        frames = Desktop(backend="win32").windows(class_name="SunAwtFrame", visible_only=False)
    if not frames:
        raise RuntimeError("no ERP frame")
    return frames[0]


def click_futures(frame):
    # 用 UIA 菜单栏（若可见）；否则按窗口相对坐标点「期货管理」
    fr = frame.rectangle()
    try:
        uia = Desktop(backend="uia").window(handle=frame.handle)
        menubar = None
        for c in uia.children():
            info = c.element_info
            if getattr(info, "control_type", None) == "MenuBar" or (info.name or "") == "应用程序":
                menubar = c
                break
        if menubar is not None:
            items = list(menubar.children())
            tr = items[FUTURES_MENU_INDEX].rectangle()
            cx, cy = (tr.left + tr.right) // 2, (tr.top + tr.bottom) // 2
        else:
            raise RuntimeError("no menubar")
    except Exception:
        # 回退：菜单栏约在标题下，期货管理是第 5 项（约 x 偏移）
        cx = fr.left + 262  # 约等于此前 (478-215)=263
        cy = fr.top + 40
    mouse.click(coords=((fr.left + fr.right) // 2, fr.top + 120))
    time.sleep(0.15)
    mouse.click(coords=(cx, cy))
    time.sleep(0.35)


def main():
    frame = find_frame()
    try:
        frame.restore()
    except Exception:
        pass
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.35)
    fr = frame.rectangle()
    wide = (fr.left + 180, fr.top + 40, min(fr.right - 20, fr.left + 1100), fr.bottom - 40)

    click_futures(frame)
    for _ in range(OTC_DERIV_DOWN):
        keyboard.send_keys("{DOWN}")
        time.sleep(0.07)
    ImageGrab.grab(bbox=wide).save(OUT / "trade_probe_01_otc.png")

    keyboard.send_keys("{RIGHT}")
    time.sleep(0.35)
    ImageGrab.grab(bbox=wide).save(OUT / "trade_probe_02_otc_sub.png")
    # 默认在「成交数据」(第1项)，再 RIGHT
    keyboard.send_keys("{RIGHT}")
    time.sleep(0.4)
    ImageGrab.grab(bbox=wide).save(OUT / "trade_probe_03_trade_data.png")

    # DOWN 若干拍下级项
    for i in range(1, 8):
        keyboard.send_keys("{DOWN}")
        time.sleep(0.12)
        ImageGrab.grab(bbox=wide).save(OUT / f"trade_probe_down_{i:02d}.png")

    keyboard.send_keys("{ESC}{ESC}{ESC}")
    print("saved trade_probe_*.png")


if __name__ == "__main__":
    main()
