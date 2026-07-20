# -*- coding: utf-8 -*-
"""兼容入口：OCR 打开持仓明细(RPA)模块。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from menu_nav import open_module, open_position_rpa_module, open_trade_rpa_module


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="OCR 导航到目标项但不点击打开")
    ap.add_argument(
        "--module",
        choices=("position_rpa", "trade_rpa"),
        default="position_rpa",
    )
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()
    open_module(args.module, dry_run=args.dry_run, verify=not args.no_verify)


if __name__ == "__main__":
    main()
