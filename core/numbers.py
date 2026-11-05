"""Resource number recognizer: white-digit template matching.

COC displays numbers as white glyphs with dark outline. We binarize on
near-white and classify each glyph against assets/digits/<d>_vN.png.
Group gaps (the visual spaces between digit groups) are skipped —
they are only separators and carry no value.
"""
from pathlib import Path
from collections import Counter

import cv2
import numpy as np

DIGITS_DIR = Path("assets/digits")

# glyph runs whose gap exceeds this are separate display groups; value-wise irrelevant
GROUP_GAP = 4
LINK_GAP = 2


def _binarize(row: np.ndarray) -> np.ndarray:
    mn = row.min(axis=2)
    return (mn > 170).astype(np.uint8)


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    """Keep only the largest connected component (the digit stroke)."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 2:
        return mask
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    out = np.zeros_like(mask)
    out[labels == largest] = 1
    return out


AVG_GLYPH_W = 9.5


def _split_glyphs(
    mask: np.ndarray, min_h: int = 9, max_h: int = 14, max_w: int = 14
) -> list[tuple[int, int, int, int]]:
    cols = mask.max(axis=0)
    runs = []
    in_run = False
    for x, v in enumerate(cols):
        if v and not in_run:
            start = x
            in_run = True
        elif not v and in_run:
            runs.append((start, x))
            in_run = False
    if in_run:
        runs.append((start, len(cols)))
    boxes = []
    for s, e in runs:
        ys = mask[:, s:e].max(axis=1)
        idx = np.where(ys)[0]
        if len(idx) == 0 or e - s < 2:
            continue
        y0, y1 = idx[0], idx[-1]
        gh = y1 - y0 + 1
        w = e - s
        if gh < min_h or w > 3 * max_w:
            continue
        if gh > max_h:
            if gh > 20:
                continue
            y0 = y1 - max_h + 1
            gh = max_h
        if w > max_w:
            # glyphs bridged by bright background: chop into equal slices
            n = max(2, round(w / AVG_GLYPH_W))
            step = w / n
            for i in range(n):
                a = s + int(round(i * step))
                b = s + int(round((i + 1) * step))
                if b - a < 3:
                    continue
                boxes.append((a, y0, b - a, gh))
        else:
            boxes.append((s, y0, w, gh))
    return boxes


class DigitReader:
    def __init__(self, digits_dir: Path = DIGITS_DIR):
        self.templates: dict[str, list[np.ndarray]] = {}
        for f in sorted(digits_dir.glob("*_v*.png")):
            label = f.name.rsplit("_v", 1)[0]
            img = cv2.imdecode(np.frombuffer(f.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                m = _clean_mask(_binarize(img))
                self.templates.setdefault(label, []).append(m.astype(np.float32))

    def _classify(self, glyph: np.ndarray) -> str | None:
        g = _clean_mask(_binarize(glyph)).astype(np.float32)
        gh, gw = g.shape
        tol = max(3, int(gh * 0.35))
        best_label, best_score = None, 0.0
        for label, tpls in self.templates.items():
            for tpl in tpls:
                th, tw = tpl.shape
                if abs(gh - th) > tol or abs(gw - tw) > tol:
                    continue
                tpl_r = cv2.resize(tpl, (gw, gh), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(g, tpl_r, cv2.TM_CCOEFF_NORMED)
                s = float(res.max())
                if s > best_score:
                    best_score, best_label = s, label
        if best_score >= 0.65:
            return best_label
        return None

    def read(self, region_img: np.ndarray) -> int | None:
        """region_img: cropped number strip (color BGR). Auto-detects scale."""
        for min_h, max_h in ((9, 14), (14, 24)):
            mask = _binarize(region_img)
            boxes = _split_glyphs(mask, min_h=min_h, max_h=max_h)
            if not boxes:
                continue
            boxes = self._snap_baselines(region_img, boxes)
            if boxes is None:
                continue
            out = []
            for glyph in boxes:
                label = self._classify(glyph)
                if label is None:
                    out = None
                    break
                out.append(label)
            if out:
                return int("".join(out))
        return None

    @staticmethod
    def _snap_baselines(
        region_img: np.ndarray, boxes: list[tuple[int, int, int, int]]
    ) -> list[np.ndarray] | None:
        """Digits in one strip share a baseline; re-crop outliers to the modal span."""
        spans = Counter((gy, gh) for _, gy, _, gh in boxes)
        (modal_y0, modal_h), _ = spans.most_common(1)[0]
        glyphs = []
        for gx, gy, gw, gh in boxes:
            if (gy, gh) != (modal_y0, modal_h) and gh <= modal_h + 6:
                gy, gh = modal_y0, modal_h
            glyphs.append(region_img[gy : gy + gh, gx : gx + gw])
        return glyphs


_default_reader = None


def read_region(frame: np.ndarray, region: tuple[int, int, int, int]) -> int | None:
    global _default_reader
    if _default_reader is None:
        _default_reader = DigitReader()
    x, y, w, h = region
    return _default_reader.read(frame[y : y + h, x : x + w])
