"""Mumu-COC control panel server.

Run:  .venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
UI:   http://localhost:8000/
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.scheduler import DeviceWorker


def _placeholder(text: str) -> bytes:
    img = np.full((270, 480, 3), 24, np.uint8)
    cv2.putText(img, text, (60, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (90, 100, 120), 2, cv2.LINE_AA)
    ok, jpeg = cv2.imencode(".jpg", img)
    return jpeg.tobytes()

app = FastAPI(title="mumu-coc")

WORKERS_FILE = Path("workers.json")
_workers: dict[str, DeviceWorker] = {}
_lock = threading.Lock()


def _persist() -> None:
    data = [
        {"id": w.id, "host": w.host, "port": w.port, "name": w.name}
        for w in _workers.values()
    ]
    WORKERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _restore() -> None:
    if WORKERS_FILE.exists():
        for item in json.loads(WORKERS_FILE.read_text()):
            w = DeviceWorker(item["id"], item["host"], item["port"], item.get("name", ""))
            _workers[w.id] = w


_restore()


class WorkerIn(BaseModel):
    host: str
    port: int
    name: str = ""


class TaskIn(BaseModel):
    kind: str = "farm"  # farm | login
    mode: str = "solo"
    dry: bool = True
    deploy: bool = True
    min_gold: int = 500_000
    min_elixir: int = 500_000
    max_searches: int = 5


def _get(worker_id: str) -> DeviceWorker:
    w = _workers.get(worker_id)
    if not w:
        raise HTTPException(404, "worker not found")
    return w


@app.get("/")
def index():
    return FileResponse("web/index.html")


@app.get("/api/workers")
def list_workers():
    return [w.snapshot() for w in _workers.values()]


@app.post("/api/workers")
def add_worker(body: WorkerIn):
    wid = uuid.uuid4().hex[:8]
    w = DeviceWorker(wid, body.host, body.port, body.name)
    with _lock:
        _workers[wid] = w
        _persist()
    return w.snapshot()


@app.delete("/api/workers/{wid}")
def remove_worker(wid: str):
    w = _get(wid)
    w.stop_task()
    with _lock:
        del _workers[wid]
        _persist()
    return {"ok": True}


@app.post("/api/workers/{wid}/check")
def check_worker(wid: str):
    w = _get(wid)
    ok = w.dev.is_alive() or w.dev.connect()
    w.log("device online" if ok else "device unreachable")
    return {"online": ok}


@app.get("/api/workers/{wid}/screenshot")
def screenshot(wid: str):
    w = _get(wid)
    try:
        frame = w.dev.screencap()
    except Exception:  # noqa: BLE001 — offline shows a placeholder instead of 502
        return Response(content=_placeholder("DEVICE OFFLINE"), media_type="image/jpeg")
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return Response(content=_placeholder("ENCODE ERROR"), media_type="image/jpeg")
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@app.post("/api/workers/{wid}/start")
def start_task(wid: str, body: TaskIn):
    w = _get(wid)
    if not w.start_task(body.model_dump()):
        raise HTTPException(409, "worker already running")
    return {"ok": True}


@app.post("/api/workers/{wid}/login")
def login_worker(wid: str):
    w = _get(wid)
    if not w.start_task({"kind": "login"}):
        raise HTTPException(409, "worker already running")
    return {"ok": True}


@app.post("/api/workers/{wid}/stop")
def stop_task(wid: str):
    w = _get(wid)
    return {"ok": w.stop_task()}
