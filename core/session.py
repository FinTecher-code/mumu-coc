from __future__ import annotations

import cv2

from core.device import AdbDevice
from core.vision import match_template, match_all

DEFAULT_DEVICE = ("112.126.58.211", 21638)


def make_device() -> AdbDevice:
    return AdbDevice(*DEFAULT_DEVICE)


def find(
    self: AdbDevice,
    tpl: str,
    threshold: float = 0.85,
) -> tuple[int, int, float] | None:
    return match_template(self.screencap(), tpl, threshold)
