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
    import win32api
    import win32clipboard
    import win32con
except ImportError:  # pragma: no cover
    win32api = None
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


def list_dialogs(*, min_w: int = 80, min_h: int = 60, visible_only: bool = False):
    """枚举 SunAwtDialog。结果小窗可能 <200x150，默认放宽尺寸过滤。"""
    out = []
    for w in Desktop(backend="win32").windows(
        class_name="SunAwtDialog", visible_only=visible_only
    ):
        try:
            title = w.window_text() or ""
            r = w.rectangle()
            h = w.handle
        except Exception:
            continue
        if r.width() > min_w and r.height() > min_h:
            out.append((title, r, h, w))
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


def _named_rect(frame, name: str, *, in_content: bool = False):
    from menu_nav import _point_in_frame_content

    for c in frame.descendants():
        try:
            n = (c.element_info.name or "").strip()
        except Exception:
            continue
        if n != name:
            continue
        r = c.rectangle()
        if in_content and not _point_in_frame_content(frame, r):
            continue
        return r
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
            date.bottom + 110,
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
            hit = find_best_hit(hits, "批量导入")
        if hit is None:
            for h in hits:
                t = h.text.replace(" ", "")
                if ("批量导入" in t or "Excel批量" in t) and "模板" not in t and "导出" not in t:
                    hit = h
                    break
        if hit is not None:
            p = (band_box[0] + hit.center[0], band_box[1] + hit.center[1])
            candidates.append(p)
            print(f"ocr Excel批量导入 candidate {p} conf={hit.conf:.2f} text={hit.text!r}")
    except Exception as e:
        print(f"ocr Excel批量导入 skipped: {e}")

    # 2) 黄钥匙图标：过滤行工具栏(y小) 或 下方链接行(y大，成交页常见)
    centers = yellow_icon_centers(band)
    toolbar_top = sorted([c for c in centers if c[1] < 55], key=lambda c: c[0])
    toolbar_link = sorted([c for c in centers if c[1] >= 55], key=lambda c: c[0])
    icon_pick = None
    if len(toolbar_top) >= 2:
        icon_pick = toolbar_top[1]
    elif len(toolbar_link) >= 2:
        icon_pick = toolbar_link[1]
    elif len(centers) >= 2:
        icon_pick = sorted(centers, key=lambda c: c[0])[1]
    if icon_pick is not None:
        p = (band_box[0] + icon_pick[0], band_box[1] + icon_pick[1])
        if p not in candidates:
            candidates.append(p)
        print(
            f"yellow-icon Excel批量导入 candidate {p} "
            f"icons_top={toolbar_top} icons_link={toolbar_link}"
        )

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


def _template_import_band_box(fr, named=None) -> tuple[int, int, int, int]:
    """价格指数页「模板导入」在查询表单下方工具栏。top+230 会裁掉该行。"""
    if named is not None:
        return (
            max(fr.left, named.left - 40),
            max(fr.top, named.top - 20),
            min(fr.right, named.right + 40),
            min(fr.bottom, named.bottom + 20),
        )
    return (
        fr.left,
        fr.top + 70,
        min(fr.right, fr.left + 980),
        min(fr.bottom, fr.top + 430),
    )


def _template_import_click_points(hits, band_box) -> list[tuple[int, int]]:
    from ocr_util import click_point_for_needle

    pts: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for h in hits:
        t = (h.text or "").replace(" ", "").replace("\u3000", "")
        if "模板导入" not in t:
            continue
        rx, ry = click_point_for_needle(h, "模板导入")
        p = (band_box[0] + rx, band_box[1] + ry)
        if p not in seen:
            seen.add(p)
            pts.append(p)
    return pts


def _ocr_hits_native_and_scaled(band):
    from ocr_util import OcrHit, ocr_image

    hits = list(ocr_image(band))
    scaled = band.resize((band.width * 2, band.height * 2))
    for h in ocr_image(scaled):
        hits.append(
            OcrHit(
                text=h.text,
                conf=h.conf,
                left=h.left // 2,
                top=h.top // 2,
                right=h.right // 2,
                bottom=h.bottom // 2,
            )
        )
    return hits


def click_template_import(*, timeout: float = 15.0) -> bool:
    """点击「模板导入」打开导入对话框（价格指数页；不用 Excel批量导入）。"""
    frame = focus_frame()
    if find_import_dialog()[0] is not None:
        return True

    _dismiss_error_dialogs()
    focus_frame(frame)

    fr = frame.rectangle()
    named = _named_rect(frame, "模板导入", in_content=True)
    band_box = _template_import_band_box(fr, named)

    band = ImageGrab.grab(bbox=band_box)
    band.save(Path(__file__).with_name("debug_template_import_band.png"))

    candidates: list[tuple[int, int]] = []

    try:
        hits = _ocr_hits_native_and_scaled(band)
        print(f"ocr 模板导入 texts={[h.text for h in hits[:50]]}")
        ocr_pts = _template_import_click_points(hits, band_box)
        for p in ocr_pts:
            if p not in candidates:
                candidates.append(p)
                print(f"ocr 模板导入 candidate {p}")
    except Exception as e:
        print(f"ocr 模板导入 skipped: {e}")

    if named is not None:
        p = ((named.left + named.right) // 2, (named.top + named.bottom) // 2)
        if p not in candidates:
            candidates.append(p)
            print(f"named 模板导入 candidate {p} rect={named}")

    if not candidates:
        try:
            ImageGrab.grab(bbox=(fr.left, fr.top, fr.right, min(fr.bottom, fr.top + 420))).save(
                Path(__file__).with_name("debug_template_import_top.png")
            )
        except Exception:
            pass
        raise RuntimeError(
            "未定位到 模板导入：当前不是商品价格指数登记页（OCR/可见控件均无此按钮）"
        )

    per_try = max(timeout / len(candidates), 8.0)
    for i, click_pos in enumerate(candidates):
        mouse.click(coords=click_pos)
        print(f"click 模板导入 attempt={i + 1}/{len(candidates)} at {click_pos}")
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


def _file_path_canvas(dlg):
    """导入文件标签右侧的路径框（价格指数为 SunAwtCanvas，不是原生 Edit）。"""
    label = None
    for c in dlg.descendants():
        try:
            if (c.element_info.name or "").strip() == "导入文件":
                label = c.rectangle()
                break
        except Exception:
            continue
    if label is None:
        return None, None
    for c in dlg.descendants():
        try:
            cls = (c.element_info.class_name or "")
            rr = c.rectangle()
        except Exception:
            continue
        if cls != "SunAwtCanvas":
            continue
        if abs(rr.left - label.right) > 8:
            continue
        if abs(rr.top - label.top) > 12:
            continue
        if rr.width() >= 80 and 16 <= rr.height() <= 40:
            return label, rr
    return label, None


def _focus_file_field(dlg) -> None:
    """点「导入文件」右侧路径框，准备 Ctrl+V。"""
    label, canvas = _file_path_canvas(dlg)
    if canvas is not None:
        mouse.click(coords=((canvas.left + canvas.right) // 2, (canvas.top + canvas.bottom) // 2))
        time.sleep(0.2)
        return
    if label is not None:
        mouse.click(coords=(label.right + 40, (label.top + label.bottom) // 2))
        time.sleep(0.2)
        return
    r = dlg.rectangle()
    mouse.click(coords=(r.left + 400, r.top + 120))


def _native_hotkey(*vk_codes: int) -> None:
    """SendInput-style Ctrl+A/V，Swing 画布收得到；pywinauto send_keys 常打到旁路 RichEdit。"""
    if win32api is None or win32con is None:
        combo = "^a" if vk_codes[-1] == ord("A") else "^v"
        keyboard.send_keys(combo)
        return
    for vk in vk_codes:
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
    for vk in reversed(vk_codes):
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


def _paste_into_file_field(dlg) -> None:
    r = dlg.rectangle()
    mouse.click(coords=((r.left + r.right) // 2, r.top + 8))
    time.sleep(0.2)
    _focus_file_field(dlg)
    time.sleep(0.25)
    vk_ctrl = win32con.VK_CONTROL if win32con is not None else 0x11
    _native_hotkey(vk_ctrl, ord("A"))
    time.sleep(0.12)
    _native_hotkey(vk_ctrl, ord("V"))


def _path_visible_in_field(dlg, file_path: Path) -> bool:
    """OCR 路径框，确认文件名已粘贴进去。"""
    from ocr_util import ocr_image, normalize_text

    _, canvas = _file_path_canvas(dlg)
    if canvas is None:
        return False
    pad = 4
    bbox = (canvas.left - pad, canvas.top - pad, canvas.right + pad, canvas.bottom + pad)
    img = ImageGrab.grab(bbox=bbox)
    hits = ocr_image(img)
    blob = normalize_text("".join(h.text for h in hits))
    name = normalize_text(file_path.name)
    stem = normalize_text(file_path.stem)
    ok = (name in blob) or (stem in blob) or ("xlsx" in blob)
    print(f"path field ocr={blob!r} expect={name!r} ok={ok}")
    return ok


def _wait_progress_done(
    title: str,
    *,
    timeout: float,
    min_wait: float = 3.0,
    settle: float = 0.8,
) -> None:
    """
    等待标题为 title 的进度窗：出现 → 消失。
    - 若一直没出现：至少再等到 min_wait（避免检查未完成就点导入）
    - 若超时后进度窗仍在：抛错，不继续
    """
    start = time.time()
    deadline = start + timeout
    seen = False
    while time.time() < deadline:
        w, _, _ = find_progress_dialog(title)
        if w is not None:
            if not seen:
                print(f"progress {title!r} appeared")
            seen = True
        elif seen:
            time.sleep(settle)
            if find_progress_dialog(title)[0] is None:
                print(f"progress {title!r} gone")
                return
        time.sleep(0.25)

    if find_progress_dialog(title)[0] is not None:
        raise RuntimeError(f"等待「{title}」进度结束超时（>{timeout:.0f}s）")

    elapsed = time.time() - start
    if not seen:
        left = max(0.0, min_wait - elapsed)
        if left > 0:
            print(
                f"progress {title!r} not observed; settle {left:.1f}s "
                f"(avoid clicking import too early)"
            )
            time.sleep(left)
        # 再确认一次没有进度窗冒出来
        end = time.time() + min(5.0, timeout * 0.1 + 1.0)
        while time.time() < end:
            if find_progress_dialog(title)[0] is not None:
                # 晚出现：改走「出现后再等消失」
                return _wait_progress_done(
                    title, timeout=max(timeout - (time.time() - start), 15.0),
                    min_wait=0, settle=settle,
                )
            time.sleep(0.25)
    print(f"progress {title!r} wait finished seen={seen}")


def _wait_ready_for_import(*, timeout: float = 45.0) -> object:
    """
    检查结束后：确认「检查数据」进度已消失，主导入框仍在且有「导入数据」。
    返回主对话框控件。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_progress_dialog("检查数据")[0] is not None:
            time.sleep(0.3)
            continue
        dlg, _, _ = find_import_dialog()
        if dlg is not None:
            names = set(_dialog_named_texts(dlg))
            if "导入数据" in names and "检查数据" in names:
                time.sleep(0.6)
                # 双检：进度窗没有又冒出来
                if find_progress_dialog("检查数据")[0] is None:
                    print("import dialog ready after check")
                    return dlg
        time.sleep(0.3)
    raise RuntimeError("检查数据后导入对话框未就绪（进度未结束或主框消失）")


def _classify_import_message(joined: str, texts: list[str]) -> str | None:
    """从结果窗文案判定 status；无法判定则返回 None。"""
    if "没有可以导入" in joined:
        return "empty"
    if any(k in joined for k in ("失败", "错误", "异常")):
        return "fail"
    if "成功导入" in joined or "导入成功" in joined or "条记录" in joined:
        return "ok"
    if "完成" in joined:
        return "ok"
    if "关闭" in texts and len(joined) > 10:
        return "fail" if any(k in joined for k in ("失败", "错误")) else "ok"
    return None


def _ocr_import_result():
    """结果窗可能无 win32 文案；OCR 全屏找成功/空文件。返回 (status, msg, dlg_or_main)。"""
    from ocr_util import ocr_image

    try:
        img = ImageGrab.grab()
        hits = ocr_image(img)
    except Exception as exc:
        print(f"ocr import result skipped: {exc}")
        return None, "", None
    texts = [h.text for h in hits if h.text.strip()]
    joined = "\n".join(texts)
    status = None
    if "没有可以导入" in joined:
        status = "empty"
    elif "成功导入" in joined or "导入成功" in joined:
        status = "ok"
    elif any("条记录" in t and "导入" in joined for t in texts):
        status = "ok"
    if status is None:
        return None, "", None
    dlg, _, _ = find_import_dialog()
    for title, r, h, w in list_dialogs(min_w=50, min_h=40):
        names = set(_dialog_named_texts(w))
        if "检查数据" in names and "导入数据" in names:
            continue
        if r.width() < 900 and r.height() < 500:
            return status, joined[:300], w
    return status, joined[:300], dlg


def _wait_import_result(*, timeout: float) -> tuple[str, str, object]:
    """
    等待导入结果窗出现可读文案。
    返回 (status, message, dialog)；status: ok | empty | fail
    - empty：没有可以导入的记录（空文件/无有效行）——不算失败
    兼容：标题非「导入数据」的结果小窗、尺寸较小的弹窗；等待中顺手关掉挡路「警告」。
    """
    deadline = time.time() + timeout
    seen_unclassified: list[str] = []
    last_ocr = 0.0
    while time.time() < deadline:
        # 挡路警告（查询限制等）先关掉，避免挡住结果窗识别
        for title, r, h, w in list_dialogs(min_w=50, min_h=40):
            names = set(_dialog_named_texts(w))
            joined = "\n".join(names)
            if "检查数据" in names and "导入数据" in names:
                # 价格指数：结果文案可能写在主导入框上
                st = None
                if "成功导入" in joined or "导入成功" in joined or "没有可以导入" in joined:
                    st = _classify_import_message(joined, list(names))
                if st is not None:
                    print(f"import result on main dialog title={title!r} status={st}")
                    return st, joined, w
                continue
            if (title or "").strip() == "警告" or "查询限制" in joined:
                if _click_dialog_button(w, "关闭") or _click_dialog_button(w, "确定"):
                    print(f"dismissed blocking popup during import wait: {title!r}")
                    time.sleep(0.3)

        candidates = []
        for title, r, h, w in list_dialogs(min_w=50, min_h=40):
            names = _dialog_named_texts(w)
            name_set = set(names)
            # 跳过主导入框（无结果文案时）
            if "检查数据" in name_set and "导入数据" in name_set:
                continue
            joined = "\n".join(names)
            status = _classify_import_message(joined, names)
            if status is not None:
                score = 2 if (title or "") == "导入数据" else 1
                if "成功导入" in joined or "没有可以导入" in joined or "导入成功" in joined:
                    score += 2
                candidates.append((score, status, joined, w, title))
            else:
                key = f"{title!r}|{r.width()}x{r.height()}|{joined[:80]}"
                if key not in seen_unclassified:
                    seen_unclassified.append(key)
                    print(f"unclassified dialog during wait: title={title!r} size={r.width()}x{r.height()} names={names[:12]}")

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            _, status, joined, w, title = candidates[0]
            print(f"import result dialog title={title!r} status={status}")
            return status, joined, w

        now = time.time()
        if now - last_ocr >= 2.0:
            last_ocr = now
            ocr_status, ocr_msg, ocr_dlg = _ocr_import_result()
            if ocr_status is not None:
                print(f"import result via OCR status={ocr_status} msg={ocr_msg[:80]!r}")
                return ocr_status, ocr_msg, ocr_dlg
        time.sleep(0.3)
    extra = "; ".join(seen_unclassified[:6])
    raise RuntimeError(f"等待导入结果超时; unclassified={extra}")


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
    - status: ok | empty | fail（fail 不在此抛错，由上层决定）
    """
    status, message, result_dlg = _wait_import_result(timeout=timeout)
    print(f"import result: {status}; msg={message[:120]!r}")

    if result_dlg is not None:
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
    pasted = False
    for attempt in range(3):
        _paste_into_file_field(dlg)
        time.sleep(1.5)
        dlg, _, _ = find_import_dialog()
        if dlg is None:
            raise RuntimeError("粘贴后对话框消失")
        if _path_visible_in_field(dlg, file_path):
            pasted = True
            break
        print(f"path paste attempt {attempt + 1} not visible, retry")
    if not pasted:
        print("path OCR did not confirm file name; continue anyway")
    time.sleep(0.4)
    if not _click_dialog_button(dlg, "检查数据"):
        raise RuntimeError("未找到「检查数据」按钮")
    print("clicked 检查数据, waiting progress...")
    _wait_progress_done("检查数据", timeout=wait_check, min_wait=3.0)
    dlg = _wait_ready_for_import(timeout=max(45.0, wait_check * 0.5))
    # 打印「导入数据」按钮矩形，便于排查 0×0 误点
    for c in dlg.descendants():
        try:
            if (c.element_info.name or "").strip() == "导入数据":
                r = c.rectangle()
                print(f"导入数据 button rect=({r.left},{r.top},{r.right},{r.bottom}) {r.width()}x{r.height()}")
        except Exception:
            continue
    if not _click_dialog_button(dlg, "导入数据"):
        raise RuntimeError("未找到「导入数据」按钮")
    print("clicked 导入数据, waiting result...")
    return finish_after_import(timeout=wait_import, kill_excel=kill_excel)
