"""Define constants for AptI."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "apti"
VERSION = "1.0.0"

PLATFORMS: list[Platform] = [
    Platform.SENSOR
]

LOGGER = logging.getLogger(__package__)

UPDATE_SESSION_INTERVAL = timedelta(minutes=20)
UPDATE_MAINT_INTERVAL = timedelta(hours=24)
UPDATE_ENERGY_INTERVAL = timedelta(hours=24)
