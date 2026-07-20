# -*- coding: utf-8 -*-
"""③ 期货掉期持仓导入 — 对应 V2: 期货与掉期持仓导入模板.xlsx"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner import run_flow


def main() -> int:
    ap = argparse.ArgumentParser(description="导入：期货掉期持仓")
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--skip-menu", action="store_true")
    ap.add_argument("--wait-check", type=float, default=60.0)
    ap.add_argument("--wait-import", type=float, default=60.0)
    args = ap.parse_args()
    run_flow(
        "merged_position",
        output_dir=args.output_dir,
        file_path=args.file,
        skip_menu=args.skip_menu,
        wait_check=args.wait_check,
        wait_import=args.wait_import,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
