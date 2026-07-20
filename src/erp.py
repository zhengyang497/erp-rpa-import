# -*- coding: utf-8 -*-
"""ERP 主窗口定位。"""
from __future__ import annotations

import time

from pywinauto import Desktop


def find_frame(timeout: float = 5.0):
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            frames = Desktop(backend="win32").windows(
                class_name="SunAwtFrame", visible_only=True
            )
            if not frames:
                frames = [
                    w
                    for w in Desktop(backend="win32").windows(
                        class_name="SunAwtFrame", visible_only=False
                    )
                    if "ERP" in (w.window_text() or "")
                ]
            if frames:
                return frames[0]
        except Exception as e:
            last_err = e
        time.sleep(0.3)
    raise RuntimeError(f"未找到建发 ERP 主窗口: {last_err}")


def focus_frame(frame=None):
    frame = frame or find_frame()
    try:
        frame.restore()
    except Exception:
        pass
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.3)
    return frame
