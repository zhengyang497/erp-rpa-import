# -*- coding: utf-8 -*-
"""Probe ERP main UI for ways to open 境外场外期货 dialog."""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("probe_open_dialog.txt")


def line(s: str, lines: list[str]) -> None:
    lines.append(s)


def main() -> None:
    from pywinauto import Desktop

    lines: list[str] = []
    desk_w = Desktop(backend="win32")
    desk_u = Desktop(backend="uia")

    # Top-level Java windows
    line("=== top-level SunAwt* ===", lines)
    for backend, desk in (("win32", desk_w), ("uia", desk_u)):
        line(f"-- {backend} --", lines)
        for w in desk.windows(visible_only=False):
            try:
                cls = w.element_info.class_name or ""
                title = w.window_text() or ""
            except Exception:
                continue
            if "SunAwt" not in cls and "javaw" not in cls.lower():
                continue
            try:
                rect = w.rectangle()
            except Exception:
                rect = "?"
            line(f"  {cls!r} title={title!r} hwnd={w.handle} rect={rect}", lines)

    # Main frame menu (UIA)
    line("\n=== UIA MenuBar / MenuItem on SunAwtFrame ===", lines)
    frames = desk_u.windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        frames = [w for w in desk_u.windows(visible_only=True) if "ERP" in (w.window_text() or "")]
    for f in frames:
        line(f"frame: {f.window_text()!r}", lines)
        try:
            for c in f.children():
                info = c.element_info
                line(
                    f"  child type={getattr(info,'control_type',None)} "
                    f"class={info.class_name!r} name={info.name!r} rect={c.rectangle()}",
                    lines,
                )
                if (info.class_name or "") == "" and getattr(info, "control_type", "") in (
                    "MenuBar",
                    "ToolBar",
                ) or (info.name or "") in ("应用程序", "系统"):
                    try:
                        for m in c.children():
                            mi = m.element_info
                            line(
                                f"    item name={mi.name!r} type={getattr(mi,'control_type',None)} "
                                f"rect={m.rectangle()}",
                                lines,
                            )
                    except Exception as e:
                        line(f"    children err: {e}", lines)
        except Exception as e:
            line(f"  children err: {e}", lines)

        # All MenuItems via descendants
        line("  all MenuItems:", lines)
        try:
            for m in f.descendants(control_type="MenuItem"):
                mi = m.element_info
                line(f"    MenuItem name={mi.name!r} rect={m.rectangle()}", lines)
        except Exception as e:
            line(f"    descendants MenuItem err: {e}", lines)

    # win32: look for anything with 期货/持仓/导入 in name under frame
    line("\n=== win32 named controls containing keywords ===", lines)
    kws = ("期货", "持仓", "导入", "掉期", "境外", "场外", "成交")
    for f in desk_w.windows(class_name="SunAwtFrame", visible_only=True):
        line(f"frame: {f.window_text()!r}", lines)
        try:
            desc = f.descendants()
        except Exception as e:
            line(f"  descendants err: {e}", lines)
            continue
        hits = []
        for c in desc:
            try:
                name = (c.element_info.name or "").strip()
                cls = c.element_info.class_name or ""
            except Exception:
                continue
            if name and any(k in name for k in kws):
                hits.append((cls, name, str(c.rectangle())))
        # unique
        seen = set()
        for cls, name, rect in hits:
            key = (cls, name)
            if key in seen:
                continue
            seen.add(key)
            line(f"  HIT {cls}: {name!r} @ {rect}", lines)
        if not hits:
            line("  (no keyword hits under frame)", lines)

    # Dialog present?
    line("\n=== SunAwtDialog titles ===", lines)
    for w in desk_w.windows(class_name="SunAwtDialog", visible_only=False):
        try:
            line(f"  {w.window_text()!r} rect={w.rectangle()}", lines)
        except Exception as e:
            line(f"  err {e}", lines)

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
