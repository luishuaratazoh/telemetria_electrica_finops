"""Simulador centralizado: genera datos crudos de todos los activos y los entrega al gateway edge.
No escribe en la base de datos (separacion de responsabilidades)."""
from __future__ import annotations

import json
import random
import threading
import time
from pathlib import Path

from telemetry_platform.common.config import load_yaml, resolve_path
from telemetry_platform.common.constants import DEVICE_BREAKER, DEVICE_METER, DEVICE_RELAY
from telemetry_platform.common.logging import get_logger
from telemetry_platform.common.timestamps import to_iso, utcnow
from telemetry_platform.edge.main import EdgeGateway

from .breaker_generator import BreakerSimulator
from .event_generator import EventGenerator
from .meter_generator import MeterSimulator
from .oscillography_generator import generate_comtrade
from .relay_generator import RelaySimulator
from .settings_generator import SettingsSimulator
from .substation_generator import Topology, load_factor

log = get_logger(__name__)


class Simulator:
    def __init__(self, topology: Topology, gateway: EdgeGateway, sim_cfg: dict | None = None) -> None:
        self.cfg = sim_cfg or load_yaml("simulator.yaml")
        self.topology = topology
        self.gateway = gateway
        seed = self.cfg.get("seed", 42)
        rng = random.Random(seed)
        self.tz = self.cfg.get("timezone_offset_hours", -5)
        self.profile_of = {s.code: s.load_profile for s in topology.substations}
        self.kv_of = {s.code: s.base_kv for s in topology.substations}

        self.breakers = {
            d.asset_id: BreakerSimulator(d.asset_id, d.substation_code) for d in topology.by_type(DEVICE_BREAKER)
        }
        self.relays = {}
        for d in topology.by_type(DEVICE_RELAY):
            brk = self.breakers.get(topology.relay_to_breaker.get(d.asset_id, ""))
            self.relays[d.asset_id] = RelaySimulator(
                d.asset_id, d.substation_code, self.kv_of[d.substation_code], d.nominal_current, rng, brk
            )
        self.meters = [
            MeterSimulator(d.asset_id, d.substation_code, d.base_kw, rng) for d in topology.by_type(DEVICE_METER)
        ]
        self.events = EventGenerator(
            self.relays, self.breakers, rng, self.cfg["fault_probability_per_tick"], self.cfg["breaker_reclose_ticks"]
        )
        self.settings = SettingsSimulator(
            {a: (r.substation, r.nominal_current) for a, r in self.relays.items()}, rng
        )
        self.rng = rng
        self.osc_dir = resolve_path(self.cfg["oscillography_dir"])
        self.tick_no = 0

    # ------------------------------------------------------------------
    def start(self) -> None:
        now = utcnow()
        if self.cfg.get("publish_initial_settings", True):
            for msg in self.settings.initial(now):
                self.gateway.handle_settings(msg)
        for b in self.breakers.values():
            self.gateway.handle_breaker(b.state(now))
        log.info(
            "Simulador listo: %d subestaciones, %d reles, %d medidores, %d interruptores",
            len(self.topology.substations), len(self.relays), len(self.meters), len(self.breakers),
        )

    def tick(self) -> None:
        now = utcnow()
        self.tick_no += 1

        lf_cache: dict[str, float] = {p: load_factor(p, now, self.tz) for p in set(self.profile_of.values())}

        events, breaker_changes, trips = self.events.tick(now)
        for ev in events:
            self.gateway.handle_event(ev)
        for st in breaker_changes:
            self.gateway.handle_breaker(st)
        for trip in trips:
            self._write_oscillography(trip)

        for relay in self.relays.values():
            self.gateway.handle_relay(relay.generate_measurement(now, lf_cache[self.profile_of[relay.substation]]))

        if self.tick_no % self.cfg["meter_profile_every_ticks"] == 0:
            interval = self.cfg["profile_interval_minutes"]
            for m in self.meters:
                self.gateway.handle_meter(m.generate_profile(now, lf_cache[self.profile_of[m.substation]], interval))

        if self.tick_no % 60 == 0:  # estado periodico de interruptores
            for b in self.breakers.values():
                self.gateway.handle_breaker(b.state(now))

        for msg in self.settings.maybe_change(now, self.cfg["settings_change_probability_per_tick"]):
            self.gateway.handle_settings(msg)

        self.gateway.collect_files()

    def _write_oscillography(self, trip) -> None:
        relay = trip.relay
        base = f"{relay.asset_id}_{trip.time.strftime('%Y%m%dT%H%M%S')}"
        folder = self.osc_dir / relay.substation
        folder.mkdir(parents=True, exist_ok=True)
        cfg_txt, dat_txt = generate_comtrade(
            relay.substation, relay.asset_id, trip.time, relay.nominal_current, trip.peak_current,
            relay.nominal_kv, self.rng,
        )
        (folder / f"{base}.cfg").write_text(cfg_txt, encoding="utf-8")
        (folder / f"{base}.dat").write_text(dat_txt, encoding="utf-8")
        # el sidecar .json se escribe al final: es la senal de "registro completo" para el colector
        (folder / f"{base}.json").write_text(
            json.dumps({"asset_id": relay.asset_id, "substation": relay.substation, "event_time": to_iso(trip.time),
                        "peak_current_a": round(trip.peak_current, 1)}),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    def run(self, max_ticks: int | None = None, stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        self.start()
        period = self.cfg["tick_seconds"]
        next_t = time.monotonic()
        while not stop_event.is_set() and (max_ticks is None or self.tick_no < max_ticks):
            t0 = time.monotonic()
            self.tick()
            elapsed = time.monotonic() - t0
            next_t += period
            wait = next_t - time.monotonic()
            if wait > 0:
                stop_event.wait(wait)
            else:
                log.warning("Tick %d tardo %.2fs (periodo %ss): el generador no sostiene el ritmo", self.tick_no, elapsed, period)
                next_t = time.monotonic()
        self.gateway.close()
