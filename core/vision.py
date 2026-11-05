from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


def match_template(
    scene: np.ndarray,
    template_path: str,
    threshold: float = 0.85,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[int, int, float]]:
    """Return (x, y, score) of the best template match center, or None."""
    tpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(template_path)
    target = scene
    offset_x = offset_y = 0
    if region is not None:
        x, y, w, h = region
        target = scene[y : y + h, x : x + w]
        offset_x, offset_y = x, y
    if (
        target.shape[0] < tpl.shape[0]
        or target.shape[1] < tpl.shape[1]
    ):
        return None
    res = cv2.matchTemplate(target, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return None
    ch, cw = tpl.shape[0] // 2, tpl.shape[1] // 2
    return (
        max_loc[0] + cw + offset_x,
        max_loc[1] + ch + offset_y,
        float(max_val),
    )


def match_all(
    scene: np.ndarray,
    template_path: str,
    threshold: float = 0.85,
    max_matches: int = 50,
) -> list[Tuple[int, int, float]]:
    """Return all match centers above threshold, suppressed to distinct spots."""
    tpl = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(template_path)
    res = cv2.matchTemplate(scene, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= threshold)
    hits = sorted(zip(xs.tolist(), ys.tolist(), res[ys, xs].tolist()),
                  key=lambda m: -m[2])
    kept: list[Tuple[int, int, float]] = []
    dist = max(tpl.shape[0], tpl.shape[1]) // 2
    for x, y, score in hits[: max_matches * 4]:
        if len(kept) >= max_matches:
            break
        if x is None:
            continue
        if all(abs(x - kx) > dist or abs(y - ky) > dist for kx, ky, _ in kept):
            kept.append((x + tpl.shape[1] // 2,
                         y + tpl.shape[0] // 2,
                         float(score)))
    return kept
