"""Add labeled digit samples from any frame with a known number strip.

Usage:
  PYTHONPATH=. python tools/add_digits.py shots/diag_0.png 45 66 105 26 236929
"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.numbers import _binarize, _split_glyphs, DigitReader  # noqa: E402
from tools.build_digits import DIGITS_DIR, next_index  # noqa: E402


def main() -> None:
    frame_path, x, y, w, h, expected = (
        sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
        int(sys.argv[4]), int(sys.argv[5]), sys.argv[6],
    )
    frame = cv2.imread(frame_path)
    row = frame[y : y + h, x : x + w]
    boxes = _split_glyphs(_binarize(row))
    if len(boxes) != len(expected):
        print(f"glyph count {len(boxes)} != {len(expected)}: SKIP")
        return
    glyphs = DigitReader._snap_baselines(row, boxes)
    DIGITS_DIR.mkdir(parents=True, exist_ok=True)
    for glyph, label in zip(glyphs, expected):
        idx = next_index(label)
        out = DIGITS_DIR / f"{label}_v{idx}.png"
        cv2.imwrite(str(out), glyph)
    print(f"saved {len(boxes)} glyphs -> {expected}")


if __name__ == "__main__":
    main()
