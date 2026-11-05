"""Per-account login-state snapshots for serial account switching.

The Tencent MSDK caches the QQ/WeChat OAuth grant inside the game's data dir.
Snapshotting those (tiny) dirs captures the whole login identity; restoring a
snapshot and relaunching the game re-enters the village as that account —
no QR scan needed until the underlying token expires.

Usage:
  PYTHONPATH=. python tools/account_snap.py save su3        # current state -> accounts/su3.tar
  PYTHONPATH=. python tools/account_snap.py load su3        # restore + relaunch game
  PYTHONPATH=. python tools/account_snap.py list
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HOST = "112.126.58.211"
PORT = 21638
PKG = "com.tencent.tmgp.supercell.clashofclans"
SNAP_DIRS = "shared_prefs files app_msdk databases app_databases save"
TMP = "/data/local/tmp/coc_snap.tar"
ACCOUNTS = Path("accounts")


def adb(*args: str, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", "-s", f"{HOST}:{PORT}", *args], capture_output=True, timeout=timeout
    )


def sh(cmd: str, timeout: float = 60) -> str:
    p = adb("shell", cmd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore"))
    return p.stdout.decode(errors="ignore")


def app_uid() -> str:
    out = sh(f"stat -c '%U:%G' /data/data/{PKG}")
    return out.strip()


def save(name: str) -> None:
    ACCOUNTS.mkdir(exist_ok=True)
    sh(f"cd /data/data/{PKG} && tar cf {TMP} {SNAP_DIRS}", timeout=120)
    p = adb("pull", TMP, str(ACCOUNTS / f"{name}.tar"), timeout=120)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore"))
    sh(f"rm -f {TMP}")
    size = (ACCOUNTS / f"{name}.tar").stat().st_size
    print(f"saved accounts/{name}.tar ({size/1024:.0f} KB)")


def load(name: str) -> None:
    tar = ACCOUNTS / f"{name}.tar"
    if not tar.exists():
        sys.exit(f"snapshot not found: {tar}")
    uid = app_uid()
    sh(f"am force-stop {PKG}")
    time.sleep(2)
    p = adb("push", str(tar), TMP, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore"))
    sh(
        f"cd /data/data/{PKG} && rm -rf {SNAP_DIRS} && tar xf {TMP} "
        f"&& chown -R {uid} {SNAP_DIRS} && chmod -R u+rwX {SNAP_DIRS} && rm -f {TMP}",
        timeout=120,
    )
    sh(f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    print(f"restored {name}, game relaunching")


def list_snaps() -> None:
    for f in sorted(ACCOUNTS.glob("*.tar")):
        print(f"{f.stem:20s} {f.stat().st_size/1024:8.0f} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["save", "load", "list"])
    ap.add_argument("name", nargs="?")
    args = ap.parse_args()
    if args.cmd == "save":
        save(args.name)
    elif args.cmd == "load":
        load(args.name)
    else:
        list_snaps()
