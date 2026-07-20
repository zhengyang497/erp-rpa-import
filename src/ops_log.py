# -*- coding: utf-8 -*-
"""Ops logging: one run log + one problems log per job."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "logs"


class JobLogger:
    def __init__(self, log_dir: Path | None = None) -> None:
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_path = self.log_dir / f"run_{ts}.log"
        self.problem_path = self.log_dir / f"problems_{ts}.log"
        self._write(self.run_path, f"=== job start {ts} ===")
        self._write(self.problem_path, f"=== problems {ts} ===")
        print(f"run log: {self.run_path}")
        print(f"problem log: {self.problem_path}")

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

    def problem(self, *, flow_key: str, flow_name: str, detail: str) -> None:
        line = f"{flow_key} ({flow_name}): {detail}"
        print(f"[PROBLEM] {line}")
        self._write(self.run_path, f"ERROR {line}")
        self._write(self.problem_path, line)

    def summary(self, lines: list[str]) -> None:
        self.info("--- summary ---")
        for line in lines:
            self.info(line)
