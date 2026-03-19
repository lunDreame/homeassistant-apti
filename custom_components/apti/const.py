"""Constants for the APTi integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "apti"
NAME = "APTi"
MANUFACTURER = "APTi"
DEFAULT_SCAN_INTERVAL_MINUTES = 10
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)
API_BASE_URL = "https://api-main.apti.co.kr"
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
PAYMENT_STATE_CODES: tuple[str, ...] = ("001", "002", "003", "004", "005")

