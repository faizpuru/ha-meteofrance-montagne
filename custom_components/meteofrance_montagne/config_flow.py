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
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util
from meteofrance_montagne import (
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
    MeteoFranceNivoApi,
    in_massif,
)
from .const import (
    API_PORTAL_URL,
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_STATIONS,
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
    api = MeteoFranceMontagneApi(session, token)
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


async def _async_massif_stations(
    hass: HomeAssistant, massif: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Return the observation stations inside a massif."""
    api = MeteoFranceNivoApi(async_get_clientsession(hass))
    stations = await api.stations(dt_util.utcnow().year)
    return {
        station_id: station
        for station_id, station in stations.items()
        if in_massif(station["longitude"], station["latitude"], massif.get("geometry"))
    }


def _stations_schema(stations: dict[str, dict[str, Any]]) -> vol.Schema:
    """Return the form checking the stations of a massif."""
    options = [
        SelectOptionDict(
            value=station_id,
            label=f"{station['nom']} ({station['altitude']} m)"
            if station.get("altitude") is not None
            else station["nom"],
        )
        for station_id, station in stations.items()
    ]
    options.sort(key=lambda option: option["label"].casefold())
    return vol.Schema({
        vol.Optional(CONF_STATIONS, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=options, multiple=True, mode=SelectSelectorMode.LIST
            )
        )
    })


def _station_names(
    stations: dict[str, dict[str, Any]], station_ids: list[str]
) -> dict[str, str]:
    """Return the names of the checked stations, keyed by station id."""
    return {station_id: stations[station_id]["nom"] for station_id in station_ids}


class MassifSelectionMixin:
    """Department, massif then stations selection, shared by the config and subentry flows."""

    _departments_data: dict[str, list[dict[str, Any]]]
    _selected_department: str
    _massif: dict[str, Any]
    _title: str
    _stations: dict[str, dict[str, Any]]

    def _get_token(self) -> str:
        """Return the API token used to list the massifs."""
        raise NotImplementedError

    def _is_configured(self, massif: dict[str, Any]) -> bool:
        """Return whether the massif is already configured."""
        return False

    async def _async_create_massif(
        self, massif: dict[str, Any], title: str, stations: dict[str, str]
    ):
        """Create the massif once selected, with its stations."""
        raise NotImplementedError

    async def async_step_department(self, user_input: dict[str, Any] | None = None):
        """Handle department selection."""
        if user_input is not None:
            self._selected_department = user_input["department"]
            return await self.async_step_massif()

        try:
            session = async_get_clientsession(self.hass)
            api = MeteoFranceMontagneApi(session, self._get_token())
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
            if self._is_configured(massif):
                return self.async_abort(reason="already_configured")
            self._massif = massif
            self._title = f"{self._selected_department} - {massif['title']}"
            return await self.async_step_stations()

        return self.async_show_form(
            step_id="massif",
            data_schema=vol.Schema({
                vol.Required("massif"): vol.In(
                    sorted(massif["title"] for massif in massifs)
                )
            }),
        )

    async def async_step_stations(self, user_input: dict[str, Any] | None = None):
        """Handle the optional selection of observation stations."""
        if user_input is not None:
            return await self._async_create_massif(
                self._massif,
                self._title,
                _station_names(self._stations, user_input[CONF_STATIONS]),
            )

        try:
            self._stations = await _async_massif_stations(self.hass, self._massif)
        except MeteoFranceMontagneApiError as err:
            # Stations are optional: add them later by reconfiguring the massif
            _LOGGER.warning("Error fetching stations: %s", err)
            self._stations = {}
        if not self._stations:
            return await self._async_create_massif(self._massif, self._title, {})

        return self.async_show_form(
            step_id="stations",
            data_schema=_stations_schema(self._stations),
            description_placeholders={"massif": self._massif["title"]},
        )


def _massif_data(massif: dict[str, Any], stations: dict[str, str]) -> dict[str, Any]:
    """Return the subentry data of a massif."""
    return {
        CONF_MASSIF: massif["code"],
        CONF_MASSIF_NAME: massif["title"],
        CONF_STATIONS: stations,
    }


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
        self, massif: dict[str, Any], title: str, stations: dict[str, str]
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title=NAME,
            data={CONF_TOKEN: self._token},
            subentries=[{
                "data": _massif_data(massif, stations),
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

    def _is_configured(self, massif: dict[str, Any]) -> bool:
        return any(
            subentry.unique_id == str(massif["code"])
            for subentry in self._get_entry().subentries.values()
        )

    async def _async_create_massif(
        self, massif: dict[str, Any], title: str, stations: dict[str, str]
    ) -> SubentryFlowResult:
        return self.async_create_entry(
            title=title,
            data=_massif_data(massif, stations),
            unique_id=str(massif["code"]),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the observation stations of a massif."""
        subentry = self._get_reconfigure_subentry()
        configured = subentry.data.get(CONF_STATIONS, {})

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data_updates={
                    CONF_STATIONS: _station_names(self._stations, user_input[CONF_STATIONS])
                },
            )

        # The geometry of the massif is not stored
        api = MeteoFranceMontagneApi(
            async_get_clientsession(self.hass), self._get_token()
        )
        try:
            departments = await api.list_massif()
            massif = next(
                (
                    massif
                    for massifs in departments.values()
                    for massif in massifs
                    if massif["code"] == subentry.data[CONF_MASSIF]
                ),
                {},
            )
            self._stations = await _async_massif_stations(self.hass, massif)
        except MeteoFranceMontagneAuthError:
            return self.async_abort(reason="invalid_auth")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error fetching stations: %s", err)
            return self.async_abort(reason="cannot_connect")

        # Keep offering a configured station that stopped observing
        for station_id, name in configured.items():
            self._stations.setdefault(station_id, {"nom": name})
        if not self._stations:
            return self.async_abort(
                reason="no_station",
                description_placeholders={"massif": subentry.data[CONF_MASSIF_NAME]},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _stations_schema(self._stations), {CONF_STATIONS: list(configured)}
            ),
            description_placeholders={"massif": subentry.data[CONF_MASSIF_NAME]},
        )
