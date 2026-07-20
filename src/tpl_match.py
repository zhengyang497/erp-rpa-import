# -*- coding: utf-8 -*-
"""静态模板匹配（无实时 OCR）。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def match_template(
    haystack: Image.Image,
    needle: Image.Image,
    *,
    threshold: float = 0.82,
) -> tuple[int, int, float] | None:
    """
    在 haystack 中找 needle，返回 (center_x, center_y, score) 相对 haystack；
    找不到返回 None。纯 numpy NCC，不跑 OCR。
    """
    H = np.asarray(haystack.convert("RGB"), dtype=np.float32)
    N = np.asarray(needle.convert("RGB"), dtype=np.float32)
    if N.shape[0] > H.shape[0] or N.shape[1] > H.shape[1]:
        return None

    nh, nw = N.shape[:2]
    hh, hw = H.shape[:2]
    n = N.reshape(-1, 3)
    n_mean = n.mean(axis=0)
    n_std = n.std(axis=0) + 1e-6
    n_norm = (n - n_mean) / n_std

    best_score = -1.0
    best_xy = (0, 0)
    # 步长 2 加速；命中后再局部精修
    for y in range(0, hh - nh + 1, 2):
        for x in range(0, hw - nw + 1, 2):
            patch = H[y : y + nh, x : x + nw].reshape(-1, 3)
            p_mean = patch.mean(axis=0)
            p_std = patch.std(axis=0) + 1e-6
            score = float(np.mean(n_norm * (patch - p_mean) / p_std))
            if score > best_score:
                best_score = score
                best_xy = (x, y)

    # 精修
    x0, y0 = best_xy
    for y in range(max(0, y0 - 2), min(hh - nh + 1, y0 + 3)):
        for x in range(max(0, x0 - 2), min(hw - nw + 1, x0 + 3)):
            patch = H[y : y + nh, x : x + nw].reshape(-1, 3)
            p_mean = patch.mean(axis=0)
            p_std = patch.std(axis=0) + 1e-6
            score = float(np.mean(n_norm * (patch - p_mean) / p_std))
            if score > best_score:
                best_score = score
                best_xy = (x, y)

    if best_score < threshold:
        return None
    x, y = best_xy
    return x + nw // 2, y + nh // 2, best_score


def load_template(name: str) -> Image.Image:
    path = TEMPLATES_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"缺少模板: {path}")
    return Image.open(path)
