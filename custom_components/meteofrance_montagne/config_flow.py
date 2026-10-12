"""Config flow for Météo-France Montagne integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
)
from .const import DOMAIN, CONF_TOKEN, CONF_MASSIF, API_PORTAL_URL

_LOGGER = logging.getLogger(__name__)


class MeteoFranceMontagneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Météo-France Montagne."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow."""
        self._departments_data = {}
        self._selected_department = None
        self._parent_entry_id = None

    async def _async_validate_token(self, token: str) -> dict[str, str]:
        """Validate the token with a test API call and return form errors."""
        session = async_get_clientsession(self.hass)
        api = MeteoFranceMontagneApi(session, self.hass, token)
        try:
            await api.rose_pentes(2)  # Test API call
        except MeteoFranceMontagneAuthError:
            return {"base": "invalid_auth"}
        except MeteoFranceMontagneApiError as err:
            _LOGGER.error("Error validating token: %s", err)
            return {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error validating token")
            return {"base": "unknown"}
        return {}

    async def _async_update_token(
        self, parent_entry: config_entries.ConfigEntry, token: str
    ) -> None:
        """Store the new token and reload every massif using it."""
        self.hass.config_entries.async_update_entry(
            parent_entry,
            data={CONF_TOKEN: token}
        )
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("parent_entry_id") == parent_entry.entry_id:
                await self.hass.config_entries.async_reload(entry.entry_id)

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
            errors = await self._async_validate_token(token)
            if not errors:
                # Create the API configuration entry
                return self.async_create_entry(
                    title="API Météo-France Montagne",
                    data={CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="api",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
            description_placeholders={
                "api_portal_url": API_PORTAL_URL
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

            # Validate token, then update it for all massifs
            errors = await self._async_validate_token(token)
            if not errors:
                await self._async_update_token(entry, token)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN, default=entry.data.get(CONF_TOKEN, "")): str,
            }),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle a rejected API token, raised by a massif entry."""
        self._parent_entry_id = entry_data["parent_entry_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for a new API token."""
        parent_entry = self.hass.config_entries.async_get_entry(self._parent_entry_id)
        if not parent_entry:
            return self.async_abort(reason="no_api")

        errors = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]

            errors = await self._async_validate_token(token)
            if not errors:
                await self._async_update_token(parent_entry, token)
                # Other massifs sharing this token opened their own reauth flow
                for flow in self._async_in_progress():
                    if (
                        flow["flow_id"] != self.flow_id
                        and flow["context"].get("source") == config_entries.SOURCE_REAUTH
                    ):
                        self.hass.config_entries.flow.async_abort(flow["flow_id"])
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_TOKEN): str,
            }),
            errors=errors,
            description_placeholders={
                "api_portal_url": API_PORTAL_URL
            }
        )
