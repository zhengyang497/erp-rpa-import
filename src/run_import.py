# -*- coding: utf-8 -*-
"""统一入口：按 key 或一次跑四个（all 按模块分组；一条挂了继续跑 + 问题日志）。"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import FLOWS
from ops_log import JobLogger
from runner import cleanup_after_failure, run_flow


# 单跑时的可选 key
ORDER = ("option_position", "option_trade", "merged_position", "merged_trade")

# all：按模块分组——每组只导航菜单一次，组内后续只切页签
MODULE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("position_rpa", ("option_position", "merged_position")),
    ("trade_rpa", ("option_trade", "merged_trade")),
)


def _run_one(
    key: str,
    *,
    output_dir: Path | None,
    skip_menu: bool,
    wait_check: float,
    wait_import: float,
    raise_on_fail: bool,
    log: JobLogger | None,
) -> dict:
    flow = FLOWS[key]
    if log:
        log.info(f">>> start {flow.name} ({key}) skip_menu={skip_menu}")
    try:
        result = run_flow(
            key,
            output_dir=output_dir,
            skip_menu=skip_menu,
            wait_check=wait_check,
            wait_import=wait_import,
            raise_on_fail=raise_on_fail,
        )
    except Exception as e:
        cleanup_after_failure()
        detail = f"{type(e).__name__}: {e}"
        tb = traceback.format_exc()
        result = {
            "key": key,
            "name": flow.name,
            "status": "fail",
            "message": detail,
            "path": "",
        }
        if log:
            log.problem(flow_key=key, flow_name=flow.name, detail=f"{detail}\n{tb}")
        elif raise_on_fail:
            raise
        return result

    status = result.get("status", "fail")
    if log:
        if status == "ok":
            log.info(f"<<< ok {flow.name}: {result.get('message', '')[:120]}")
        elif status == "empty":
            log.warn(f"<<< empty/skip {flow.name}: {result.get('message', '')[:120]}")
        else:
            log.problem(
                flow_key=key,
                flow_name=flow.name,
                detail=str(result.get("message", "fail")),
            )
            cleanup_after_failure()
    return result


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
    ap.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="日志目录（默认 src/logs）",
    )
    args = ap.parse_args()

    log = JobLogger(args.log_dir)

    if args.flow == "all":
        results: list[dict] = []
        for module, keys in MODULE_GROUPS:
            log.info(f"===== 模块 {module}（菜单最多 1 次）=====")
            for i, key in enumerate(keys):
                print(f"\n>>> {FLOWS[key].name}")
                results.append(
                    _run_one(
                        key,
                        output_dir=args.output_dir,
                        skip_menu=args.skip_menu or i > 0,
                        wait_check=args.wait_check,
                        wait_import=args.wait_import,
                        raise_on_fail=False,
                        log=log,
                    )
                )

        summary = []
        n_fail = 0
        for r in results:
            st = r.get("status", "fail")
            summary.append(f"{r.get('name')}: {st}")
            if st == "fail":
                n_fail += 1
        log.summary(summary)
        if n_fail:
            log.info(f"完成：{n_fail} 条失败，详见 {log.problem_path}")
            return 1
        log.info("完成：全部成功或空文件跳过")
        return 0

    print(f"\n>>> {FLOWS[args.flow].name}")
    result = _run_one(
        args.flow,
        output_dir=args.output_dir,
        skip_menu=args.skip_menu,
        wait_check=args.wait_check,
        wait_import=args.wait_import,
        raise_on_fail=True,
        log=log,
    )
    if result.get("status") == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
