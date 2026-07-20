# -*- coding: utf-8 -*-
"""
从主菜单深入：期货管理 → 展开「境外&场外衍生品」/「境外场外持仓管理」子菜单并截图。
用键盘 Down/Right 导航（不依赖控件名）。
"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop, keyboard, mouse

OUT = Path(__file__).resolve().parent
REPORT = OUT / "probe_submenu_path.txt"


def find_frame():
    desk = Desktop(backend="uia")
    frames = desk.windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        raise RuntimeError("未找到 ERP 主窗口")
    return frames[0]


def find_menubar(frame):
    for c in frame.children():
        info = c.element_info
        if getattr(info, "control_type", None) == "MenuBar" or (info.name or "") == "应用程序":
            return c
    raise RuntimeError("未找到菜单栏")


def click_futures_menu(frame) -> tuple[int, int]:
    menubar = find_menubar(frame)
    items = list(menubar.children())
    # OCR 顺序：0系统 … 4期货管理
    target = items[4]
    tr = target.rectangle()
    cx, cy = (tr.left + tr.right) // 2, (tr.top + tr.bottom) // 2
    fr = frame.rectangle()
    mouse.click(coords=((fr.left + fr.right) // 2, fr.top + 120))
    time.sleep(0.15)
    mouse.click(coords=(cx, cy))
    time.sleep(0.35)
    return cx, cy


def grab(name: str, bbox) -> Path:
    p = OUT / name
    ImageGrab.grab(bbox=bbox).save(p)
    return p


def main() -> None:
    lines: list[str] = []
    frame = find_frame()
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.25)
    fr = frame.rectangle()

    # 区域：左侧下拉 + 右侧可能出现的级联菜单
    wide = (fr.left + 200, fr.top + 45, fr.left + 900, fr.bottom - 40)

    cx, cy = click_futures_menu(frame)
    lines.append(f"clicked 期货管理 at ({cx},{cy})")
    grab("path_00_futures_open.png", wide)

    # 向下移动到接近列表底部（境外相关项在靠下位置）
    # 先截一张完整下拉（加高）
    drop = (cx - 40, cy + 10, cx + 380, min(fr.bottom - 20, cy + 10 + 560))
    grab("path_01_full_dropdown.png", drop)

    # 键盘：从首项一路 Down，每几步截图；在疑似目标附近 Right 展开
    # Swing 菜单通常在打开后焦点已在首项
    for i in range(1, 28):
        keyboard.send_keys("{DOWN}")
        time.sleep(0.12)
        if i in (1, 5, 10, 15, 18, 20, 21, 22, 23, 24, 25):
            grab(f"path_down_{i:02d}.png", wide)
            lines.append(f"DOWN x{i} shot path_down_{i:02d}.png")

    # 在当前位置试 Right 展开子菜单（假设已停在境外相关项附近）
    # 重新打开菜单，精确定位：先 Down 到第 21 项左右再 Right
    click_futures_menu(frame)
    time.sleep(0.2)
    for _ in range(21):
        keyboard.send_keys("{DOWN}")
        time.sleep(0.08)
    grab("path_at_item21.png", wide)
    keyboard.send_keys("{RIGHT}")
    time.sleep(0.4)
    grab("path_item21_right.png", wide)
    lines.append("at item21 + RIGHT -> path_item21_right.png")

    # 再试第 24 项（境外场外持仓管理约在此）
    click_futures_menu(frame)
    time.sleep(0.2)
    for _ in range(24):
        keyboard.send_keys("{DOWN}")
        time.sleep(0.08)
    grab("path_at_item24.png", wide)
    keyboard.send_keys("{RIGHT}")
    time.sleep(0.4)
    grab("path_item24_right.png", wide)
    lines.append("at item24 + RIGHT -> path_item24_right.png")

    # Esc 收起，避免挡住界面
    keyboard.send_keys("{ESC}")
    time.sleep(0.1)
    keyboard.send_keys("{ESC}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")
    print("Review path_*.png under scripts/")


if __name__ == "__main__":
    main()
