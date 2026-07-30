"""Config flow for Cummins Generator integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from .client import CannotConnect, InvalidAuth, validate_credentials
from .const import CONF_MIN_REQUEST_GAP_MS, DEFAULT_MIN_REQUEST_GAP_MS

DOMAIN = "cummins_generator"


class CumminsGeneratorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cummins Generator."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_credentials(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Cummins Generator", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PASSWORD, default="cummins"): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CumminsGeneratorOptionsFlow()


class CumminsGeneratorOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Cummins Generator."""

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            new_password = user_input.pop(CONF_PASSWORD)
            if new_password != self.config_entry.data.get(CONF_PASSWORD):
                try:
                    await validate_credentials(
                        self.hass,
                        self.config_entry.data[CONF_HOST],
                        new_password,
                    )
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_PASSWORD: new_password},
                    )
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        current_gap = self.config_entry.options.get(
            CONF_MIN_REQUEST_GAP_MS, DEFAULT_MIN_REQUEST_GAP_MS
        )
        current_password = self.config_entry.data.get(CONF_PASSWORD, "cummins")
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD, default=current_password): str,
                vol.Required(CONF_MIN_REQUEST_GAP_MS, default=current_gap): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=10000)
                ),
            }),
            errors=errors,
        )
