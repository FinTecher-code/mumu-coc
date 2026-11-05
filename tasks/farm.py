"""Farm loop (M2 skeleton).

Flow: home -> battle menu -> search -> army panel -> (raid) -> end battle -> home.

Dry mode enters a solo map, reads the loot display, then ends the battle —
no troops dropped, no trophies touched. Multiplayer raiding (live filtering by
loot thresholds + deploy strategy) plugs into the same state machine.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from core.device import AdbDevice
from core.numbers import read_region
from core.vision import match_template

ASSETS = Path("assets")

# loot rows in the raid view (960x540)
LOOT_GOLD = (46, 66, 60, 22)
LOOT_ELIXIR = (46, 93, 60, 22)
# multiplayer raid shows bigger loot digits, 3 rows (gold/elixir/dark)
LOOT_MULTI = {
    "gold": (45, 66, 105, 26),
    "elixir": (45, 93, 105, 26),
    "dark": (45, 120, 80, 26),
}
# tapping here (village area outside the attack-menu overlay) closes the menu
MENU_DISMISS = (700, 250)
# known blocking popups: (detector template, button template to tap)
POPUPS = (
    ("dlg_welcome", "btn_ok"),
    ("btn_return_camp", "btn_return_camp"),  # battle settle screen
    ("dlg_star_bonus", "btn_star_ok"),
)


@dataclass
class FarmConfig:
    min_gold: int = 500_000
    min_elixir: int = 500_000
    max_searches: int = 5
    mode: str = "solo"  # solo: riskless dry-run raids; multi: real matchmaking
    dry: bool = True
    deploy: bool = True  # drop troops on qualifying multi raids


@dataclass
class FarmResult:
    searches: int = 0
    raids: int = 0
    loot_readings: list[tuple[int | None, int | None]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# v1 deploy plan for the current army (飞龙x10 / 女皇 / 恶魔王 / 电击法术x7 / 骷髅x1):
# (slot_x, [points to tap]) — troop cards sit in the bottom bar at y≈500.
# Ground points hug the map border ring: the middle of the screen is usually
# covered by buildings where taps are rejected.
DEPLOY_PLAN = [
    (95, [(x, 35) for x in range(80, 880, 80)]
       + [(45, y) for y in range(120, 420, 70)]
       + [(915, y) for y in range(120, 420, 70)]),
    (268, [(120, 390)]),
    (355, [(180, 390)]),
    (440, [(480, 220), (480, 220), (480, 220)]),
    (520, [(480, 250), (480, 250)]),
]


class FarmTask:
    def __init__(
        self,
        device: AdbDevice,
        cfg: FarmConfig,
        cancel_check=None,
    ):
        self.dev = device
        self.cfg = cfg
        self._cancel_check = cancel_check

    def cancelled(self) -> bool:
        return bool(self._cancel_check and self._cancel_check())

    # ---- primitives ----

    def _find(self, tpl: str, threshold: float = 0.85):
        frame = self.dev.screencap()
        return match_template(frame, f"assets/{tpl}.png", threshold)

    def _tap_tpl(self, tpl: str, threshold: float = 0.85, settle: float = 2.0) -> bool:
        hit = self._find(tpl, threshold)
        if not hit:
            return False
        self.dev.tap(hit[0], hit[1])
        time.sleep(settle)
        return True

    def _tpl(self, name: str):
        p = ASSETS / f"{name}.png"
        return f"assets/{name}.png" if p.exists() else None

    def at_home(self) -> bool:
        return self._find("btn_battle", 0.9) is not None

    def go_home(self, timeout: float = 12.0) -> bool:
        """Best-effort return to the home village from benign states."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.at_home():
                return True
            frame = self.dev.screencap()
            handled = False
            for dlg, btn in POPUPS:
                hit = match_template(frame, f"assets/{dlg}.png", 0.8)
                if hit:
                    b = match_template(frame, f"assets/{btn}.png", 0.8)
                    if b:
                        self.dev.tap(b[0], b[1])
                        handled = True
                        break
            if not handled:
                self.dev.tap(*MENU_DISMISS)
            time.sleep(1.5)
        return self.at_home()

    def read_loot(self) -> tuple[int | None, int | None]:
        frame = self.dev.screencap()
        return (
            read_region(frame, LOOT_GOLD),
            read_region(frame, LOOT_ELIXIR),
        )

    def read_loot_multi(self) -> tuple[int | None, int | None, int | None]:
        frame = self.dev.screencap()
        gold = read_region(frame, LOOT_MULTI["gold"])
        elixir = read_region(frame, LOOT_MULTI["elixir"])
        dark = read_region(frame, LOOT_MULTI["dark"])
        return gold, elixir, dark

    # ---- state machine ----

    def run(self) -> FarmResult:
        res = FarmResult()
        if not self.go_home():
            res.errors.append("not at home screen")
            return res
        while res.searches < self.cfg.max_searches and not self.cancelled():
            outcome = self.search_once(res)
            if outcome == "failed":
                break
        if self.cancelled():
            res.errors.append("cancelled")
        return res

    def search_once(self, res: FarmResult) -> str:
        """One entry cycle. Returns 'done'|'skipped'|'failed'."""
        if not self._tap_tpl("btn_battle", settle=2.5):
            res.errors.append("battle button missing")
            return "failed"
        if self.cfg.mode == "solo":
            return self._solo_cycle(res)
        return self._multi_cycle(res)

    def _solo_cycle(self, res: FarmResult) -> str:
        if not self._tap_tpl("btn_solo_tab", settle=2.0):
            res.errors.append("solo tab missing")
            return "failed"
        if not self._tap_tpl("btn_solo_go", settle=10.0):
            res.errors.append("solo attack button missing")
            return "failed"
        res.searches += 1
        gold, elixir = self.read_loot()
        res.loot_readings.append((gold, elixir))
        return self._end_battle(res)

    def _multi_cycle(self, res: FarmResult) -> str:
        if not self._tap_tpl("btn_search", settle=3.0):
            res.errors.append("search button missing")
            return "failed"
        if not self._tap_tpl("btn_attack_go", settle=10.0):
            res.errors.append("attack-go missing")
            return "failed"
        for attempt in range(self.cfg.max_searches):
            if self.cancelled():
                return "skipped"
            res.searches += 1
            time.sleep(2)  # loot panel settle
            gold, elixir, dark = self.read_loot_multi()
            res.loot_readings.append((gold, elixir))
            good = (
                gold is not None
                and elixir is not None
                and gold >= self.cfg.min_gold
                and elixir >= self.cfg.min_elixir
            )
            if good and self.cfg.deploy and not self.cfg.dry:
                res.raids += 1
                self._wait_battle_start()
                self.deploy_army()
                return self._end_battle(res)
            if attempt == self.cfg.max_searches - 1:
                return self._end_battle(res)
            if not self._tap_tpl("btn_next", settle=8.0):
                res.errors.append("next button missing")
                return "failed"
        return "skipped"

    def _wait_battle_start(self, timeout: float = 45.0) -> bool:
        """Raids open with a ~29s countdown; deploy taps are ignored until it ends.

        The 1x speed button appears once deployment unlocks.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self.dev.screencap()
            if match_template(frame, "assets/btn_1x.png", 0.8):
                return True
            time.sleep(2)
        return False

    def deploy_army(self, plan: list | None = None) -> None:
        for slot_x, points in plan or DEPLOY_PLAN:
            if self.cancelled():
                return
            self.dev.tap(slot_x, 500)
            time.sleep(0.6)
            for x, y in points:
                self.dev.tap(x, y)
                time.sleep(0.45)

    def _end_battle(self, res: FarmResult) -> str:
        time.sleep(3)  # let loot panel settle / transition flash pass
        for _ in range(3):
            if self._tap_tpl("btn_end_battle", settle=2.0):
                break
            time.sleep(1)
        # possible confirm dialog, then possible settle screen, then home
        for _ in range(12):
            if self.at_home():
                return "done"
            frame = self.dev.screencap()
            for name in ("btn_confirm", "btn_return_camp", "btn_return_home", "btn_end_battle"):
                path = self._tpl(name)
                if not path:
                    continue
                hit = match_template(frame, path, 0.85)
                if hit:
                    self.dev.tap(hit[0], hit[1])
                    break
            time.sleep(1.5)
        if self.at_home():
            return "done"
        res.errors.append("did not return home after battle")
        return "failed"
