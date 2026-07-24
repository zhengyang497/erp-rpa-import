# -*- coding: utf-8 -*-
"""主菜单导航：顶栏下标 + 一级下拉实时 OCR；级联用相对偏移（无 OCR）。"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop, keyboard, mouse

from erp import find_frame, focus_frame
from ocr_util import find_best_hit, ocr_image


# 顶栏：0系统 … 4期货管理
FUTURES_MENU_INDEX = 4

# 一级下拉（变动最大）——唯一实时 OCR
POSITION_DROPDOWN = "境外场外持仓管理"
TRADE_DROPDOWN = "境外＆场外衍生品"

# 级联相对一级下拉 OCR 命中点的屏幕偏移（实测，无实时 OCR）
# 成交：悬停父项后 → 成交数据 → 成交明细(RPA+手工)
TRADE_SUB_DX, TRADE_SUB_DY = 217, 0
TRADE_LEAF_DX, TRADE_LEAF_DY = 376, 21
# 持仓：悬停父项后 → 持仓明细(RPA)
POSITION_LEAF_DX, POSITION_LEAF_DY = 280, 41


def _dismiss_menus() -> None:
    keyboard.send_keys("{ESC}")
    time.sleep(0.08)
    keyboard.send_keys("{ESC}")
    time.sleep(0.08)
    keyboard.send_keys("{ESC}")
    time.sleep(0.15)


def _grab(bbox: tuple[int, int, int, int]):
    return ImageGrab.grab(bbox=bbox), bbox


def _menu_bbox(frame) -> tuple[int, int, int, int]:
    fr = frame.rectangle()
    return (
        fr.left + 8,
        fr.top + 45,
        min(fr.right - 8, fr.left + 1100),
        fr.bottom - 20,
    )


def _screen_center(bbox: tuple[int, int, int, int], hit) -> tuple[int, int]:
    cx, cy = hit.center
    return bbox[0] + cx, bbox[1] + cy


def _click_futures_menu(frame) -> None:
    fr = frame.rectangle()
    mouse.click(coords=((fr.left + fr.right) // 2, fr.top + 120))
    time.sleep(0.15)

    uia = Desktop(backend="uia").window(handle=frame.handle)
    menubar = None
    for c in uia.children():
        info = c.element_info
        if getattr(info, "control_type", None) == "MenuBar" or (info.name or "") == "应用程序":
            menubar = c
            break
    if menubar is None:
        raise RuntimeError("未找到顶栏 MenuBar")

    items = list(menubar.children())
    if FUTURES_MENU_INDEX >= len(items):
        raise RuntimeError(f"MenuBar 项数不足: {len(items)}，需要 index={FUTURES_MENU_INDEX}")

    r = items[FUTURES_MENU_INDEX].rectangle()
    x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    print(f"click top menu index={FUTURES_MENU_INDEX} at ({x},{y})")
    mouse.click(coords=(x, y))
    time.sleep(0.35)


def _locate_dropdown_ocr(frame, text: str, *, retries: int = 4):
    """仅用于期货管理一级下拉。"""
    bbox = _menu_bbox(frame)
    last_hits = []
    last_img = None
    for _ in range(retries):
        img, _ = _grab(bbox)
        last_img = img
        scaled = img.resize((img.width * 2, img.height * 2))
        hits = ocr_image(scaled)
        from ocr_util import OcrHit

        hits = [
            OcrHit(
                text=h.text,
                conf=h.conf,
                left=h.left // 2,
                top=h.top // 2,
                right=h.right // 2,
                bottom=h.bottom // 2,
            )
            for h in hits
        ]
        last_hits = hits
        hit = find_best_hit(hits, text)
        if hit is not None:
            return hit, bbox
        time.sleep(0.3)

    try:
        dbg = Path(__file__).with_name("ocr_menu_miss.png")
        if last_img is not None:
            last_img.save(dbg)
            print(f"saved debug shot: {dbg}")
    except Exception:
        pass
    raise RuntimeError(f"一级下拉 OCR 未找到: {text}; got={[h.text for h in last_hits[:40]]}")


def _hover_dropdown_ocr(frame, text: str) -> tuple[int, int]:
    hit, bbox = _locate_dropdown_ocr(frame, text)
    x, y = _screen_center(bbox, hit)
    print(f"OCR dropdown '{hit.text}' conf={hit.conf:.2f} at ({x},{y})")
    mouse.move(coords=(x, y))
    time.sleep(0.45)
    return x, y


def _named_exists(frame, name: str, *, require_visible: bool = False) -> bool:
    for c in frame.descendants():
        try:
            if (c.element_info.name or "").strip() != name:
                continue
            if not require_visible:
                return True
            r = c.rectangle()
            if (r.right - r.left) > 1 and (r.bottom - r.top) > 1:
                # 排除最小化到屏外的幽灵控件
                if r.left > -1000 and r.top > -1000:
                    return True
        except Exception:
            continue
    return False


def _verify_opened(module: str, *, timeout: float = 10.0) -> None:
    """用 win32 锚点校验（轮询等待页面加载），不用 OCR。"""
    if module == "position_rpa":
        names = ("持仓日期从",)
        hint = "持仓日期从"
    else:
        names = ("交易日从", "交易日期从", "持仓日期从")
        hint = "交易日从/交易日期从/持仓日期从"

    deadline = time.time() + timeout
    last_ok = False
    while time.time() < deadline:
        frame = find_frame()
        # 优先可见控件；再接受仅存在于树中的命名控件（Swing 常见）
        last_ok = any(_named_exists(frame, n, require_visible=True) for n in names) or any(
            _named_exists(frame, n, require_visible=False) for n in names
        )
        print(f"verify win32 anchor '{hint}': {last_ok}")
        if last_ok:
            return
        time.sleep(0.45)
    raise RuntimeError(f"打开后页面校验失败：未找到控件 {hint}（等了 {timeout:.0f}s）")


def open_position_rpa_module(*, dry_run: bool = False, verify: bool = True) -> None:
    """
    顶栏点「期货管理」
    → OCR 悬停「境外场外持仓管理」
    → 相对偏移点击持仓明细（RPA）
    """
    frame = focus_frame()
    _dismiss_menus()
    _click_futures_menu(frame)
    x, y = _hover_dropdown_ocr(frame, POSITION_DROPDOWN)
    lx, ly = x + POSITION_LEAF_DX, y + POSITION_LEAF_DY
    print(f"relative leaf click at ({lx},{ly}) dx={POSITION_LEAF_DX} dy={POSITION_LEAF_DY}")
    if dry_run:
        mouse.move(coords=(lx, ly))
        time.sleep(0.3)
        _dismiss_menus()
        return
    mouse.click(coords=(lx, ly))
    time.sleep(0.3)
    _dismiss_menus()
    time.sleep(1.5)
    if verify:
        _verify_opened("position_rpa", timeout=12.0)


def open_trade_rpa_module(*, dry_run: bool = False, verify: bool = True) -> None:
    """
    顶栏点「期货管理」
    → OCR 悬停「境外&场外衍生品」
    → 相对偏移悬停成交数据 → 点击成交明细（RPA+手工）
    """
    frame = focus_frame()
    _dismiss_menus()
    _click_futures_menu(frame)
    x, y = _hover_dropdown_ocr(frame, TRADE_DROPDOWN)
    sx, sy = x + TRADE_SUB_DX, y + TRADE_SUB_DY
    print(f"relative hover 成交数据 at ({sx},{sy})")
    mouse.move(coords=(sx, sy))
    time.sleep(0.45)
    lx, ly = x + TRADE_LEAF_DX, y + TRADE_LEAF_DY
    print(f"relative leaf click at ({lx},{ly})")
    if dry_run:
        mouse.move(coords=(lx, ly))
        time.sleep(0.3)
        _dismiss_menus()
        return
    mouse.click(coords=(lx, ly))
    time.sleep(0.3)
    _dismiss_menus()
    time.sleep(1.5)
    if verify:
        _verify_opened("trade_rpa", timeout=12.0)


def open_module(module: str, *, dry_run: bool = False, verify: bool = True) -> None:
    if module == "position_rpa":
        open_position_rpa_module(dry_run=dry_run, verify=verify)
    elif module == "trade_rpa":
        open_trade_rpa_module(dry_run=dry_run, verify=verify)
    else:
        raise ValueError(f"unknown module: {module}")
