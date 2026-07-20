# -*- coding: utf-8 -*-
"""Excel批量导入：打开对话框 → 粘贴路径 → 检查数据 → 导入数据 → 确定/成功判定。"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from PIL import Image, ImageGrab
from pywinauto import Desktop, keyboard, mouse

from erp import focus_frame

try:
    import win32clipboard
    import win32con
except ImportError:  # pragma: no cover
    win32clipboard = None
    win32con = None


def set_clipboard_text(text: str) -> None:
    if win32clipboard is None:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"],
            check=True,
        )
        return
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def list_dialogs():
    out = []
    for w in Desktop(backend="win32").windows(class_name="SunAwtDialog", visible_only=False):
        try:
            t = w.window_text() or ""
            r = w.rectangle()
            h = w.handle
        except Exception:
            continue
        if r.width() > 200 and r.height() > 150:
            out.append((t, r, h, w))
    return out


def _dialog_named_texts(dlg) -> list[str]:
    texts: list[str] = []
    try:
        for c in dlg.descendants():
            n = (c.element_info.name or "").strip()
            if n:
                texts.append(n)
    except Exception:
        pass
    return texts


def find_import_dialog():
    """主导入框：必须带「检查数据」按钮（避免误匹配结果框「导入数据」）。"""
    for t, r, h, w in list_dialogs():
        names = set(_dialog_named_texts(w))
        if "检查数据" in names and "导入数据" in names:
            return w, t, r
    return None, None, None


def find_progress_dialog(title: str):
    """进度/结果小窗，如标题「检查数据」「导入数据」。"""
    for t, r, h, w in list_dialogs():
        if t == title:
            return w, t, r
    return None, None, None


def yellow_icon_centers(img: Image.Image) -> list[tuple[int, int]]:
    pts = []
    for y in range(img.height):
        for x in range(min(img.width, 800)):
            r, g, b = img.getpixel((x, y))[:3]
            if r > 200 and g > 180 and b < 120 and r > b + 40:
                pts.append((x, y))
    if not pts:
        return []
    pts.sort()
    clusters: list[list[tuple[int, int]]] = []
    cur = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - cur[-1][0]) <= 25 and abs(p[1] - cur[-1][1]) <= 15:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    centers = []
    for c in clusters:
        if len(c) < 5:
            continue
        xs = [p[0] for p in c]
        ys = [p[1] for p in c]
        centers.append((sum(xs) // len(xs), sum(ys) // len(ys)))
    centers.sort(key=lambda t: t[0])
    return centers


def _named_rect(frame, name: str):
    for c in frame.descendants():
        try:
            n = (c.element_info.name or "").strip()
        except Exception:
            continue
        if n == name:
            return c.rectangle()
    return None


def _excel_link_band(frame) -> tuple[int, int, int, int]:
    fr = frame.rectangle()
    date = (
        _named_rect(frame, "持仓日期从")
        or _named_rect(frame, "交易日从")
        or _named_rect(frame, "日期从")
    )
    keep = _named_rect(frame, "保留筛选")
    if date is not None:
        top = date.bottom - 2
        bot = date.bottom + 55
        left = fr.left
        right = min(fr.left + 520, keep.left - 10 if keep else fr.left + 520)
    elif keep is not None:
        top = keep.bottom
        bot = keep.bottom + 55
        left = fr.left
        right = fr.left + 520
    else:
        top = fr.top + 180
        bot = fr.top + 270
        left = fr.left
        right = fr.left + 520
    return (left, top, right, bot)


def _dismiss_error_dialogs() -> None:
    """关掉挡操作的「错误」小窗（标题或文案含「错误」）。"""
    for w in Desktop(backend="win32").windows(class_name="SunAwtDialog", visible_only=False):
        try:
            t = (w.window_text() or "").strip()
            names = set(_dialog_named_texts(w))
            if t != "错误" and "错误" not in names and "错误" not in t:
                continue
            r = w.rectangle()
            if r.width() < 40 or r.height() < 30:
                continue
            # 点右上角关闭，或底部确认
            if not _click_dialog_button(w, "确定") and not _click_dialog_button(w, "关闭"):
                mouse.click(coords=(r.right - 12, r.top + 10))
            print(f"dismissed error dialog {t!r}")
            time.sleep(0.3)
        except Exception:
            continue


def close_import_dialog() -> None:
    """关掉主导入框（若有）：优先 ESC。"""
    for _ in range(4):
        dlg, _, _ = find_import_dialog()
        if dlg is None:
            return
        keyboard.send_keys("{ESC}")
        time.sleep(0.35)
    # 仍在则点放弃/确认
    dlg, _, _ = find_import_dialog()
    if dlg is not None:
        if not _click_dialog_button(dlg, "放弃"):
            _click_dialog_button(dlg, "确认")
        time.sleep(0.3)


def click_excel_batch_import(*, timeout: float = 15.0) -> bool:
    """
    点击「Excel批量导入」打开导入对话框。
    四条链路共用：OCR 文字 → 黄图标 → 静态模板 → 过滤行锚点。
    """
    from ocr_util import find_best_hit, ocr_image
    from tpl_match import load_template, match_template

    frame = focus_frame()
    if find_import_dialog()[0] is not None:
        return True

    _dismiss_error_dialogs()
    focus_frame(frame)

    fr = frame.rectangle()
    date = (
        _named_rect(frame, "持仓日期从")
        or _named_rect(frame, "交易日从")
        or _named_rect(frame, "日期从")
    )
    keep = _named_rect(frame, "保留筛选")

    if date is not None:
        band_box = (
            fr.left,
            date.top - 5,
            min(fr.right, fr.left + 900),
            date.bottom + 90,
        )
    else:
        band_box = (fr.left, fr.top + 160, min(fr.right, fr.left + 900), fr.top + 340)

    band = ImageGrab.grab(bbox=band_box)
    band.save(Path(__file__).with_name("debug_excel_band.png"))

    candidates: list[tuple[int, int]] = []

    # 1) OCR「Excel批量导入」
    try:
        hits = ocr_image(band)
        hit = find_best_hit(hits, "Excel批量导入")
        if hit is None:
            for h in hits:
                t = h.text.replace(" ", "")
                if ("批量导入" in t or "Excel批量" in t) and "模板" not in t:
                    hit = h
                    break
        if hit is not None:
            p = (band_box[0] + hit.center[0], band_box[1] + hit.center[1])
            candidates.append(p)
            print(f"ocr Excel批量导入 candidate {p} conf={hit.conf:.2f} text={hit.text!r}")
    except Exception as e:
        print(f"ocr Excel批量导入 skipped: {e}")

    # 2) 工具行第 2 个黄图标（第 1 个通常是模板下载）
    centers = yellow_icon_centers(band)
    toolbar = [c for c in centers if c[1] < 55]
    if len(toolbar) >= 2:
        p = (band_box[0] + toolbar[1][0], band_box[1] + toolbar[1][1])
        if p not in candidates:
            candidates.append(p)
        print(f"yellow-icon Excel批量导入 candidate {p} icons={toolbar}")

    # 3) 静态模板（持仓/成交布局各一份，按分数取）
    best_tpl: tuple[float, int, int] | None = None
    for tpl_name in ("excel_batch_import.png", "excel_batch_import_trade.png"):
        try:
            tpl = load_template(tpl_name)
        except FileNotFoundError:
            continue
        hit = match_template(band, tpl, threshold=0.72)
        if hit is None:
            continue
        rx, ry, score = hit
        if best_tpl is None or score > best_tpl[0]:
            best_tpl = (score, rx, ry)
            print(f"template Excel批量导入 candidate via {tpl_name} score={score:.3f}")
    if best_tpl is not None:
        _, rx, ry = best_tpl
        p = (band_box[0] + rx - 20, band_box[1] + ry)
        if p not in candidates:
            candidates.append(p)

    # 4) 过滤行锚点
    if date is not None and keep is not None and abs(keep.top - date.top) < 40:
        p = (date.left + 165, date.bottom + 16)
        if p not in candidates:
            candidates.append(p)
            print(f"anchor Excel批量导入 candidate {p}")

    if not candidates:
        raise RuntimeError("未定位到 Excel批量导入（OCR/图标/模板/锚点均失败）")

    per_try = max(timeout / len(candidates), 8.0)
    for i, click_pos in enumerate(candidates):
        mouse.click(coords=click_pos)
        print(f"click Excel批量导入 attempt={i + 1}/{len(candidates)} at {click_pos}")
        deadline = time.time() + per_try
        while time.time() < deadline:
            dlg, title, rect = find_import_dialog()
            if dlg is not None:
                print(f"opened dialog: {title!r} {rect}")
                return True
            time.sleep(0.25)
    return False


def _click_dialog_button(dlg, name: str, *, allow_zero_size: bool = True) -> bool:
    """
    点对话框按钮。实测「关闭/确认/放弃」常被暴露为 0×0 矩形，但仍有有效 left/top，
    此时按该点点击（或点对话框底部估算位置）。
    """
    for c in dlg.descendants():
        try:
            n = (c.element_info.name or "").strip()
            if n != name:
                continue
            r = c.rectangle()
            if r.width() >= 5 and r.height() >= 5:
                mouse.click(coords=((r.left + r.right) // 2, (r.top + r.bottom) // 2))
                return True
            if allow_zero_size and r.left > 0 and r.top > 0:
                # 零尺寸：点在报告坐标附近偏右下（按钮热区）
                mouse.click(coords=(r.left + 40, r.top + 12))
                return True
        except Exception:
            continue
    return False


def _click_result_close(dlg) -> bool:
    """结果框点「关闭」；零尺寸时用对话框底部估算。"""
    if _click_dialog_button(dlg, "关闭", allow_zero_size=True):
        return True
    # 回退：对话框底部偏左（实测关闭约在左下）
    r = dlg.rectangle()
    mouse.click(coords=(r.left + int(r.width() * 0.22), r.bottom - 40))
    return True


def _focus_file_field(dlg) -> None:
    """点「导入文件」标签右侧空白区，准备 Ctrl+V。"""
    label = None
    for c in dlg.descendants():
        try:
            if (c.element_info.name or "").strip() == "导入文件":
                label = c.rectangle()
                break
        except Exception:
            continue
    if label is None:
        r = dlg.rectangle()
        mouse.click(coords=(r.left + 400, r.top + 120))
        return
    mouse.click(coords=(label.right + 40, (label.top + label.bottom) // 2))
    time.sleep(0.2)


def _wait_progress_done(title: str, *, timeout: float) -> None:
    """等待标题为 title 的进度窗出现后消失（检查数据过程）。"""
    deadline = time.time() + timeout
    seen = False
    while time.time() < deadline:
        w, _, _ = find_progress_dialog(title)
        if w is not None:
            seen = True
        elif seen:
            return
        time.sleep(0.25)
    # 没看到进度窗也继续（有的环境很快）


def _wait_import_result(*, timeout: float) -> tuple[str, str, object]:
    """
    等待「导入数据」结果窗出现可读文案。
    返回 (status, message, dialog)；status: ok | empty | fail
    - empty：没有可以导入的记录（空文件/无有效行）——不算失败
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        w, title, _ = find_progress_dialog("导入数据")
        if w is None:
            time.sleep(0.25)
            continue
        texts = _dialog_named_texts(w)
        joined = "\n".join(texts)
        if "没有可以导入" in joined:
            return "empty", joined, w
        if any(k in joined for k in ("失败", "错误", "异常")):
            return "fail", joined, w
        if "成功导入" in joined:
            return "ok", joined, w
        if "完成" in joined:
            return "ok", joined, w
        if "关闭" in texts and len(joined) > 10:
            if any(k in joined for k in ("失败", "错误")):
                return "fail", joined, w
            return "ok", joined, w
        time.sleep(0.3)
    raise RuntimeError("等待导入结果超时")


def dismiss_post_import_popups(*, timeout: float = 8.0) -> int:
    """
    导入成功并关掉导入框后，ERP 可能再弹提示（原 Uibot 未处理）。
    实测：标题「警告」，文案含「查询限制…50000…」，按钮「关闭」。
    """
    closed = 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        hit = None
        for t, r, h, w in list_dialogs():
            title = (t or "").strip()
            names = set(_dialog_named_texts(w))
            joined = "\n".join(names)
            # 结果窗已处理；主导入框不应在此关
            if "检查数据" in names and "导入数据" in names:
                continue
            if title in ("导入数据", "检查数据"):
                continue
            is_warn = title == "警告" or "警告" in names
            is_limit = "查询限制" in joined or "50000" in joined
            if is_warn or is_limit or (title in ("提示", "信息") and "关闭" in names):
                hit = w
                break
        if hit is None:
            if closed:
                break
            time.sleep(0.3)
            continue
        title = hit.window_text() or ""
        if _click_dialog_button(hit, "关闭") or _click_dialog_button(hit, "确定"):
            print(f"dismissed post-import popup {title!r}")
            closed += 1
            time.sleep(0.4)
        else:
            r = hit.rectangle()
            mouse.click(coords=(r.right - 12, r.top + 10))
            print(f"dismissed post-import popup {title!r} via title-bar X")
            closed += 1
            time.sleep(0.4)
    return closed


def finish_after_import(*, timeout: float = 30.0, kill_excel: bool = False) -> dict:
    """
    按实测优化（不必照搬 Uibot）：
    - 导入后出现标题「导入数据」的结果窗，文案如「成功导入 88 条记录\\n完成」
    - 点「关闭」（不是确定）；主框「确认」常为 0×0，改用 ESC 关掉
    - 成功后可能再出「警告」弹窗（查询限制 50000），点「关闭」——原 RPA 没有这一步
    """
    status, message, result_dlg = _wait_import_result(timeout=timeout)
    print(f"import result: {status}; msg={message[:120]!r}")

    _click_result_close(result_dlg)
    time.sleep(0.5)

    # 关掉主导入框
    for _ in range(3):
        dlg, _, _ = find_import_dialog()
        if dlg is None:
            break
        # 确认控件经常是 0×0 且坐标无意义，ESC 更稳
        keyboard.send_keys("{ESC}")
        time.sleep(0.4)

    dlg_left, _, _ = find_import_dialog()
    # 若结果窗还在，再点一次关闭
    rw, _, _ = find_progress_dialog("导入数据")
    if rw is not None:
        _click_result_close(rw)
        time.sleep(0.3)

    # 导入成功后的额外提示窗（如「警告」查询限制）；空文件一般不会出
    if status == "ok":
        n = dismiss_post_import_popups(timeout=8.0)
        if n:
            print(f"closed {n} post-import popup(s)")

    if kill_excel:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "EXCEL.EXE"],
                capture_output=True,
                text=True,
                check=False,
            )
            print("killed EXCEL.EXE (if any)")
        except Exception as e:
            print(f"kill excel skipped: {e}")

    result = {
        "status": status,
        "message": message[:300],
        "dialog_closed": find_import_dialog()[0] is None,
    }
    print(f"import finish: {result}")
    if status == "empty":
        print("无导入记录（空文件/无有效行），按跳过处理，不视为失败")
        return result
    if status == "fail":
        raise RuntimeError(f"导入失败: {result}")
    return result


def run_dialog_import(
    file_path: Path,
    *,
    wait_check: float = 60.0,
    wait_import: float = 60.0,
    kill_excel: bool = False,
) -> dict:
    """粘贴路径 → 检查数据 → 导入数据 → 读结果并关闭。"""
    path = str(file_path.resolve())
    dlg, title, _ = find_import_dialog()
    if dlg is None:
        raise RuntimeError("导入对话框未打开")

    print(f"import into {title!r}: {path}")
    set_clipboard_text(path)
    time.sleep(0.2)
    _focus_file_field(dlg)
    keyboard.send_keys("^a")
    time.sleep(0.1)
    keyboard.send_keys("^v")
    time.sleep(1.2)

    dlg, _, _ = find_import_dialog()
    if dlg is None:
        raise RuntimeError("粘贴后对话框消失")
    if not _click_dialog_button(dlg, "检查数据"):
        raise RuntimeError("未找到「检查数据」按钮")
    print("clicked 检查数据, waiting progress...")
    _wait_progress_done("检查数据", timeout=wait_check)

    dlg, _, _ = find_import_dialog()
    if dlg is None:
        raise RuntimeError("检查数据后主对话框消失")
    if not _click_dialog_button(dlg, "导入数据"):
        raise RuntimeError("未找到「导入数据」按钮")
    print("clicked 导入数据, waiting result...")
    return finish_after_import(timeout=wait_import, kill_excel=kill_excel)
