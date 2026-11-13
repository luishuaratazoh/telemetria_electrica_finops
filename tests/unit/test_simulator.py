import random
from datetime import datetime, timezone

from telemetry_platform.simulator.oscillography_generator import generate_comtrade
from telemetry_platform.simulator.relay_generator import RelaySimulator
from telemetry_platform.simulator.substation_generator import build_topology, load_factor

COUNTS = {"substations": 3, "relays": 30, "meters": 300, "breakers": 12}


def test_topology_counts_and_links():
    t = build_topology(COUNTS, seed=1)
    assert len(t.substations) == 3
    assert len(t.by_type("protection_relay")) == 30
    assert len(t.by_type("smart_meter")) == 300
    assert len(t.by_type("breaker")) == 12
    assert len(t.relay_to_breaker) == 30
    assert len({d.asset_id for d in t.devices}) == len(t.devices)  # ids unicos


def test_topology_deterministic():
    a = build_topology(COUNTS, seed=7)
    b = build_topology(COUNTS, seed=7)
    assert [d.asset_id for d in a.devices] == [d.asset_id for d in b.devices]


def test_load_factor_in_range():
    now = datetime(2026, 11, 11, 23, 0, tzinfo=timezone.utc)
    for p in ("residential", "industrial", "commercial"):
        assert 0.2 < load_factor(p, now) <= 1.0


def test_relay_measurement_physics():
    r = RelaySimulator("SEL_751_00001", "SE_001", 10.0, 200.0, random.Random(1))
    m = r.generate_measurement(datetime.now(timezone.utc), 1.0)
    assert m["active_power_kw"] > 0 and 59 < m["frequency_hz"] < 61
    r.start_fault()
    assert r.generate_measurement(datetime.now(timezone.utc), 1.0)["current_a"] > 400


def test_comtrade_files():
    cfg, dat = generate_comtrade("SE_001", "SEL_751_00001", datetime.now(timezone.utc), 200, 1200, 10.0, random.Random(1))
    assert cfg.startswith("SE_001,SEL_751_00001,1999") and "ASCII" in cfg
    assert len(dat.strip().splitlines()) == 160
