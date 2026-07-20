# -*- coding: utf-8 -*-
"""Bring ERP to front, capture full window, try WinRT OCR on menu strip."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
FULL = OUT / "erp_full.png"
MENU = OUT / "erp_menu_ocr.png"
REPORT = OUT / "ocr_report.txt"


def find_frame():
    from pywinauto import Desktop

    desk = Desktop(backend="win32")
    frames = desk.windows(class_name="SunAwtFrame", visible_only=True)
    if not frames:
        raise RuntimeError("ERP SunAwtFrame not found")
    return frames[0]


def ocr_winrt(image_path: Path) -> str:
    """Use Windows.Media.Ocr via PowerShell if available."""
    ps = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
$path = $args[0]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
Function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'zh-Hans')) }
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Text
"""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps, str(image_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return f"OCR_FAILED: {r.stderr.strip()}"
    return (r.stdout or "").strip()


def main() -> None:
    from PIL import ImageGrab

    frame = find_frame()
    try:
        frame.set_focus()
    except Exception:
        pass
    time.sleep(0.4)
    rect = frame.rectangle()
    bbox = (rect.left, rect.top, rect.right, rect.bottom)
    full = ImageGrab.grab(bbox=bbox)
    full.save(FULL)

    # menu strip relative to window: ~ title 30px + menu ~20px
    menu = full.crop((0, 28, full.width, 55))
    # upscale for OCR
    menu4 = menu.resize((menu.width * 3, menu.height * 3))
    menu4.save(MENU)

    text = ocr_winrt(MENU)
    lines = [
        f"frame_rect={rect}",
        f"saved {FULL}",
        f"saved {MENU}",
        "OCR_MENU:",
        text,
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
