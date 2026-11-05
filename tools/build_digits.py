"""Extract digit glyphs from the home resource bars.

Because the bar values are known, glyph labels come for free:
  gold   "13 183 550" -> 13183550
  elixir "1 782 110"  -> 1782110
  dark   "14 260"     -> 14260
  gem    "806"        -> 806

Glyphs are saved to assets/digits/<label>_vN.png for the recognizer.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
from core.numbers import _binarize, _split_glyphs, DigitReader

ASSETS = Path("assets")
DIGITS_DIR = ASSETS / "digits"

ROWS = {
    "gold": ((800, 15, 118, 28), "13183550"),
    "elixir": ((795, 52, 122, 30), "1782110"),
    "dark": ((838, 89, 80, 29), "14260"),
    "gem": ((848, 126, 70, 29), "806"),
}


def binarize(row: np.ndarray) -> np.ndarray:
    return _binarize(row)


def split_glyphs(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    return _split_glyphs(mask)


def next_index(label: str) -> int:
    return 1 + len(list(DIGITS_DIR.glob(f"{label}_v*.png")))


def build(frame: np.ndarray) -> None:
    DIGITS_DIR.mkdir(parents=True, exist_ok=True)
    reader = DigitReader.__new__(DigitReader)  # for _snap_baselines only
    for name, ((x, y, w, h), expected) in ROWS.items():
        row = frame[y : y + h, x : x + w]
        mask = _binarize(row)
        boxes = _split_glyphs(mask)
        if len(boxes) != len(expected):
            print(f"[{name}] glyph count {len(boxes)} != expected {len(expected)}: SKIP")
            continue
        glyphs = reader._snap_baselines(row, boxes)
        if glyphs is None:
            print(f"[{name}] snap failed: SKIP")
            continue
        for glyph, label in zip(glyphs, expected):
            idx = next_index(label)
            out = DIGITS_DIR / f"{label}_v{idx}.png"
            cv2.imwrite(str(out), glyph)
        print(f"[{name}] saved {len(boxes)} glyphs -> {expected}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        frame = cv2.imread(sys.argv[1])
    else:
        from core.device import AdbDevice

        dev = AdbDevice("112.126.58.211", 21638)
        frame = dev.screencap()
        cv2.imwrite("shots/bar_latest.png", frame)
    build(frame)
