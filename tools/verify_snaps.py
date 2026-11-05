"""Verify which village each account snapshot actually opens.

Flow per snapshot: restore -> launch -> tick agree -> tap QQ login
-> wait for village -> read resource bar -> save screenshot.
"""
import subprocess
import sys
import time
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.device import AdbDevice  # noqa: E402
from core.numbers import read_region  # noqa: E402
from core.vision import match_template  # noqa: E402
from tools.account_snap import PKG, load  # noqa: E402

HOST = "112.126.58.211"
PORT = 21638

GOLD = (800, 15, 118, 28)
ELIXIR = (795, 52, 122, 30)


def tap(dev: AdbDevice, tpl: str, threshold=0.8, settle=2.0) -> bool:
    frame = dev.screencap()
    hit = match_template(frame, f"assets/{tpl}.png", threshold)
    if not hit:
        return False
    dev.tap(hit[0], hit[1])
    time.sleep(settle)
    return True


def verify(name: str, dev: AdbDevice) -> None:
    print(f"=== {name} ===")
    load(name)  # force-stop, restore, relaunch
    time.sleep(20)

    deadline = time.time() + 90
    in_village = False
    while time.time() < deadline:
        frame = dev.screencap()
        if match_template(frame, "assets/btn_battle.png", 0.9):
            in_village = True
            break
        tap(dev, "btn_tencent_agree")
        tap(dev, "chk_unchecked")
        if tap(dev, "btn_qq_login2", settle=6.0):
            time.sleep(8)
        tap(dev, "dlg_star_bonus")  # dismiss popups
        time.sleep(2)

    if not in_village:
        print("  !! did not reach village in 90s")
        return
    # settle + dismiss place-item prompt with X (left button)
    time.sleep(4)
    frame = dev.screencap()
    gold = read_region(frame, GOLD)
    elixir = read_region(frame, ELIXIR)
    out = Path(f"shots/verify_{name}.png")
    cv2.imwrite(str(out), frame)
    print(f"  village reached | gold={gold} elixir={elixir} | shot={out}")


if __name__ == "__main__":
    dev = AdbDevice(HOST, PORT)
    dev.ensure()
    for name in sys.argv[1:] or ["su1", "su2", "su3_qq"]:
        verify(name, dev)
