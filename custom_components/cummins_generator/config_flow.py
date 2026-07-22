"""Config flow for Cummins Generator integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PASSWORD

DOMAIN = "cummins_generator"

CONF_MIN_REQUEST_GAP_MS = "min_request_gap_ms"
DEFAULT_MIN_REQUEST_GAP_MS = 500


class CumminsGeneratorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cummins Generator."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Cummins Generator", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PASSWORD, default="cummins"): str,
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CumminsGeneratorOptionsFlow(config_entry)


class CumminsGeneratorOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Cummins Generator."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_MIN_REQUEST_GAP_MS, DEFAULT_MIN_REQUEST_GAP_MS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_MIN_REQUEST_GAP_MS, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=10000)
                ),
            }),
        )
