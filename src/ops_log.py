# -*- coding: utf-8 -*-
"""运维日志：文本 run/problems + 给人看的「问题报告」Excel（对齐 option-margin）。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "logs"


class Severity(str, Enum):
    FATAL = "致命"
    WARNING = "警告"
    INFO = "信息"


@dataclass(frozen=True)
class Issue:
    """给人看的问题行；列名对齐 option-margin 习惯，字段按 RPA 语义填充。"""

    severity: Severity
    message: str
    flow: str = ""  # 链路名，如 期权持仓
    file: str = ""  # Excel 路径
    module: str = ""  # position_rpa / trade_rpa
    tab: str = ""  # futures_swap / option
    step: str = ""  # 菜单/页签/导入等

    def to_row(self) -> dict[str, Any]:
        return {
            "严重程度": self.severity.value,
            "链路": self.flow,
            "文件": self.file,
            "模块": self.module,
            "页签": self.tab,
            "步骤": self.step,
            "问题描述": self.message,
        }


class JobLogger:
    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.started = datetime.now()
        ts = self.started.strftime("%Y%m%d_%H%M%S")
        self.date_label = self.started.strftime("%Y-%m-%d")
        self.run_path = self.log_dir / f"run_{ts}.log"
        self.problem_path = self.log_dir / f"problems_{ts}.log"
        self.report_path = self.log_dir / f"问题报告_{self.date_label}.xlsx"
        self.issues: list[Issue] = []
        self._write(self.run_path, f"=== job start {ts} ===")
        self._write(self.problem_path, f"=== problems {ts} ===")
        print(f"run log: {self.run_path}")
        print(f"problem log: {self.problem_path}")
        print(f"问题报告: {self.report_path}")

    @staticmethod
    def _write(path: Path, line: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {line}\n")

    def info(self, msg: str) -> None:
        print(msg)
        self._write(self.run_path, f"INFO  {msg}")

    def warn(self, msg: str) -> None:
        print(msg)
        self._write(self.run_path, f"WARN  {msg}")

    def add_issue(
        self,
        severity: Severity,
        message: str,
        *,
        flow: str = "",
        file: str = "",
        module: str = "",
        tab: str = "",
        step: str = "",
    ) -> None:
        self.issues.append(
            Issue(
                severity=severity,
                message=message,
                flow=flow,
                file=file,
                module=module,
                tab=tab,
                step=step,
            )
        )

    def problem(
        self,
        *,
        flow_key: str,
        flow_name: str,
        detail: str,
        file: str = "",
        module: str = "",
        tab: str = "",
        step: str = "导入",
    ) -> None:
        """致命问题：文本 problems 日志 + 收集进 Excel 报告。"""
        line = f"{flow_key} ({flow_name}): {detail}"
        print(f"[PROBLEM] {line}")
        self._write(self.run_path, f"ERROR {line}")
        self._write(self.problem_path, line)
        # Excel 里问题描述不宜过长堆栈；截断，全文仍在 problems_*.log
        short = detail.strip()
        if len(short) > 800:
            short = short[:800] + "…"
        self.add_issue(
            Severity.FATAL,
            short,
            flow=flow_name or flow_key,
            file=file,
            module=module,
            tab=tab,
            step=step,
        )

    def empty_skip(
        self,
        *,
        flow_name: str,
        message: str,
        file: str = "",
        module: str = "",
        tab: str = "",
    ) -> None:
        """空文件跳过：记信息级，写入报告便于核对。"""
        self.warn(f"<<< empty/skip {flow_name}: {message[:120]}")
        self.add_issue(
            Severity.INFO,
            message.strip() or "没有可以导入的记录",
            flow=flow_name,
            file=file,
            module=module,
            tab=tab,
            step="导入",
        )

    def summary(self, lines: list[str]) -> None:
        self.info("--- summary ---")
        for line in lines:
            self.info(line)

    def has_fatal(self) -> bool:
        return any(i.severity == Severity.FATAL for i in self.issues)

    def write_problem_report(self) -> Path:
        """
        写出给人看的 Excel（对齐 option-margin「问题报告_日期.xlsx」）。
        无问题也写表头，方便打开确认。
        """
        try:
            from openpyxl import Workbook
        except ImportError as e:
            self.warn(f"未安装 openpyxl，跳过问题报告 Excel: {e}")
            return self.report_path

        wb = Workbook()
        ws = wb.active
        ws.title = "问题报告"
        headers = ["严重程度", "链路", "文件", "模块", "页签", "步骤", "问题描述"]
        ws.append(headers)
        for issue in self.issues:
            row = issue.to_row()
            ws.append([row[h] for h in headers])

        # 简单列宽，方便打开就看
        widths = {"A": 10, "B": 16, "C": 48, "D": 14, "E": 14, "F": 10, "G": 60}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        wb.save(self.report_path)
        n_fatal = sum(1 for i in self.issues if i.severity == Severity.FATAL)
        n_warn = sum(1 for i in self.issues if i.severity == Severity.WARNING)
        n_info = sum(1 for i in self.issues if i.severity == Severity.INFO)
        self.info(
            f"问题报告已写出: {self.report_path} "
            f"（致命 {n_fatal}，警告 {n_warn}，信息 {n_info}）"
        )
        return self.report_path
