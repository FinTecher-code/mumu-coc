"""Grab frames from the device for template authoring.

Usage:
  .venv/bin/python tools/grab.py                     # save one frame to shots/
  .venv/bin/python tools/grab.py --watch --interval 2
  .venv/bin/python tools/grab.py --crop X Y W H --name btn_attack
                                                     # save cropped template into assets/
"""
import argparse
import time
from pathlib import Path

import cv2

from core.device import AdbDevice

SHOTS = Path("shots")
SHOTS.mkdir(exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="112.126.58.211")
    parser.add_argument("--port", type=int, default=21638)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--crop", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--name", help="template name when using --crop")
    args = parser.parse_args()

    dev = AdbDevice(args.host, args.port)
    n = 0
    while True:
        frame = dev.screencap()
        if args.crop:
            if not args.name:
                parser.error("--crop needs --name to save into assets/")
            x, y, w, h = args.crop
            cropped = frame[y : y + h, x : x + w]
            out = Path("assets") / f"{args.name}.png"
            cv2.imwrite(str(out), cropped)
            print(f"saved template {out} ({w}x{h})")
            break
        out = SHOTS / f"{time.strftime('%H%M%S')}_{n:03d}.png"
        cv2.imwrite(str(out), frame)
        print(f"saved {out}")
        n += 1
        if not args.watch:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
