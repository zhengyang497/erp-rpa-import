# -*- coding: utf-8 -*-
"""四类导入流程编排。

公共步骤（四条完全一致）：
  关旧导入框 →（可选）开模块 → 切页签 → Excel批量导入 → 粘贴/检查/导入/关窗

仅差异：
  - flow.module / open_module      —— 菜单
  - flow.tab / flow.tab_needle     —— 页签
  - flow.filename / resolve_file   —— 账单地址
"""
from __future__ import annotations

import time
from pathlib import Path

from config import FLOWS, ImportFlow, resolve_file
from import_dialog import (
    click_excel_batch_import,
    close_import_dialog,
    find_import_dialog,
    run_dialog_import,
)
from menu_nav import open_module
from tabs import switch_tab


def run_flow(
    flow: ImportFlow | str,
    *,
    output_dir: Path | None = None,
    skip_menu: bool = False,
    file_path: Path | None = None,
    wait_check: float = 60.0,
    wait_import: float = 60.0,
) -> Path:
    if isinstance(flow, str):
        if flow not in FLOWS:
            raise KeyError(f"未知流程: {flow}; 可选 {list(FLOWS)}")
        flow = FLOWS[flow]

    path = file_path or resolve_file(flow, output_dir)
    print(f"=== {flow.name} ({flow.key}) ===")
    print(f"module={flow.module} tab={flow.tab}")
    print(f"file: {path}")

    # 不复用旧对话框，避免带着上一条链路的上下文
    if find_import_dialog()[0] is not None:
        print("关闭已打开的导入对话框…")
        close_import_dialog()

    if not skip_menu:
        open_module(flow.module)
        time.sleep(1.5)

    switch_tab(flow.tab, tab_needle=flow.tab_needle)
    time.sleep(1.0)

    ok = click_excel_batch_import(timeout=15.0)
    if not ok:
        print("Excel批量导入 first try failed, retry once...")
        time.sleep(1.0)
        ok = click_excel_batch_import(timeout=15.0)
    if not ok:
        raise RuntimeError("无法打开导入对话框")

    run_dialog_import(path, wait_check=wait_check, wait_import=wait_import)
    return path
