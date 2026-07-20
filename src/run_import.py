# -*- coding: utf-8 -*-
"""统一入口：按 key 或一次跑四个（all 按模块分组，菜单只开两次）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import FLOWS
from runner import run_flow


# 单跑时的可选 key
ORDER = ("option_position", "option_trade", "merged_position", "merged_trade")

# all：按模块分组——每组只导航菜单一次，组内后续只切页签
MODULE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("position_rpa", ("option_position", "merged_position")),
    ("trade_rpa", ("option_trade", "merged_trade")),
)


def main() -> int:
    ap = argparse.ArgumentParser(description="ERP 导入：对应 option-margin V2 四份输出")
    ap.add_argument(
        "flow",
        nargs="?",
        choices=[*ORDER, "all"],
        default="all",
        help="option_position|option_trade|merged_position|merged_trade|all",
    )
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument(
        "--skip-menu",
        action="store_true",
        help="跳过主菜单（单跑时用；all 时表示两组都不再开菜单）",
    )
    ap.add_argument("--wait-check", type=float, default=60.0)
    ap.add_argument("--wait-import", type=float, default=60.0)
    args = ap.parse_args()

    if args.flow == "all":
        for module, keys in MODULE_GROUPS:
            print(f"\n===== 模块 {module}（菜单最多 1 次）=====")
            for i, key in enumerate(keys):
                print(f"\n>>> {FLOWS[key].name}")
                run_flow(
                    key,
                    output_dir=args.output_dir,
                    skip_menu=args.skip_menu or i > 0,
                    wait_check=args.wait_check,
                    wait_import=args.wait_import,
                )
        return 0

    print(f"\n>>> {FLOWS[args.flow].name}")
    run_flow(
        args.flow,
        output_dir=args.output_dir,
        skip_menu=args.skip_menu,
        wait_check=args.wait_check,
        wait_import=args.wait_import,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
