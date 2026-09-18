# -*- coding: utf-8 -*-
"""路径与导入映射（option-margin v2/v3 + 商品价格指数）。

共用同一套：打开导入 → 粘贴 → 检查 → 导入 → 关窗。
仅以下按流程不同：
  - module：主菜单进哪个模块
  - tab / tab_needle：模块内页签
  - filename / output_folder：Excel 路径
  - open_import / query_after / close_tab_after
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_output_dir(folder: str) -> Path:
    """账单目录：环境变量 > 同级 option-margin/<folder> > 本仓库 <folder>。"""
    env = os.environ.get("ERP_RPA_OUTPUT_DIR")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parent.parent
    sibling = root.parent / "option-margin" / folder
    if sibling.is_dir():
        return sibling
    return root / folder


def _default_output_v2() -> Path:
    return _default_output_dir("output_v2")


def _default_output_v3() -> Path:
    return _default_output_dir("output_v3")


# 默认读 v2 输出目录（可用 ERP_RPA_OUTPUT_DIR 或 --output-dir 覆盖）
DEFAULT_OUTPUT_V2 = _default_output_v2()
DEFAULT_OUTPUT_V3 = _default_output_v3()
DEFAULT_PRICE_DIR = Path(os.environ.get("ERP_RPA_PRICE_DIR", r"E:\RPA\价格导入"))


@dataclass(frozen=True)
class ImportFlow:
    key: str
    name: str
    filename: str
    # position_rpa | trade_rpa | fund_rpa | price_rpa  —— 菜单
    module: str
    # futures_swap | option | fund | price  —— 页签语义
    tab: str
    # 文档子签 OCR 目标文案
    tab_needle: str
    # option-margin 输出子目录：output_v2 / output_v3；price = DEFAULT_PRICE_DIR
    output_folder: str = "output_v2"
    # excel_batch = Excel批量导入；template = 模板导入
    open_import: str = "excel_batch"
    query_after: bool = True
    close_tab_after: bool = False


FLOWS: dict[str, ImportFlow] = {
    "option_position": ImportFlow(
        key="option_position",
        name="期权持仓",
        filename="期权持仓导入模板.xlsx",
        module="position_rpa",
        tab="option",
        tab_needle="境外与场外衍生品持仓明细（RPA）-期权",
    ),
    "option_trade": ImportFlow(
        key="option_trade",
        name="期权成交",
        filename="外盘期权成交明细模板.xlsx",
        module="trade_rpa",
        tab="option",
        # 成交模块子签实测短名；完整名 OCR 不稳定时走 tabs 短名回退
        tab_needle="期权成交明细",
    ),
    "merged_position": ImportFlow(
        key="merged_position",
        name="期货掉期持仓",
        filename="期货与掉期持仓导入模板.xlsx",
        module="position_rpa",
        tab="futures_swap",
        tab_needle="境外与场外衍生品持仓明细（RPA）-期货与掉期",
    ),
    "merged_trade": ImportFlow(
        key="merged_trade",
        name="期货掉期远期成交",
        filename="期货、掉期、远期成交导入模板.xlsx",
        module="trade_rpa",
        tab="futures_swap",
        tab_needle="商品衍生品",
    ),
    "fund_detail": ImportFlow(
        key="fund_detail",
        name="境外场外资金明细",
        filename="境外场外资金情况导入模板.xlsx",
        module="fund_rpa",
        tab="fund",
        tab_needle="境外场外资金情况",
        output_folder="output_v3",
    ),
    "price_index": ImportFlow(
        key="price_index",
        name="商品价格指数",
        filename="NEW.xlsx",
        module="price_rpa",
        tab="price",
        tab_needle="商品指数登记",
        output_folder="price",
        open_import="template",
        query_after=False,
        close_tab_after=True,
    ),
}


def resolve_file(flow: ImportFlow, output_dir: Path | None = None) -> Path:
    if output_dir is not None:
        root = output_dir
    elif flow.output_folder == "output_v3":
        root = DEFAULT_OUTPUT_V3
    elif flow.output_folder == "price":
        root = DEFAULT_PRICE_DIR
    else:
        root = DEFAULT_OUTPUT_V2
    path = root / flow.filename
    if not path.is_file():
        raise FileNotFoundError(f"找不到输出文件: {path}")
    return path.resolve()
