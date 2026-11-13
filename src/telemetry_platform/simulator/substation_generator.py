"""Topologia: subestaciones y dispositivos (determinista por semilla)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from telemetry_platform.common.config import load_yaml
from telemetry_platform.common.constants import DEVICE_BREAKER, DEVICE_METER, DEVICE_RELAY, SYSTEM_VOLTAGE_KV

REGIONS = [
    ("Lima", -12.05, -77.04), ("Arequipa", -16.40, -71.54), ("Cusco", -13.53, -71.97),
    ("Piura", -5.19, -80.63), ("Trujillo", -8.11, -79.03), ("Junin", -12.07, -75.21),
    ("Ica", -14.07, -75.73), ("Lambayeque", -6.77, -79.84),
]

# Factor de carga por hora local (0-23)
LOAD_PROFILES: dict[str, list[float]] = {
    "residential": [0.45, 0.40, 0.38, 0.37, 0.40, 0.50, 0.65, 0.75, 0.70, 0.65, 0.62, 0.62,
                    0.65, 0.65, 0.63, 0.65, 0.70, 0.85, 1.00, 0.98, 0.90, 0.80, 0.65, 0.52],
    "industrial": [0.70, 0.70, 0.70, 0.72, 0.75, 0.82, 0.92, 1.00, 1.00, 1.00, 1.00, 0.98,
                   0.92, 0.98, 1.00, 1.00, 0.98, 0.90, 0.85, 0.80, 0.76, 0.74, 0.72, 0.70],
    "commercial": [0.35, 0.33, 0.32, 0.32, 0.34, 0.40, 0.55, 0.75, 0.92, 1.00, 1.00, 0.98,
                   0.95, 0.96, 1.00, 1.00, 0.97, 0.92, 0.85, 0.75, 0.60, 0.48, 0.40, 0.37],
}


def load_factor(profile: str, now: datetime, tz_offset_hours: float = -5.0) -> float:
    """Interpola linealmente el perfil horario."""
    local = now.astimezone(timezone(timedelta(hours=tz_offset_hours)))
    prof = LOAD_PROFILES[profile]
    h = local.hour + local.minute / 60 + local.second / 3600
    i = int(math.floor(h)) % 24
    frac = h - math.floor(h)
    return prof[i] * (1 - frac) + prof[(i + 1) % 24] * frac


@dataclass
class Substation:
    code: str
    name: str
    region: str
    latitude: float
    longitude: float
    load_profile: str
    base_kv: float = SYSTEM_VOLTAGE_KV


@dataclass
class Device:
    asset_id: str
    substation_code: str
    device_type: str
    manufacturer: str
    model: str
    nominal_current: float = 0.0   # solo reles
    base_kw: float = 0.0           # solo medidores


@dataclass
class Topology:
    substations: list[Substation]
    devices: list[Device]
    relay_to_breaker: dict[str, str] = field(default_factory=dict)

    def by_type(self, device_type: str) -> list[Device]:
        return [d for d in self.devices if d.device_type == device_type]


def build_topology(counts: dict[str, int], seed: int = 42) -> Topology:
    rng = random.Random(seed)
    dev_cfg = load_yaml("devices.yaml")
    n = counts["substations"]
    profiles = list(LOAD_PROFILES)

    subs: list[Substation] = []
    for i in range(1, n + 1):
        region, lat, lon = REGIONS[(i - 1) % len(REGIONS)]
        subs.append(
            Substation(
                code=f"SE_{i:03d}",
                name=f"Subestacion {region} {i:02d}",
                region=region,
                latitude=round(lat + rng.uniform(-0.3, 0.3), 5),
                longitude=round(lon + rng.uniform(-0.3, 0.3), 5),
                load_profile=profiles[rng.randrange(len(profiles))],
            )
        )

    devices: list[Device] = []

    def distribute(total: int, dtype: str, prefix: str, width: int) -> dict[str, list[str]]:
        cfg = dev_cfg[dtype]
        base, extra = divmod(total, n)
        idx = 1
        per_sub: dict[str, list[str]] = {}
        for si, sub in enumerate(subs):
            for _ in range(base + (1 if si < extra else 0)):
                asset = f"{prefix}_{idx:0{width}d}"
                d = Device(asset, sub.code, dtype, cfg["manufacturer"], rng.choice(cfg["models"]))
                if dtype == DEVICE_RELAY:
                    d.nominal_current = round(rng.uniform(120, 250), 1)
                elif dtype == DEVICE_METER:
                    d.base_kw = round(rng.uniform(0.5, 6.0), 2)
                devices.append(d)
                per_sub.setdefault(sub.code, []).append(asset)
                idx += 1
        return per_sub

    relays = distribute(counts["relays"], DEVICE_RELAY, dev_cfg[DEVICE_RELAY]["prefix"], 5)
    distribute(counts["meters"], DEVICE_METER, dev_cfg[DEVICE_METER]["prefix"], 6)
    breakers = distribute(counts["breakers"], DEVICE_BREAKER, dev_cfg[DEVICE_BREAKER]["prefix"], 4)

    relay_to_breaker: dict[str, str] = {}
    for code, relay_ids in relays.items():
        brks = breakers.get(code)
        if not brks:
            continue
        for j, rid in enumerate(relay_ids):
            relay_to_breaker[rid] = brks[j % len(brks)]
    return Topology(subs, devices, relay_to_breaker)
