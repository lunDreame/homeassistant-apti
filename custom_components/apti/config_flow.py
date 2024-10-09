"""Config flow to configure APT.i."""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv

from .apti import APTiAPI
from .const import DOMAIN, LOGGER


class APTiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for APT.i."""

    VERSION = 1

    async def async_step_user(
        self, 
        user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            
            api = APTiAPI(self.hass, None)
            await api.login(username, password)

            if not api.logged_in:
                errors["base"] = "login_failed"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }),
            errors=errors
        )
