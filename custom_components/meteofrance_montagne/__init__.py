"""The Météo-France Montagne integration."""
import asyncio
import logging

from pathlib import Path
from types import MappingProxyType

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_TOKEN,
    DOMAIN,
    NAME,
    RESOURCES_URL,
    SUBENTRY_TYPE_MASSIF,
)
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.IMAGE, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# One coordinator per massif, keyed by subentry id
type MeteoFranceMontagneConfigEntry = ConfigEntry[
    dict[str, MeteoFranceMontagneDataUpdateCoordinator]
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Météo-France Montagne component."""
    should_cache = True
    files_path: Path = Path(__file__).parent / "resources"

    await hass.http.async_register_static_paths([
        StaticPathConfig(RESOURCES_URL, str(files_path), should_cache),
    ])

    await async_migrate_integration(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MeteoFranceMontagneConfigEntry
) -> bool:
    """Set up Météo-France Montagne from a config entry."""
    session = async_get_clientsession(hass)

    coordinators = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_MASSIF:
            continue
        coordinator = MeteoFranceMontagneDataUpdateCoordinator(
            hass,
            entry,
            session,
            subentry.data[CONF_MASSIF],
            subentry.data[CONF_MASSIF_NAME],
            entry.data[CONF_TOKEN],
        )
        coordinators[subentry.subentry_id] = coordinator

    results = await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ),
        return_exceptions=True,
    )
    errors = {
        coordinator.massif_name: result
        for coordinator, result in zip(coordinators.values(), results)
        if isinstance(result, Exception)
    }
    for error in errors.values():
        # The key is shared by all the massifs, and bugs must not be hidden
        if not isinstance(error, ConfigEntryNotReady):
            raise error
    if coordinators and len(errors) == len(coordinators):
        raise next(iter(errors.values()))

    # A failing massif does not block the others: its entities stay
    # unavailable until one of its next hourly refreshes succeeds
    for massif_name, error in errors.items():
        _LOGGER.warning("Massif %s is not available yet: %s", massif_name, error)

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when a massif is added or removed
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MeteoFranceMontagneConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(
    hass: HomeAssistant, entry: MeteoFranceMontagneConfigEntry
) -> None:
    """Reload the entry when its subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Turn the version 2 massif entries into subentries of their API entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not any(entry.version < 3 for entry in entries):
        return

    entity_registry = er.async_get(hass)

    for parent in entries:
        if parent.version >= 3 or CONF_TOKEN not in parent.data:
            continue

        for child in entries:
            if child.data.get("parent_entry_id") != parent.entry_id:
                continue

            unique_id = str(child.data[CONF_MASSIF])
            subentry = next(
                (
                    sub for sub in parent.subentries.values()
                    if sub.unique_id == unique_id
                ),
                None,
            )
            if subentry is None:
                subentry = ConfigSubentry(
                    data=MappingProxyType({
                        CONF_MASSIF: child.data[CONF_MASSIF],
                        CONF_MASSIF_NAME: child.data[CONF_MASSIF_NAME],
                    }),
                    subentry_type=SUBENTRY_TYPE_MASSIF,
                    title=child.title,
                    unique_id=unique_id,
                )
                hass.config_entries.async_add_subentry(parent, subentry)

            # Move the entities before removing the child entry, which would
            # otherwise delete them along with their history
            for entity in er.async_entries_for_config_entry(
                entity_registry, child.entry_id
            ):
                disabled_by = entity.disabled_by
                # Moving to an enabled entry clears CONFIG_ENTRY, keep it disabled
                if disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY:
                    disabled_by = er.RegistryEntryDisabler.USER
                entity_registry.async_update_entity(
                    entity.entity_id,
                    config_entry_id=parent.entry_id,
                    config_subentry_id=subentry.subentry_id,
                    disabled_by=disabled_by,
                )

            await hass.config_entries.async_remove(child.entry_id)

        hass.config_entries.async_update_entry(
            parent, title=NAME, version=3, minor_version=1
        )


async def async_migrate_entry(
    hass: HomeAssistant, entry: MeteoFranceMontagneConfigEntry
) -> bool:
    """Handle entries left behind by async_migrate_integration."""
    if entry.version < 3:
        # A massif whose API entry was deleted cannot be migrated
        _LOGGER.error(
            "Cannot migrate massif %s: its API configuration no longer exists. "
            "Delete it and add the massif again",
            entry.title,
        )
    return False
