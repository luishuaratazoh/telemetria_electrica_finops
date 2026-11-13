from telemetry_platform.edge.deadband import DeadbandFilter
from telemetry_platform.edge.normalizer import normalize_meter, normalize_relay
from telemetry_platform.edge.validator import assess_quality


def test_normalize_relay_common_schema():
    raw = {"relay": "SEL_751_00001", "substation": "SE_001", "ts": "2026-11-11T15:00:00.000Z",
           "voltage_kv": 10.0, "current_a": 150.0, "active_power_kw": 2400.0,
           "reactive_power_kvar": 800.0, "frequency_hz": 60.0}
    out = normalize_relay(raw)
    assert len(out) == 5
    p = next(m for m in out if m["measurement_type"] == "active_power")
    assert p["unit"] == "kW" and p["asset_id"] == "SEL_751_00001" and p["quality"] == "GOOD"


def test_normalize_meter_profile():
    out = normalize_meter({"meter": "MTR_000001", "substation": "SE_001", "ts": "t", "kw": 2.0, "kwh": 0.5})
    assert out["demand"] == 2.0 and out["active_energy"] == 0.5


def test_quality():
    assert assess_quality("voltage", 10.0) == "GOOD"
    assert assess_quality("voltage", 8.0) == "SUSPECT"
    assert assess_quality("voltage", 99.0) == "BAD"
    assert assess_quality("frequency", float("nan")) == "BAD"


def test_deadband_suppresses_small_changes_and_heartbeat():
    f = DeadbandFilter({"voltage": 1.0}, heartbeat_seconds=60)
    assert f.should_publish("A", "voltage", 10.0, now=0)
    assert not f.should_publish("A", "voltage", 10.01, now=1)      # cambio 0.1% < 1%
    assert f.should_publish("A", "voltage", 10.5, now=2)           # cambio 5%
    assert f.should_publish("A", "voltage", 10.5, now=100)         # heartbeat
    assert f.should_publish("A", "current", 1.0, now=0)            # sin umbral -> siempre
