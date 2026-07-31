# -*- coding: utf-8 -*-
"""路径与四类导入映射（对应 option-margin v2 四份输出）。

四条链路共用同一套：Excel批量导入 → 粘贴 → 检查 → 导入 → 关窗。
仅以下三项按流程不同：
  - module：主菜单进哪个模块
  - tab / tab_needle：模块内页签
  - filename：V2 账单 Excel 路径
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_output_v2() -> Path:
    """V2 账单目录：环境变量 > 同级 option-margin/output_v2 > 本仓库 output_v2。"""
    env = os.environ.get("ERP_RPA_OUTPUT_DIR")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parent.parent
    sibling = root.parent / "option-margin" / "output_v2"
    if sibling.is_dir():
        return sibling
    return root / "output_v2"


# 默认读 v2 输出目录（可用 ERP_RPA_OUTPUT_DIR 或 --output-dir 覆盖）
DEFAULT_OUTPUT_V2 = _default_output_v2()


@dataclass(frozen=True)
class ImportFlow:
    key: str
    name: str
    filename: str
    # position_rpa | trade_rpa  —— 菜单
    module: str
    # futures_swap | option  —— 页签语义
    tab: str
    # 文档子签 OCR 目标文案
    tab_needle: str


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
}


def resolve_file(flow: ImportFlow, output_dir: Path | None = None) -> Path:
    root = output_dir or DEFAULT_OUTPUT_V2
    path = root / flow.filename
    if not path.is_file():
        raise FileNotFoundError(f"找不到 V2 输出文件: {path}")
    return path.resolve()
