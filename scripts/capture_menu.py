# -*- coding: utf-8 -*-
"""Capture ERP menu bar image and list top toolbar-like children."""
from __future__ import annotations

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
IMG = OUT_DIR / "menu_bar.png"
IMG_TOP = OUT_DIR / "top_strip.png"
REPORT = OUT_DIR / "menu_capture.txt"


def main() -> None:
    from pywinauto import Desktop
    from PIL import ImageGrab

    lines: list[str] = []
    desk = Desktop(backend="uia")
    frames = desk.windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        raise SystemExit("no ERP frame")
    f = frames[0]
    lines.append(f"title={f.window_text()!r}")
    lines.append(f"frame_rect={f.rectangle()}")

    # Find MenuBar
    menubar = None
    for c in f.children():
        info = c.element_info
        if getattr(info, "control_type", None) == "MenuBar" or (info.name or "") == "应用程序":
            menubar = c
            break
    if menubar is None:
        lines.append("menubar not found")
    else:
        r = menubar.rectangle()
        lines.append(f"menubar_rect={r}")
        # slightly taller crop for clarity
        bbox = (r.left, r.top, r.right, min(r.bottom + 2, r.top + 40))
        img = ImageGrab.grab(bbox=bbox)
        img.save(IMG)
        lines.append(f"saved {IMG} size={img.size}")

        # also dump each menu item rect for later click-by-index
        for i, m in enumerate(menubar.children()):
            mr = m.rectangle()
            lines.append(f"menu[{i}] rect={mr} center=({(mr.left+mr.right)//2},{(mr.top+mr.bottom)//2})")

    # Top strip below title: toolbar canvas
    fr = f.rectangle()
    top_bbox = (fr.left, fr.top + 28, fr.right, fr.top + 100)
    ImageGrab.grab(bbox=top_bbox).save(IMG_TOP)
    lines.append(f"saved {IMG_TOP}")

    # win32 buttons near top of frame
    desk_w = Desktop(backend="win32")
    fw = desk_w.window(handle=f.handle)
    lines.append("\nwin32 buttons near top:")
    try:
        for b in fw.descendants(class_name="Button"):
            try:
                name = b.window_text() or ""
                br = b.rectangle()
            except Exception:
                continue
            if br.top < fr.top + 120 and name.strip():
                lines.append(f"  Button {name!r} @ {br}")
    except Exception as e:
        lines.append(f"  err {e}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
