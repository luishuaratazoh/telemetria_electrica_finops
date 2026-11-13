"""Constantes compartidas: variables electricas, unidades y rangos de validacion."""

# nombre -> (id en master.variables, unidad)
VARIABLES: dict[str, tuple[int, str]] = {
    "voltage": (1, "kV"),
    "current": (2, "A"),
    "active_power": (3, "kW"),
    "reactive_power": (4, "kvar"),
    "apparent_power": (5, "kVA"),
    "frequency": (6, "Hz"),
    "energy": (7, "kWh"),
    "demand": (8, "kW"),
}
UNITS = {name: unit for name, (_, unit) in VARIABLES.items()}

DEVICE_RELAY = "protection_relay"
DEVICE_METER = "smart_meter"
DEVICE_BREAKER = "breaker"

QUALITY_GOOD = "GOOD"
QUALITY_SUSPECT = "SUSPECT"
QUALITY_BAD = "BAD"

# Limites fisicos: fuera de este rango el dato es BAD (error de sensor/comunicacion).
HARD_RANGES: dict[str, tuple[float, float]] = {
    "voltage": (0.0, 40.0),
    "current": (0.0, 5000.0),
    "active_power": (-100_000.0, 100_000.0),
    "reactive_power": (-100_000.0, 100_000.0),
    "apparent_power": (0.0, 100_000.0),
    "frequency": (45.0, 65.0),
    "energy": (0.0, 1_000_000.0),
    "demand": (0.0, 100_000.0),
}

# Banda operativa normal (red de 10 kV, 60 Hz): fuera de ella el dato es SUSPECT (posible evento).
NORMAL_RANGES: dict[str, tuple[float, float]] = {
    "voltage": (9.5, 10.5),
    "frequency": (59.5, 60.5),
}

SYSTEM_VOLTAGE_KV = 10.0
SYSTEM_FREQUENCY_HZ = 60.0
