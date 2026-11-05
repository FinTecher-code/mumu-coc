"""Account login task: bring a fresh instance from desktop to the village.

Flow: launch COC -> tencent privacy agreement -> login screen (check the
agree box, tap QQ login) -> QQ authorization (sticky after first manual
login) -> village home detected.

The QQ app must be logged in on the instance beforehand (one-time manual
step). Multi-account = one MuMu instance per QQ account.
"""
from __future__ import annotations

import time

from core.device import AdbDevice
from core.vision import match_template

COC_PACKAGE = "com.tencent.tmgp.supercell.clashofclans"


class LoginTask:
    def __init__(self, device: AdbDevice, cancel_check=None):
        self.dev = device
        self._cancel_check = cancel_check

    def cancelled(self) -> bool:
        return bool(self._cancel_check and self._cancel_check())

    def _tap(self, tpl: str, threshold: float = 0.8, settle: float = 2.0) -> bool:
        frame = self.dev.screencap()
        hit = match_template(frame, f"assets/{tpl}.png", threshold)
        if not hit:
            return False
        self.dev.tap(hit[0], hit[1])
        time.sleep(settle)
        return True

    def at_village(self, threshold: float = 0.9) -> bool:
        frame = self.dev.screencap()
        return match_template(frame, "assets/btn_battle.png", threshold) is not None

    def run(self, timeout: float = 180.0) -> str:
        """Returns 'village' | 'need_manual' | 'failed'."""
        deadline = time.time() + timeout
        self.dev.launch(COC_PACKAGE)
        time.sleep(8)

        saw_login_screen = False
        while time.time() < deadline and not self.cancelled():
            if self.at_village():
                return "village"
            # tencent privacy agreement
            if self._tap("btn_tencent_agree", settle=3.0):
                continue
            # login screen: tick the agree box, then tap QQ login
            if self._tap("chk_agree", settle=1.0):
                saw_login_screen = True
                continue
            if self._tap("btn_qq_login", settle=4.0):
                saw_login_screen = True
                time.sleep(5)
                continue
            # QQ authorization / quick-login confirm screens: templates TBD
            # (slice from a real QQ-login instance)
            time.sleep(3)

        if self.at_village():
            return "village"
        return "need_manual" if saw_login_screen else "failed"
