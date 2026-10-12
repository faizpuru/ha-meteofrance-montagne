"""Config flow for Météo-France Montagne integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
)
from .const import (
    API_PORTAL_URL,
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_TOKEN,
    DOMAIN,
    NAME,
    SUBENTRY_TYPE_MASSIF,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


async def _async_validate_token(hass: HomeAssistant, token: str) -> dict[str, str]:
    """Validate the token with a test API call and return form errors."""
    session = async_get_clientsession(hass)
    api = MeteoFranceMontagneApi(session, hass, token)
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


class MassifSelectionMixin:
    """Department then massif selection, shared by the config and subentry flows."""

    _departments_data: dict[str, list[dict[str, Any]]]
    _selected_department: str

    def _get_token(self) -> str:
        """Return the API token used to list the massifs."""
        raise NotImplementedError

    async def _async_create_massif(self, massif: dict[str, Any], title: str):
        """Create the massif once selected."""
        raise NotImplementedError

    async def async_step_department(self, user_input: dict[str, Any] | None = None):
        """Handle department selection."""
        if user_input is not None:
            self._selected_department = user_input["department"]
            return await self.async_step_massif()

        try:
            session = async_get_clientsession(self.hass)
            api = MeteoFranceMontagneApi(session, self.hass, self._get_token())
            self._departments_data = await api.list_massif()
        except MeteoFranceMontagneAuthError:
            return self.async_abort(reason="invalid_auth")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error fetching departments: %s", err)
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="department",
            data_schema=vol.Schema({
                vol.Required("department"): vol.In(
                    sorted(self._departments_data.keys())
                )
            }),
        )

    async def async_step_massif(self, user_input: dict[str, Any] | None = None):
        """Handle massif selection."""
        massifs = self._departments_data[self._selected_department]

        if user_input is not None:
            massif = next(
                massif for massif in massifs
                if massif["title"] == user_input["massif"]
            )
            title = f"{self._selected_department} - {massif['title']}"
            return await self._async_create_massif(massif, title)

        return self.async_show_form(
            step_id="massif",
            data_schema=vol.Schema({
                vol.Required("massif"): vol.In(
                    sorted(massif["title"] for massif in massifs)
                )
            }),
        )


def _massif_data(massif: dict[str, Any]) -> dict[str, Any]:
    """Return the subentry data of a massif."""
    return {CONF_MASSIF: massif["code"], CONF_MASSIF_NAME: massif["title"]}


class MeteoFranceMontagneConfigFlow(MassifSelectionMixin, ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Météo-France Montagne."""

    VERSION = 3
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._token = ""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types supported by this integration."""
        return {SUBENTRY_TYPE_MASSIF: MassifSubentryFlowHandler}

    def _get_token(self) -> str:
        return self._token

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API token, then for a first massif."""
        errors = {}

        if user_input is not None:
            errors = await _async_validate_token(self.hass, user_input[CONF_TOKEN])
            if not errors:
                self._token = user_input[CONF_TOKEN]
                return await self.async_step_department()

        return self.async_show_form(
            step_id="user",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"api_portal_url": API_PORTAL_URL},
        )

    async def _async_create_massif(
        self, massif: dict[str, Any], title: str
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=NAME,
            data={CONF_TOKEN: self._token},
            subentries=[{
                "data": _massif_data(massif),
                "subentry_type": SUBENTRY_TYPE_MASSIF,
                "title": title,
                "unique_id": str(massif["code"]),
            }],
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the API token."""
        entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            errors = await _async_validate_token(self.hass, user_input[CONF_TOKEN])
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user_input[CONF_TOKEN]}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(TOKEN_SCHEMA, entry.data),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected API token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API token."""
        errors = {}

        if user_input is not None:
            errors = await _async_validate_token(self.hass, user_input[CONF_TOKEN])
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_TOKEN: user_input[CONF_TOKEN]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"api_portal_url": API_PORTAL_URL},
        )


class MassifSubentryFlowHandler(MassifSelectionMixin, ConfigSubentryFlow):
    """Add a massif to the API entry."""

    def _get_token(self) -> str:
        return self._get_entry().data[CONF_TOKEN]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start with the department selection."""
        return await self.async_step_department()

    async def _async_create_massif(
        self, massif: dict[str, Any], title: str
    ) -> SubentryFlowResult:
        unique_id = str(massif["code"])
        if any(
            subentry.unique_id == unique_id
            for subentry in self._get_entry().subentries.values()
        ):
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=title, data=_massif_data(massif), unique_id=unique_id
        )
