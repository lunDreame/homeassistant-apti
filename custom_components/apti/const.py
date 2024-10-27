"""Define constants for AptI."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

DOMAIN = "apti"
VERSION = "1.0.5"

PLATFORMS: list[Platform] = [
    Platform.SENSOR
]

LOGGER = logging.getLogger(__package__)

UPDATE_ME_INTERVAL = timedelta(days=7)
