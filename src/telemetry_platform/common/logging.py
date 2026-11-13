"""Configuracion de logging a partir de configs/logging.yaml."""
from __future__ import annotations

import logging
import logging.config

from .config import load_yaml

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    cfg = load_yaml("logging.yaml")
    if cfg:
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
