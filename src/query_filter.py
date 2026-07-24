# -*- coding: utf-8 -*-
"""导入完成后按账单日筛选并查询 ERP 列表。"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageGrab
from pywinauto import keyboard, mouse

from bill_date import previous_workday, read_bill_date
from erp import focus_frame
from import_dialog import set_clipboard_text
from ocr_util import OcrHit, find_best_hit, normalize_text, ocr_image


@dataclass(frozen=True)
class FilterProfile:
    """不同 ERP 模块的日期筛选标签。"""

    kind: str
    start_labels: tuple[str, ...]


POSITION_FILTER = FilterProfile(kind="position", start_labels=("持仓日期从",))
TRADE_FILTER = FilterProfile(kind="trade", start_labels=("交易日期从", "交易日从"))


def profile_for_module(module: str) -> FilterProfile:
    """返回模块对应的筛选界面配置。"""
    profiles = {
        "position_rpa": POSITION_FILTER,
        "trade_rpa": TRADE_FILTER,
    }
    try:
        return profiles[module]
    except KeyError as exc:
        raise KeyError(f"不支持账单日筛选的模块: {module}") from exc


def _filter_band(frame) -> tuple[tuple[int, int, int, int], list[OcrHit]]:
    """识别主窗口顶部的筛选区。

    持仓界面「查询」在筛选行最右侧（靠近窗口右缘），成交界面也在条件区下方；
    带宽必须覆盖整窗宽度，不能裁成 left+1100。
    """
    rect = frame.rectangle()
    box = (
        rect.left,
        rect.top + 45,
        rect.right - 8,
        min(rect.bottom, rect.top + 360),
    )
    return box, ocr_image(ImageGrab.grab(bbox=box))


def _same_row(left: OcrHit, right: OcrHit) -> bool:
    return abs(left.center[1] - right.center[1]) <= max(
        20, left.bottom - left.top, right.bottom - right.top
    )


def _find_start(hits: list[OcrHit], profile: FilterProfile) -> OcrHit | None:
    for label in profile.start_labels:
        hit = find_best_hit(hits, label)
        if hit is not None:
            return hit
    return None


def _find_query(hits: list[OcrHit]) -> OcrHit | None:
    return find_best_hit(hits, "查询")


def _absolute_center(box: tuple[int, int, int, int], hit: OcrHit) -> tuple[int, int]:
    return box[0] + hit.center[0], box[1] + hit.center[1]


def _date_hits(hits: list[OcrHit]) -> list[OcrHit]:
    """只接受 OCR 已明确识别为日期的文本，避免误清除其他输入框。"""
    pattern = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$")
    return [hit for hit in hits if pattern.match(hit.text.strip())]


def _paste_date(point: tuple[int, int], bill_date: str) -> None:
    mouse.click(coords=point)
    time.sleep(0.15)
    keyboard.send_keys("^a")
    set_clipboard_text(bill_date)
    keyboard.send_keys("^v")
    time.sleep(0.35)


def _clear_field(point: tuple[int, int]) -> None:
    mouse.click(coords=point)
    time.sleep(0.1)
    keyboard.send_keys("^a")
    keyboard.send_keys("{DELETE}")
    time.sleep(0.2)


def filter_by_bill_date(module: str, bill_date: str) -> None:
    """填写起始账单日，保持结束日期为空，并点击「查询」。"""
    profile = profile_for_module(module)
    frame = focus_frame()
    box, hits = _filter_band(frame)
    start = _find_start(hits, profile)
    query = _find_query(hits)

    # 过滤条件可能折叠；依次尝试工具栏的已验证候选位置。
    if start is None or query is None:
        rect = frame.rectangle()
        for dx in (400, 430, 460, 490, 520, 370, 550):
            mouse.click(coords=(rect.left + dx, rect.top + 70))
            time.sleep(0.45)
            box, hits = _filter_band(frame)
            start = _find_start(hits, profile)
            query = _find_query(hits)
            if start is not None and query is not None:
                break

    if start is None or query is None:
        raise RuntimeError(f"未找到筛选条件或「查询」按钮: module={module}")

    # 「到」与起始标签同一行时，限定起始日期 OCR 命中在二者之间。
    end_label = min(
        (
            hit
            for hit in hits
            if normalize_text(hit.text) == "到"
            and hit.left > start.right
            and _same_row(start, hit)
        ),
        key=lambda hit: hit.left,
        default=None,
    )
    dates = _date_hits(hits)
    start_dates = [
        hit
        for hit in dates
        if hit.left >= start.right
        and _same_row(start, hit)
        and (end_label is None or hit.right <= end_label.left)
    ]
    if start_dates:
        start_point = _absolute_center(box, min(start_dates, key=lambda hit: hit.left))
    else:
        # 空输入框通常没有 OCR 文字，点击标签右侧的输入框位置。
        start_point = (box[0] + start.right + 55, box[1] + start.center[1])
    _paste_date(start_point, bill_date)

    # 若 ERP 默认保留了结束日期，明确清空；没有 OCR 日期时不碰该字段。
    if end_label is not None:
        end_dates = [
            hit
            for hit in dates
            if hit.left >= end_label.right and _same_row(end_label, hit)
        ]
        if end_dates:
            _clear_field(_absolute_center(box, min(end_dates, key=lambda hit: hit.left)))

    # 重新识别后再点击查询，避免筛选区布局因填值发生偏移。
    time.sleep(0.3)
    box, hits = _filter_band(frame)
    query = _find_query(hits)
    if query is None:
        raise RuntimeError("填写账单日后未找到「查询」按钮")
    mouse.click(coords=_absolute_center(box, query))
    time.sleep(0.5)
    print(f"queried {profile.kind} from date {bill_date}")


def after_import_query(module: str, excel_path: Path | str) -> str:
    """
    从 Excel 读账单日，用「前一工作日」作为查询起始日（终止日留空）。
    返回实际填入的查询起始日 YYYY-MM-DD。
    """
    bill_date = read_bill_date(Path(excel_path))
    query_date = previous_workday(bill_date)
    print(f"bill_date={bill_date} query_from={query_date} (previous workday)")
    filter_by_bill_date(module, query_date)
    return query_date
