# -*- coding: utf-8 -*-
"""四类导入流程编排。

公共步骤（四条完全一致）：
  关旧导入框 →（可选）开模块 → 切页签 → Excel批量导入 → 粘贴/检查/导入/关窗
  → 填起始日(账单日前一工作日)+查询（持仓用持仓日期从，成交用交易日期从）

仅差异：
  - flow.module / open_module      —— 菜单
  - flow.tab / flow.tab_needle     —— 页签
  - flow.filename / resolve_file   —— 账单地址
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from config import FLOWS, ImportFlow, resolve_file
from import_dialog import (
    click_excel_batch_import,
    close_import_dialog,
    find_import_dialog,
    run_dialog_import,
)
from menu_nav import open_module
from query_filter import after_import_query
from tabs import switch_tab


def cleanup_after_failure() -> None:
    """单条失败后尽量清掉导入框/菜单，方便下一条继续。"""
    try:
        if find_import_dialog()[0] is not None:
            close_import_dialog()
    except Exception:
        pass
    try:
        from menu_nav import _dismiss_menus

        _dismiss_menus()
    except Exception:
        pass
    try:
        from import_dialog import dismiss_post_import_popups

        dismiss_post_import_popups(timeout=2.0)
    except Exception:
        pass


def run_flow(
    flow: ImportFlow | str,
    *,
    output_dir: Path | None = None,
    skip_menu: bool = False,
    file_path: Path | None = None,
    wait_check: float = 60.0,
    wait_import: float = 60.0,
    raise_on_fail: bool = True,
) -> dict[str, Any]:
    """
    返回 {key, name, status, message, path}。
    status: ok | empty | fail
    raise_on_fail=True 时，status=fail 会抛 RuntimeError（单跑脚本默认）。
    """
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
        result = {
            "key": flow.key,
            "name": flow.name,
            "status": "fail",
            "message": "无法打开导入对话框",
            "path": str(path),
        }
        if raise_on_fail:
            raise RuntimeError(result["message"])
        return result

    dialog_result = run_dialog_import(
        path, wait_check=wait_check, wait_import=wait_import
    )
    result = {
        "key": flow.key,
        "name": flow.name,
        "status": dialog_result.get("status", "fail"),
        "message": dialog_result.get("message", ""),
        "path": str(path),
    }
    # 仅导入成功后查列表；空文件无账单日，跳过
    if result["status"] == "ok":
        try:
            result["query_date"] = after_import_query(flow.module, path)
        except Exception as exc:
            message = f"查询失败: {exc}"
            if raise_on_fail:
                raise RuntimeError(message) from exc
            result["status"] = "fail"
            result["message"] = message
    elif result["status"] == "empty":
        print("空文件跳过导入后查询")
    if result["status"] == "fail" and raise_on_fail:
        raise RuntimeError(f"导入失败: {result}")
    return result
