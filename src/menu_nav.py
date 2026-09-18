# -*- coding: utf-8 -*-
"""主菜单导航：顶栏下标 + 一级下拉实时 OCR；级联用相对偏移（无 OCR）。"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Desktop, keyboard, mouse

from erp import find_frame, focus_frame
from ocr_util import find_best_hit, ocr_image


# 顶栏：0系统 … 4期货管理 … 14基础信息（2026-08-19 逐项 OCR 实测）
FUTURES_MENU_INDEX = 4
PRICE_MENU_INDEX = 14

# 一级下拉（变动最大）——唯一实时 OCR
POSITION_DROPDOWN = "境外场外持仓管理"
TRADE_DROPDOWN = "境外＆场外衍生品"
PRICE_DROPDOWN = "经营单位商品"

# 级联相对一级下拉 OCR 命中点的屏幕偏移（实测，无实时 OCR）
# 成交：悬停父项后 → 成交数据 → 成交明细(RPA+手工)
TRADE_SUB_DX, TRADE_SUB_DY = 217, 0
TRADE_LEAF_DX, TRADE_LEAF_DY = 376, 21
# 持仓：悬停父项后 → 持仓明细(RPA)
POSITION_LEAF_DX, POSITION_LEAF_DY = 280, 41
# 资金：悬停父项后 → 资金数据 → 境外与场外衍生品资金明细
FUND_SUB_DX, FUND_SUB_DY = 217, 43
FUND_LEAF_DX, FUND_LEAF_DY = 340, 43
# 价格指数：悬停「经营单位商品」后 → 2、商品价格指数登记
PRICE_LEAF_DX, PRICE_LEAF_DY = 221, 177
PRICE_NAV_ATTEMPTS = 3
# 必须是页面上的可见控件。不要用「商品指数登记」（菜单/页签名，未打开也会在控件树里）。
_PRICE_SCREEN_NAMES = ("模板导入", "指数编码", "指数中文名称")
_BLOCKING_TAB_MARKERS = ("申请", "确认", "审批", "用章", "客商")
_PRICE_TAB_MARKERS = ("指数登记", "价格指数", "商品指数")


def _chrome_click_coords(frame) -> tuple[int, int]:
    """点标题栏聚焦，避免点进单据内容区盖住下拉。"""
    fr = frame.rectangle()
    return (fr.left + fr.right) // 2, fr.top + 8


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


def _price_drop_bbox(frame) -> tuple[int, int, int, int]:
    """基础信息下拉在顶栏右侧；限制扫描区避免审批页文字抢 OCR。"""
    fr = frame.rectangle()
    return (
        max(fr.left + 8, fr.right - 720),
        fr.top + 40,
        fr.right - 4,
        min(fr.bottom - 20, fr.top + 450),
    )


def _screen_center(bbox: tuple[int, int, int, int], hit) -> tuple[int, int]:
    cx, cy = hit.center
    return bbox[0] + cx, bbox[1] + cy


def _click_top_menu(frame, index: int) -> None:
    x, y = _chrome_click_coords(frame)
    mouse.click(coords=(x, y))
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
    if index >= len(items):
        raise RuntimeError(f"MenuBar 项数不足: {len(items)}，需要 index={index}")

    r = items[index].rectangle()
    x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    print(f"click top menu index={index} at ({x},{y})")
    mouse.click(coords=(x, y))
    time.sleep(0.35)


def _click_futures_menu(frame) -> None:
    _click_top_menu(frame, FUTURES_MENU_INDEX)


def _locate_dropdown_ocr(frame, text: str, *, retries: int = 4, bbox=None):
    """仅用于一级下拉。"""
    bbox = bbox or _menu_bbox(frame)
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


def _point_in_frame_content(frame, r) -> bool:
    """控件中心是否在主窗口内容区（排除标题栏/菜单幽灵项和屏外节点）。"""
    fr = frame.rectangle()
    width = r.right - r.left
    height = r.bottom - r.top
    x = r.left if width <= 1 else (r.left + r.right) // 2
    y = r.top if height <= 1 else (r.top + r.bottom) // 2
    return fr.left <= x <= fr.right and (fr.top + 50) <= y <= (fr.bottom - 10)


def _looks_like_price_screen(frame) -> bool:
    return any(_named_exists(frame, n, require_visible=True) for n in _PRICE_SCREEN_NAMES)


def _close_non_price_documents() -> None:
    """关掉挡住基础信息菜单的审批/申请页；点不到则 Ctrl+F4 关当前单据。"""
    from tabs import _tab_band

    frame = find_frame()
    if _looks_like_price_screen(frame):
        return
    bbox = _tab_band(frame)
    img = ImageGrab.grab(bbox=bbox)
    hits = ocr_image(img)
    for hit in hits:
        text = hit.text or ""
        if any(mark in text for mark in _PRICE_TAB_MARKERS):
            continue
        if not any(mark in text for mark in _BLOCKING_TAB_MARKERS):
            continue
        x = bbox[0] + hit.right + 12
        y = bbox[1] + hit.center[1]
        print(f"close blocking tab {text!r} at ({x},{y})")
        mouse.click(coords=(x, y))
        time.sleep(0.45)
        return
    if not _looks_like_price_screen(find_frame()):
        print("non-price screen: Ctrl+F4 close document, then 基础信息 → 经营单位商品")
        keyboard.send_keys("^{F4}")
        time.sleep(0.6)


def _prepare_price_menu() -> None:
    try:
        from import_dialog import (
            close_import_dialog,
            dismiss_post_import_popups,
            find_import_dialog,
        )

        dismiss_post_import_popups(timeout=2.0)
        if find_import_dialog()[0] is not None:
            close_import_dialog()
    except Exception as exc:
        print(f"price menu prepare dialogs: {exc}")
    _dismiss_menus()
    _close_non_price_documents()


def _hover_price_dropdown(frame) -> tuple[int, int]:
    last_exc: Exception | None = None
    for bbox in (_price_drop_bbox(frame), _menu_bbox(frame)):
        try:
            return _hover_dropdown_ocr(frame, PRICE_DROPDOWN, bbox=bbox)
        except RuntimeError as exc:
            last_exc = exc
            print(f"price dropdown miss, try next bbox: {exc}")
    assert last_exc is not None
    raise last_exc


def _hover_dropdown_ocr(frame, text: str, *, bbox=None) -> tuple[int, int]:
    hit, bbox = _locate_dropdown_ocr(frame, text, bbox=bbox)
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
            if _point_in_frame_content(frame, r):
                return True
        except Exception:
            continue
    return False


def _verify_opened(module: str, *, timeout: float = 10.0) -> None:
    """用 win32 锚点校验（轮询等待页面加载），不用 OCR。"""
    if module == "position_rpa":
        names = ("持仓日期从",)
        hint = "持仓日期从"
    elif module == "fund_rpa":
        names = ("日期从", "持仓日期从", "交易日从", "交易日期从")
        hint = "日期从"
    elif module == "price_rpa":
        names = ("模板导入", "指数编码", "指数中文名称")
        hint = "模板导入/指数编码"
    else:
        names = ("交易日从", "交易日期从", "持仓日期从")
        hint = "交易日从/交易日期从/持仓日期从"

    deadline = time.time() + timeout
    last_ok = False
    while time.time() < deadline:
        frame = find_frame()
        # 优先可见控件；再接受仅存在于树中的命名控件（Swing 常见）
        last_ok = any(_named_exists(frame, n, require_visible=True) for n in names)
        if module != "price_rpa" and not last_ok:
            # 持仓/成交等 Swing 页常见：锚点只在控件树里、矩形不可见
            last_ok = any(_named_exists(frame, n, require_visible=False) for n in names)
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


def open_fund_rpa_module(*, dry_run: bool = False, verify: bool = True) -> None:
    """
    顶栏点「期货管理」
    → OCR 悬停「境外&场外衍生品」
    → 相对偏移悬停资金数据 → 点击境外与场外衍生品资金明细
    """
    frame = focus_frame()
    _dismiss_menus()
    _click_futures_menu(frame)
    x, y = _hover_dropdown_ocr(frame, TRADE_DROPDOWN)
    sx, sy = x + FUND_SUB_DX, y + FUND_SUB_DY
    print(f"relative hover 资金数据 at ({sx},{sy})")
    mouse.move(coords=(sx, sy))
    time.sleep(0.45)
    lx, ly = x + FUND_LEAF_DX, y + FUND_LEAF_DY
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
        _verify_opened("fund_rpa", timeout=12.0)


def open_price_rpa_module(*, dry_run: bool = False, verify: bool = True) -> None:
    """
    顶栏点「基础信息」
    → OCR 悬停「经营单位商品」
    → 相对偏移点击「2、商品价格指数登记」
    若当前是审批/申请页，先关掉再切菜单（失败会重试）。
    """
    last_exc: Exception | None = None
    for attempt in range(1, PRICE_NAV_ATTEMPTS + 1):
        frame = focus_frame()
        _prepare_price_menu()
        frame = focus_frame()
        if _looks_like_price_screen(frame):
            print(f"already on 商品价格指数登记 (attempt {attempt})")
            if dry_run:
                return
            if verify:
                _verify_opened("price_rpa", timeout=4.0)
            return
        try:
            print(f"price menu navigate attempt {attempt}/{PRICE_NAV_ATTEMPTS}: 基础信息 → 经营单位商品")
            _click_top_menu(frame, PRICE_MENU_INDEX)
            x, y = _hover_price_dropdown(frame)
            lx, ly = x + PRICE_LEAF_DX, y + PRICE_LEAF_DY
            print(f"relative leaf click at ({lx},{ly}) dx={PRICE_LEAF_DX} dy={PRICE_LEAF_DY}")
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
                _verify_opened("price_rpa", timeout=12.0)
            return
        except Exception as exc:
            last_exc = exc
            print(f"price menu attempt {attempt} failed: {exc}")
            _dismiss_menus()
            time.sleep(0.4)
    raise last_exc if last_exc is not None else RuntimeError("打开商品价格指数登记失败")


def open_module(module: str, *, dry_run: bool = False, verify: bool = True) -> None:
    if module == "position_rpa":
        open_position_rpa_module(dry_run=dry_run, verify=verify)
    elif module == "trade_rpa":
        open_trade_rpa_module(dry_run=dry_run, verify=verify)
    elif module == "fund_rpa":
        open_fund_rpa_module(dry_run=dry_run, verify=verify)
    elif module == "price_rpa":
        open_price_rpa_module(dry_run=dry_run, verify=verify)
    else:
        raise ValueError(f"unknown module: {module}")
