"""The Météo-France Montagne integration."""
import logging

from pathlib import Path
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_MASSIF, CONF_TOKEN
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.IMAGE, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Météo-France Montagne component."""
    hass.data.setdefault(DOMAIN, {})

    should_cache = True
    files_path: Path = Path(__file__).parent / "resources"

    await hass.http.async_register_static_paths([
        StaticPathConfig("/api/meteofrance_montagne/resources",
                         str(files_path), should_cache),
    ])

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Météo-France Montagne from a config entry."""

    # If this is an API configuration entry (parent), nothing to set up
    if CONF_TOKEN in entry.data:
        return True

    # Get the token from the parent entry
    parent_entry = hass.config_entries.async_get_entry(entry.data["parent_entry_id"])
    if not parent_entry:
        _LOGGER.error("Parent entry not found for massif %s", entry.data.get("massif_name"))
        return False

    token = parent_entry.data.get(CONF_TOKEN, "")
    if not token:
        _LOGGER.error("No token found in parent entry")
        return False

    session = async_get_clientsession(hass)

    coordinator = MeteoFranceMontagneDataUpdateCoordinator(
        hass,
        session,
        entry.data[CONF_MASSIF],
        entry.data["massif_name"],
        token
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # If this is an API configuration entry (parent), nothing to unload
    if CONF_TOKEN in entry.data:
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
