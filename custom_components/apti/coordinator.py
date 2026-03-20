"""Data coordinator for the APTi integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APTiApiError, APTiAuthError, APTiClient
from .const import DOMAIN, PAYMENT_STATE_CODES

_LOGGER = logging.getLogger(__name__)


class APTiDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and merge APTi API payloads."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: APTiClient,
        update_interval,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh all data required by entities."""
        try:
            await self._client.async_login()
        except APTiAuthError as err:
            raise ConfigEntryAuthFailed("APTi authentication failed") from err
        except APTiApiError as err:
            raise UpdateFailed(f"APTi login request failed: {err}") from err

        based_month = dt_util.now().strftime("%Y%m")

        tasks: dict[str, asyncio.Future] = {
            "account_v2": asyncio.create_task(self._client.async_get_user_information_v2()),
            "account_v3": asyncio.create_task(self._client.async_get_user_information_v3()),
            "account_v3_detail": asyncio.create_task(
                self._client.async_get_user_information_detail_v3()
            ),
            "manage_home": asyncio.create_task(self._client.async_get_manage_home()),
            "management_fee": asyncio.create_task(
                self._client.async_get_management_fee_history()
            ),
            "manage_payment_next": asyncio.create_task(
                self._client.async_get_manage_payment_next()
            ),
            "manage_auto_discount": asyncio.create_task(
                self._client.async_get_manage_auto_discount()
            ),
            "manage_energy": asyncio.create_task(self._client.async_get_manage_energy()),
            "parking_visit": asyncio.create_task(self._client.async_get_parking_visit(based_month)),
            "parking_application_status": asyncio.create_task(
                self._client.async_get_parking_application_status()
            ),
            "parking_favorites": asyncio.create_task(self._client.async_get_parking_favorites()),
        }

        for state_code in PAYMENT_STATE_CODES:
            tasks[f"payment_{state_code}"] = asyncio.create_task(
                self._client.async_get_management_payment_history(state_code)
            )

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        raw: dict[str, Any] = {}
        errors: dict[str, str] = {}

        for key, result in zip(tasks, results, strict=False):
            if isinstance(result, APTiAuthError):
                raise ConfigEntryAuthFailed("APTi token rejected") from result
            if isinstance(result, Exception):
                errors[key] = str(result)
                continue
            raw[key] = result

        manage_home = raw.get("manage_home")
        management_fee = raw.get("management_fee")
        if not isinstance(manage_home, dict) and not isinstance(management_fee, dict):
            raise UpdateFailed("APTi core management endpoints returned no data")

        account = self._merge_account(
            raw.get("account_v2"), raw.get("account_v3"), raw.get("account_v3_detail")
        )

        payment_histories: dict[str, list[dict[str, Any]]] = {}
        for state_code in PAYMENT_STATE_CODES:
            rows = raw.get(f"payment_{state_code}")
            payment_histories[state_code] = rows if isinstance(rows, list) else []

        data: dict[str, Any] = {
            "account": account,
            "manage_home": manage_home if isinstance(manage_home, dict) else {},
            "management_fee": management_fee if isinstance(management_fee, dict) else {},
            "manage_payment_next": raw.get("manage_payment_next")
            if isinstance(raw.get("manage_payment_next"), dict)
            else {},
            "manage_auto_discount": raw.get("manage_auto_discount")
            if isinstance(raw.get("manage_auto_discount"), dict)
            else {},
            "manage_energy": raw.get("manage_energy")
            if isinstance(raw.get("manage_energy"), dict)
            else {},
            "parking_visit": raw.get("parking_visit")
            if isinstance(raw.get("parking_visit"), dict)
            else {},
            "parking_application_status": raw.get("parking_application_status")
            if isinstance(raw.get("parking_application_status"), dict)
            else {},
            "parking_favorites": raw.get("parking_favorites")
            if isinstance(raw.get("parking_favorites"), list)
            else [],
            "payment_histories": payment_histories,
            "based_month": based_month,
        }

        if errors:
            _LOGGER.debug("APTi partial refresh errors: %s", errors)
            data["partial_errors"] = errors

        return data

    def _merge_account(
        self,
        account_v2: dict[str, Any] | None,
        account_v3: dict[str, Any] | None,
        account_v3_detail: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge account payloads with v2 as baseline."""
        merged: dict[str, Any] = {}
        if isinstance(account_v2, dict):
            merged.update(account_v2)
        if isinstance(account_v3, dict):
            merged.update(account_v3)
        if isinstance(account_v3_detail, dict):
            merged.update(account_v3_detail)
        return merged
