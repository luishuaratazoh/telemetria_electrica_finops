from datetime import datetime, timedelta

import polars as pl

from telemetry_platform.analytics.anomaly_detection import zscore_anomalies
from telemetry_platform.processing.aggregation import aggregate_frame
from telemetry_platform.processing.deduplication import deduplicate_indices
from telemetry_platform.processing.quality import MeasurementMsg, parse_messages


def test_deduplicate_keeps_last():
    keys = [(1, 1, 100), (1, 1, 100), (2, 1, 100), (1, 1, 101)]
    assert deduplicate_indices(keys) == [1, 2, 3]


def test_parse_rejects_bad_messages():
    good = {"asset_id": "A", "substation_id": "S", "device_type": "protection_relay", "measurement_type": "voltage",
            "value": 10.0, "unit": "kV", "event_time": "2026-11-11T15:00:00Z", "quality": "GOOD", "source": "x"}
    bad = {**good, "value": "abc"}
    valid, rejected = parse_messages(MeasurementMsg, [good, bad])
    assert len(valid) == 1 and len(rejected) == 1


def test_aggregate_frame_hourly():
    t0 = datetime(2026, 1, 1, 0, 0)
    df = pl.DataFrame({
        "event_time": [t0 + timedelta(minutes=m) for m in (0, 20, 40, 70)],
        "device_id": [1, 1, 1, 1], "variable_id": [1, 1, 1, 1], "value": [1.0, 2.0, 3.0, 10.0]})
    out = aggregate_frame(df).sort("event_time")
    assert out["samples"].to_list() == [3, 1]
    assert out["avg_value"].to_list() == [2.0, 10.0]


def test_zscore_detects_spike():
    vals = [10.0 + (i % 3) * 0.1 for i in range(60)] + [50.0]
    out = zscore_anomalies(pl.DataFrame({"value": vals}), window=20, threshold=3.0)
    assert out.height >= 1 and 50.0 in out["value"].to_list()
