from telemetry_platform.finops import cost_model as cm

FLEET = {"relays": 4000, "meters": 50000, "breakers": 1000, "relay_variables": 5,
         "relay_sample_seconds": 5, "meter_profile_minutes": 15, "trips_per_relay_per_month": 0.5}
PARAMS = dict(retention_days=30, compress_after_days=2, compression_ratio=10, object_retention_days=90,
              consumer_groups=1)
SIZING = cm.Sizing(8, 32, 8)


def test_estimate_scales_with_volume():
    small = cm.Workload(1e6, 200, 1e6, 90)
    big = cm.Workload(1e7, 200, 1e7, 90)
    t_small = cm.total(cm.estimate(small, cm.Sizing(1, 4, 1), **PARAMS))
    t_big = cm.total(cm.estimate(big, cm.Sizing(1, 4, 1), **PARAMS))
    assert t_big > t_small


def test_messaging_cost_formula():
    w = cm.Workload(messages_per_day=1_000_000, avg_message_bytes=1024**3 / 1_000_000 / 30, rows_per_day=0, bytes_per_row=0)
    line = next(ln for ln in cm.estimate(w, cm.Sizing(0, 0, 0), {"messaging_ingest": 0.04}, **PARAMS) if ln.resource == "messaging_ingest")
    assert abs(line.quantity - 2.0) < 1e-6   # 1 GiB/mes publicado + 1 GiB entregado
    assert abs(line.cost_usd - 0.08) < 1e-6


def test_compression_reduces_db_storage():
    w = cm.Workload(1e6, 200, 1e6, 90)
    no_c = next(l for l in cm.estimate(w, SIZING, **{**PARAMS, "compression_ratio": 1}) if l.resource == "db_storage")
    c = next(l for l in cm.estimate(w, SIZING, **PARAMS) if l.resource == "db_storage")
    assert c.quantity < no_c.quantity


def test_deadband_saving_lowers_full_fleet_cost():
    w0 = cm.full_fleet_workload(FLEET, 0.0, 230, 90, 14000)
    w5 = cm.full_fleet_workload(FLEET, 0.5, 230, 90, 14000)
    assert w5.messages_per_day < w0.messages_per_day
    assert cm.total(cm.estimate(w5, SIZING, **PARAMS)) < cm.total(cm.estimate(w0, SIZING, **PARAMS))


def test_what_if_levers_sorted_and_non_negative():
    w = cm.full_fleet_workload(FLEET, 0.5, 230, 90, 14000)
    levers = cm.what_if(w, SIZING, FLEET, 0.5, None, PARAMS)
    savings = [l["saving_usd_month"] for l in levers]
    assert savings == sorted(savings, reverse=True)
    assert all(s >= -0.01 for s in savings)
