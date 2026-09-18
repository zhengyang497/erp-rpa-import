# -*- coding: utf-8 -*-
"""OCR 工具：截图识别中文，供菜单文字定位。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class OcrHit:
    text: str
    conf: float
    # 相对截图坐标
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + self.right) // 2, (self.top + self.bottom) // 2


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = t.replace(" ", "").replace("\u3000", "")
    t = t.replace("&", "＆").replace("(", "（").replace(")", "）")
    t = t.replace("+", "＋")
    t = re.sub(r"[-—–_·•]+", "", t)
    return t.lower()


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_image(image: Image.Image) -> list[OcrHit]:
    """对 PIL 图做 OCR，返回相对坐标命中列表。"""
    arr = np.array(image.convert("RGB"))
    result, _ = _engine()(arr)
    hits: list[OcrHit] = []
    if not result:
        return hits
    for item in result:
        # item: [box(4 points), text, score]
        box, text, score = item[0], item[1], float(item[2])
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        hits.append(
            OcrHit(
                text=str(text),
                conf=score,
                left=int(min(xs)),
                top=int(min(ys)),
                right=int(max(xs)),
                bottom=int(max(ys)),
            )
        )
    return hits


def score_hit(hit: OcrHit, needle: str) -> float:
    """返回匹配分；不匹配为 0。避免「管理」等公共后缀误匹配。"""
    target = normalize_text(needle)
    got = normalize_text(hit.text)
    if not target or not got or hit.conf < 0.4:
        return 0.0
    if got == target:
        return 200.0 + hit.conf
    if target in got:
        ratio = len(got) / max(len(target), 1)
        if ratio <= 1.35:
            return 150.0 + hit.conf
        if ratio <= 1.8:
            return 100.0 + hit.conf
        return 0.0
    if got in target and len(got) >= len(target) - 1 and len(got) >= 3:
        return 120.0 + hit.conf
    return 0.0


def click_point_for_needle(hit: OcrHit, needle: str) -> tuple[int, int]:
    """相对截图坐标。OCR 把同一行多个按钮合成一串时，点 needle 所在片段，不要点整框中心。"""
    t = (hit.text or "").replace(" ", "").replace("\u3000", "")
    n = (needle or "").replace(" ", "").replace("\u3000", "")
    idx = t.rfind(n) if n else -1
    width = max(hit.right - hit.left, 1)
    if idx >= 0 and len(t) > len(n) + 1:
        frac = (idx + len(n) / 2.0) / max(len(t), 1)
        x = hit.left + int(round(width * frac))
        x = min(max(x, hit.left + 1), hit.right - 1)
    else:
        x = (hit.left + hit.right) // 2
    y = (hit.top + hit.bottom) // 2
    return x, y


def find_best_hit(
    hits: list[OcrHit],
    needle: str,
    *,
    min_conf: float = 0.4,
    min_score: float = 90.0,
) -> OcrHit | None:
    """在 OCR 结果中找最匹配目标文字。"""
    best: tuple[float, OcrHit] | None = None
    for h in hits:
        if h.conf < min_conf:
            continue
        sc = score_hit(h, needle)
        if sc < min_score:
            continue
        if best is None or sc > best[0]:
            best = (sc, h)
    return best[1] if best else None
