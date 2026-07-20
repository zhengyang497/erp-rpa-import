# -*- coding: utf-8 -*-
"""Upscale menu capture + list all named win32 controls on ERP frame."""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pywinauto import Desktop

OUT = Path(__file__).resolve().parent
SRC = OUT / "menu_bar.png"
BIG = OUT / "menu_bar_x4.png"
TOP = OUT / "top_strip.png"
TOP_BIG = OUT / "top_strip_x3.png"
REPORT = OUT / "named_controls.txt"


def main() -> None:
    if SRC.exists():
        img = Image.open(SRC)
        img.resize((img.width * 4, img.height * 4), Image.Resampling.NEAREST).save(BIG)
        print(f"saved {BIG}")
    if TOP.exists():
        img = Image.open(TOP)
        img.resize((img.width * 3, img.height * 3), Image.Resampling.NEAREST).save(TOP_BIG)
        print(f"saved {TOP_BIG}")

    desk = Desktop(backend="win32")
    frames = desk.windows(class_name="SunAwtFrame", visible_only=True)
    lines: list[str] = []
    for f in frames:
        lines.append(f"FRAME {f.window_text()!r}")
        try:
            desc = f.descendants()
        except Exception as e:
            lines.append(f"descendants err: {e}")
            continue
        named = []
        for c in desc:
            try:
                info = c.element_info
                name = (info.name or "").strip()
                if not name:
                    continue
                named.append((info.class_name or "", name, str(c.rectangle())))
            except Exception:
                continue
        seen = set()
        for cls, name, rect in named:
            key = (cls, name)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  {cls}: {name!r} @ {rect}")

    # dialogs
    lines.append("\nDIALOGS:")
    for w in desk.windows(class_name="SunAwtDialog", visible_only=False):
        try:
            lines.append(f"  {w.window_text()!r} @ {w.rectangle()}")
        except Exception as e:
            lines.append(f"  err {e}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
