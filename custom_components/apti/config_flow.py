"""Config flow for APTi integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APTiApiError, APTiAuthError, APTiClient
from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate_login(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate account credentials against APTi API."""
    client = APTiClient(
        async_get_clientsession(hass),
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )
    login_payload = await client.async_login(force=True)

    info: dict[str, Any] | None = None

    try:
        info_v2 = await client.async_get_user_information_v2()
    except APTiApiError as err:
        _LOGGER.debug("APTi v2 profile lookup failed during config validation: %s", err)
        info_v2 = None
    if isinstance(info_v2, dict):
        info = info_v2

    if info is None:
        info_v3 = await client.async_get_user_information_v3()
        if isinstance(info_v3, dict):
            info = info_v3

    if info is None:
        info_v3_detail = await client.async_get_user_information_detail_v3()
        if isinstance(info_v3_detail, dict):
            info = info_v3_detail

    if info is None:
        info = {"userId": login_payload.get("userId") or data[CONF_USERNAME]}

    return data, info


def _build_entry_title(info: dict[str, Any], fallback: str) -> str:
    """Create a readable config entry title."""
    apt_name = str(info.get("aptName") or "").strip()
    dong = str(info.get("dong") or info.get("aptDong") or "").strip()
    ho = str(info.get("ho") or info.get("aptHo") or "").strip()
    if apt_name and dong and ho:
        return f"{apt_name} {dong}-{ho}"
    if apt_name:
        return apt_name
    return fallback


class APTiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for APTi."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow."""
        return APTiOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data, info = await _validate_login(self.hass, user_input)
            except APTiAuthError:
                errors["base"] = "invalid_auth"
            except APTiApiError as err:
                _LOGGER.warning("APTi login validation failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                unique_id = str(info.get("userId") or data[CONF_USERNAME])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=_build_entry_title(info, data[CONF_USERNAME]),
                    data={
                        CONF_USERNAME: data[CONF_USERNAME],
                        CONF_PASSWORD: data[CONF_PASSWORD],
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )


class APTiOptionsFlow(OptionsFlow):
    """Options flow for APTi."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL, 
                    default=self._config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        DEFAULT_SCAN_INTERVAL_MINUTES,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=120)),
            }),
        )
