"""Per-device worker: owns an AdbDevice and runs farm tasks in a thread."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Optional

from core.device import AdbDevice
from tasks.farm import FarmConfig, FarmResult, FarmTask
from tasks.login import LoginTask


class DeviceWorker:
    def __init__(self, device_id: str, host: str, port: int, name: str = ""):
        self.id = device_id
        self.host = host
        self.port = port
        self.name = name or f"{host}:{port}"
        self.dev = AdbDevice(host, port)
        self.logs: deque[str] = deque(maxlen=500)
        self.status = "idle"  # idle|running|stopping
        self.config: dict = {}
        self.last_result: Optional[dict] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {self.name} {msg}"
        with self._lock:
            self.logs.append(line)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "name": self.name,
                "host": self.host,
                "port": self.port,
                "status": self.status,
                "config": self.config,
                "last_result": self.last_result,
                "logs": list(self.logs)[-80:],
            }

    # ---- task control ----

    def start_task(self, cfg: dict) -> bool:
        with self._lock:
            if self.status == "running":
                return False
            self._stop.clear()
            self.status = "running"
            self.config = cfg
            self._thread = threading.Thread(target=self._dispatch, args=(cfg,), daemon=True)
            self._thread.start()
            return True

    def _dispatch(self, cfg: dict) -> None:
        kind = cfg.get("kind", "farm")
        if kind == "login":
            self._run_login()
        else:
            self._run(cfg)

    def _run_login(self) -> None:
        task = LoginTask(self.dev, cancel_check=self._cancelled)
        self.log("login task start")
        try:
            outcome = task.run()
            self.log(f"login outcome: {outcome}")
            with self._lock:
                self.last_result = {"kind": "login", "outcome": outcome}
        except Exception as e:  # noqa: BLE001
            self.log(f"login error: {e!r}")
            with self._lock:
                self.last_result = {"kind": "login", "errors": [repr(e)]}
        finally:
            with self._lock:
                self.status = "idle"
            self.log("worker idle")

    def stop_task(self) -> bool:
        if self.status != "running":
            return False
        self.status = "stopping"
        self._stop.set()
        return True

    def _cancelled(self) -> bool:
        return self._stop.is_set()

    def _run(self, cfg: dict) -> None:
        farm_cfg = FarmConfig(
            min_gold=int(cfg.get("min_gold", 500_000)),
            min_elixir=int(cfg.get("min_elixir", 500_000)),
            max_searches=int(cfg.get("max_searches", 5)),
            mode=cfg.get("mode", "solo"),
            dry=bool(cfg.get("dry", True)),
            deploy=bool(cfg.get("deploy", True)),
        )
        task = FarmTask(self.dev, farm_cfg, cancel_check=self._cancelled)
        self.log(f"task start mode={farm_cfg.mode} dry={farm_cfg.dry}")
        try:
            res = task.run()
            with self._lock:
                self.last_result = asdict(res)
            self.log(f"task done: {asdict(res)}")
        except Exception as e:  # noqa: BLE001 — surface any failure to the panel
            self.log(f"task error: {e!r}")
            with self._lock:
                self.last_result = {"errors": [repr(e)]}
        finally:
            with self._lock:
                self.status = "idle"
            self.log("worker idle")
