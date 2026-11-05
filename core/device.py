import subprocess
import time
import socket
from typing import Optional

import cv2
import numpy as np


class AdbDevice:
    def __init__(self, host: str, port: int, adb_path: str = "adb"):
        self.serial = f"{host}:{port}"
        self.adb_path = adb_path
        self._connected = False

    def _cmd(self, *args: str, timeout: float = 15.0) -> bytes:
        cmd = [self.adb_path, "-s", self.serial, *args]
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"adb {args[0]} failed: {proc.stderr.decode(errors='ignore').strip()}"
            )
        return proc.stdout

    def connect(self, retries: int = 3) -> bool:
        for i in range(retries):
            try:
                subprocess.run(
                    ["adb", "disconnect", self.serial],
                    capture_output=True, timeout=10,
                )
                proc = subprocess.run(
                    [self.adb_path, "connect", self.serial],
                    capture_output=True,
                    timeout=10,
                )
                out = (proc.stdout + proc.stderr).decode(errors="ignore")
                if "connected" in out and self.is_alive():
                    self._connected = True
                    return True
            except (subprocess.TimeoutExpired, OSError, socket.error):
                pass
            time.sleep(2 * (i + 1))
        self._connected = False
        return False

    def is_alive(self) -> bool:
        try:
            out = subprocess.run(
                ["adb", "devices"], capture_output=True, timeout=10
            ).stdout.decode()
        except (subprocess.TimeoutExpired, OSError):
            return False
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0] == self.serial and parts[1] == "device":
                return True
        return False

    def ensure(self) -> None:
        if not self.is_alive():
            if not self.connect():
                raise ConnectionError(f"cannot reach device {self.serial}")

    # ---- control ----

    def screencap(self, retries: int = 2) -> np.ndarray:
        self.ensure()
        last_err: Exception | None = None
        for _ in range(retries + 1):
            try:
                png = self._cmd("exec-out", "screencap", "-p", timeout=30)
                img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    return img
                last_err = RuntimeError("screencap returned invalid data")
            except subprocess.TimeoutExpired as e:
                last_err = e
            time.sleep(1)
        raise last_err or RuntimeError("screencap failed")

    def tap(self, x: int, y: int) -> None:
        self.ensure()
        self._cmd("shell", "input", "tap", str(int(x)), str(int(y)), timeout=10)

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
    ) -> None:
        self.ensure()
        self._cmd(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)),
            str(int(duration_ms)),
            timeout=15,
        )

    def key_back(self) -> None:
        self.ensure()
        self._cmd("shell", "input", "keyevent", "4", timeout=10)

    def launch(self, package: str) -> None:
        self.ensure()
        self._cmd(
            "shell",
            "monkey",
            "-p", package,
            "-c", "android.intent.category.LAUNCHER",
            "1",
            timeout=30,
        )

    def stop(self, package: str) -> None:
        self.ensure()
        self._cmd("shell", "am", "force-stop", package, timeout=15)

    def installed(self, package: str) -> bool:
        self.ensure()
        out = self._cmd("shell", "pm", "list", "packages", package, timeout=15)
        return package in out.decode(errors="ignore")
