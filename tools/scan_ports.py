"""Discover live MuMu instances on the Windows host by probing ADB ports.

MuMu12 default series: 16384, 16416, 16448 ... (+32 per instance, up to ~16576).
Older series: 5555-5599 (odd), 7555. Custom ports (like 21638) can be probed too.

Usage:
  PYTHONPATH=. python tools/scan_ports.py --host 112.126.58.211
  PYTHONPATH=. python tools/scan_ports.py --host 112.126.58.211 --extra 21638
"""
import argparse
import subprocess
import socket


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def adb_try_connect(serial: str) -> str | None:
    try:
        p = subprocess.run(
            ["adb", "connect", serial], capture_output=True, timeout=8
        )
        out = (p.stdout + p.stderr).decode(errors="ignore")
        if "connected" in out and "cannot" not in out.lower():
            q = subprocess.run(
                ["adb", "-s", serial, "shell", "echo", "ok"],
                capture_output=True, timeout=8,
            )
            if q.returncode == 0 and b"ok" in q.stdout:
                return out.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--extra", action="append", default=[],
                    help="additional custom ports to probe")
    args = ap.parse_args()

    ports = set(range(16384, 16577, 32)) | set(range(5555, 5600, 2)) | {7555}
    ports |= {int(p) for p in args.extra}

    print(f"probing {len(ports)} ports on {args.host} ...")
    open_ports = [p for p in sorted(ports) if port_open(args.host, p)]
    print(f"tcp open: {open_ports}")
    alive = []
    for p in open_ports:
        serial = f"{args.host}:{p}"
        if adb_try_connect(serial):
            alive.append(serial)
            print(f"  ADB ALIVE  {serial}")
        else:
            print(f"  tcp only   {serial} (not adb / busy)")
    print(f"\n{len(alive)} live instance(s): {alive}")


if __name__ == "__main__":
    main()
