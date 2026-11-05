"""Dry-run the farm loop: N solo searches with loot reading, no troops dropped."""
import argparse
import json

from core.device import AdbDevice
from tasks.farm import FarmConfig, FarmTask


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="112.126.58.211")
    ap.add_argument("--port", type=int, default=21638)
    ap.add_argument("--n", type=int, default=2)
    ap.add_argument("--mode", choices=["solo", "multi"], default="solo")
    args = ap.parse_args()

    dev = AdbDevice(args.host, args.port)
    dev.ensure()
    cfg = FarmConfig(dry=True, max_searches=args.n, mode=args.mode)
    result = FarmTask(dev, cfg).run()
    print(json.dumps(
        {
            "searches": result.searches,
            "loot": result.loot_readings,
            "errors": result.errors,
        },
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
