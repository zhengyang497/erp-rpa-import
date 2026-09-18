# -*- coding: utf-8 -*-
"""导入流程编排（含资金明细 / 商品价格指数）。

公共步骤：
  关旧导入框 →（可选）开模块 → 切页签 → 打开导入 → 粘贴/检查/导入/关窗
  →（可选）填起始日+查询；（可选）关页签

仅差异：
  - flow.module / open_module      —— 菜单
  - flow.tab / flow.tab_needle     —— 页签
  - flow.filename / resolve_file   —— 文件地址
  - flow.open_import / query_after / close_tab_after
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from config import FLOWS, ImportFlow, resolve_file
from import_dialog import (
    click_excel_batch_import,
    click_template_import,
    close_import_dialog,
    find_import_dialog,
    run_dialog_import,
)
from menu_nav import open_module
from query_filter import after_import_query
from tabs import close_document_tab, switch_tab


def cleanup_after_failure() -> None:
    """单条失败后尽量清掉结果窗/导入框/菜单，方便下一条继续。"""
    try:
        from import_dialog import (
            _click_dialog_button,
            _dialog_named_texts,
            dismiss_post_import_popups,
            find_progress_dialog,
            list_dialogs,
        )
        from pywinauto import keyboard

        # 关掉残留结果/警告小窗
        for _ in range(4):
            closed = False
            for title, r, h, w in list_dialogs(min_w=50, min_h=40):
                names = set(_dialog_named_texts(w))
                if "检查数据" in names and "导入数据" in names:
                    continue
                t = (title or "").strip()
                if t in ("导入数据", "检查数据", "警告", "提示", "信息", "错误") or "成功导入" in "\n".join(names) or "没有可以导入" in "\n".join(names):
                    if _click_dialog_button(w, "关闭") or _click_dialog_button(w, "确定"):
                        closed = True
                        time.sleep(0.25)
            if not closed:
                break
        dismiss_post_import_popups(timeout=3.0)
    except Exception:
        pass
    try:
        if find_import_dialog()[0] is not None:
            close_import_dialog()
    except Exception:
        pass
    try:
        from menu_nav import _dismiss_menus
        from pywinauto import keyboard

        _dismiss_menus()
        keyboard.send_keys("{ESC}")
        time.sleep(0.15)
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
        cleanup_after_failure()
        open_module(flow.module)
        time.sleep(1.5)

    switch_tab(flow.tab, tab_needle=flow.tab_needle)
    time.sleep(1.0)

    opener = click_template_import if flow.open_import == "template" else click_excel_batch_import
    open_label = "模板导入" if flow.open_import == "template" else "Excel批量导入"
    ok = False
    last_open_err: Exception | None = None
    for attempt in range(1, 3):
        try:
            ok = opener(timeout=15.0)
            last_open_err = None
        except RuntimeError as exc:
            ok = False
            last_open_err = exc
            print(f"{open_label} attempt {attempt} error: {exc}")
        if ok:
            break
        if attempt == 1:
            print(f"{open_label} first try failed, retry once...")
            if flow.open_import == "template" and not skip_menu:
                print("re-open 商品价格指数登记 then retry 模板导入")
                open_module(flow.module)
                time.sleep(1.5)
                switch_tab(flow.tab, tab_needle=flow.tab_needle)
                time.sleep(1.0)
            else:
                time.sleep(1.0)
    if not ok:
        message = str(last_open_err) if last_open_err else "无法打开导入对话框"
        result = {
            "key": flow.key,
            "name": flow.name,
            "status": "fail",
            "message": message,
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
    # 仅导入成功后查列表；空文件无账单日，跳过。价格指数不做日期查询。
    if result["status"] == "ok" and flow.query_after:
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
    elif result["status"] == "ok" and not flow.query_after:
        print("跳过导入后查询")

    if flow.close_tab_after and result["status"] in {"ok", "empty"}:
        close_document_tab(flow.tab_needle)

    if result["status"] == "fail" and raise_on_fail:
        raise RuntimeError(f"导入失败: {result}")
    return result
