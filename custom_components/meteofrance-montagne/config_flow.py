"""Config flow for Météo France Montagne integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MeteoFranceMontagneApi
from .const import DOMAIN, CONF_TOKEN, CONF_MASSIF

_LOGGER = logging.getLogger(__name__)


class MeteoFranceMontagneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Météo France Montagne."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._departments_data = {}
        self._selected_department = None
        self._parent_entry_id = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - show menu to choose action."""
        # Check if we already have an API configuration (parent) entry
        api_entries = [
            entry for entry in self._async_current_entries()
            if CONF_TOKEN in entry.data
        ]

        # If no API config exists, force creating one
        if not api_entries:
            return await self.async_step_api()

        # If API config exists, go to massif selection
        return await self.async_step_select_api()

    async def async_step_api(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle API configuration (parent entry)."""
        errors = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]

            # Validate token by trying to fetch data
            try:
                session = async_get_clientsession(self.hass)
                api = MeteoFranceMontagneApi(session, self.hass, token)
                await api.rose_pentes(2)  # Test API call

                # Create the API configuration entry
                return self.async_create_entry(
                    title="API Météo France Montagne",
                    data={CONF_TOKEN: token},
                )
            except Exception as err:
                _LOGGER.error("Error validating token: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="api",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
            description_placeholders={
                "description": "Enter your Météo France API token. This will be used for all massifs."
            }
        )

    async def async_step_select_api(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which API configuration to use for this massif."""
        api_entries = [
            entry for entry in self._async_current_entries()
            if CONF_TOKEN in entry.data
        ]

        if not api_entries:
            return await self.async_step_api()

        # If only one API config, use it automatically
        if len(api_entries) == 1:
            self._parent_entry_id = api_entries[0].entry_id
            return await self.async_step_department()

        # Multiple API configs - let user choose
        if user_input is not None:
            self._parent_entry_id = user_input["api"]
            return await self.async_step_department()

        return self.async_show_form(
            step_id="select_api",
            data_schema=vol.Schema({
                vol.Required("api"): vol.In({
                    entry.entry_id: entry.title
                    for entry in api_entries
                })
            })
        )

    async def async_step_department(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle department selection."""
        errors = {}

        # Get parent entry to retrieve token
        parent_entry = self.hass.config_entries.async_get_entry(self._parent_entry_id)
        if not parent_entry:
            return self.async_abort(reason="no_api")

        token = parent_entry.data.get(CONF_TOKEN)

        if user_input is None:
            # Fetch departments list
            try:
                session = async_get_clientsession(self.hass)
                api = MeteoFranceMontagneApi(session, self.hass, token)
                self._departments_data = await api.list_massif()

                return self.async_show_form(
                    step_id="department",
                    data_schema=vol.Schema({
                        vol.Required("department"): vol.In(
                            sorted(list(self._departments_data.keys()))
                        )
                    }),
                    errors=errors,
                )

            except Exception as err:
                _LOGGER.error("Error fetching departments: %s", err)
                errors["base"] = "cannot_connect"
                return self.async_abort(reason="cannot_connect")

        else:
            # User selected a department
            self._selected_department = user_input["department"]
            return await self.async_step_massif()

    async def async_step_massif(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle massif selection."""
        errors = {}

        if user_input is None:
            # Show massifs for selected department
            massifs = self._departments_data[self._selected_department]
            massif_titles = [massif["title"] for massif in massifs]

            return self.async_show_form(
                step_id="massif",
                data_schema=vol.Schema({
                    vol.Required("massif"): vol.In(sorted(massif_titles))
                }),
                errors=errors,
            )

        else:
            # User selected a massif
            title = user_input["massif"]
            name = self._selected_department + " - " + title

            # Find corresponding code
            selected_massif = next(
                massif for massif in self._departments_data[self._selected_department]
                if massif["title"] == title
            )

            # Check for duplicates
            await self.async_set_unique_id(f"{self._parent_entry_id}_{selected_massif['code']}")
            self._abort_if_unique_id_configured()

            # Create child entry
            return self.async_create_entry(
                title=name,
                data={
                    CONF_MASSIF: selected_massif["code"],
                    "massif_name": title,
                    "parent_entry_id": self._parent_entry_id,
                },
            )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the API token."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if not entry or CONF_TOKEN not in entry.data:
            return self.async_abort(reason="not_api")

        errors = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]

            # Validate token
            try:
                session = async_get_clientsession(self.hass)
                api = MeteoFranceMontagneApi(session, self.hass, token)
                await api.rose_pentes(2)  # Test API call

                # Update the entry
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={CONF_TOKEN: token}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            except Exception as err:
                _LOGGER.error("Error validating token: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")): str,
            }),
            errors=errors,
        )
