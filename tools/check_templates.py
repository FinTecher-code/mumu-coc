import sys

from core.device import AdbDevice
from core.vision import match_template

dev = AdbDevice("112.126.58.211", 21638)
frame = dev.screencap()
for name in sys.argv[1:] or ["btn_battle", "btn_build"]:
    hit = match_template(frame, f"assets/{name}.png", threshold=0.8)
    print(name, "->", hit)
