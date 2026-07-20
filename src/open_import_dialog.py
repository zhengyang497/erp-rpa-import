# -*- coding: utf-8 -*-
"""
端到端（仅到打开导入对话框为止）:

  主菜单 → 境外与场外衍生品持仓明细（RPA） → Excel批量导入 → 境外场外期货对话框

不执行：粘贴路径 / 检查数据 / 导入数据。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from click_excel_import import click_excel_batch_import, list_import_dialogs
from open_module import open_rpa_position_module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--skip-menu",
        action="store_true",
        help="模块已打开时跳过主菜单导航，只点 Excel批量导入",
    )
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()

    if list_import_dialogs():
        print("already open: 境外场外期货")
        return 0

    if not args.skip_menu:
        open_rpa_position_module(dry_run=False, shot=True)
        time.sleep(1.0)

    ok = click_excel_batch_import(timeout=args.timeout)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
