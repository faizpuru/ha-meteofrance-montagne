"""Tests for the Météo-France Montagne setup and migration."""
from datetime import timedelta

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.meteofrance_montagne import async_migrate_integration
from custom_components.meteofrance_montagne.api import (
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
)
from custom_components.meteofrance_montagne.const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_TOKEN,
    DOMAIN,
    NAME,
    OFF_SEASON_UPDATE_INTERVAL,
    SUBENTRY_TYPE_MASSIF,
    UPDATE_INTERVAL,
)

from .conftest import MASSIF_ID, MASSIF_NAME, TOKEN, load_resource


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry to Home Assistant and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_call_api")
async def test_setup_and_unload(hass: HomeAssistant, config_entry):
    """Create the massif device and its entities, then unload them."""
    await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    entities = er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    )
    assert len(entities) == 19
    (subentry_id,) = config_entry.subentries
    assert {entity.config_subentry_id for entity in entities} == {subentry_id}

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry(hass: HomeAssistant, config_entry, mock_call_api):
    """Retry later when the API is down."""
    mock_call_api.side_effect = MeteoFranceMontagneApiError("500")

    await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failed(hass: HomeAssistant, config_entry, mock_call_api):
    """Start a reauthentication when the key is rejected."""
    mock_call_api.side_effect = MeteoFranceMontagneAuthError("401")

    await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    (flow,) = hass.config_entries.flow.async_progress()
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == config_entry.entry_id


async def test_off_season(hass: HomeAssistant, config_entry, mock_call_api):
    """Load off season, poll less often, and come back with the first bulletin."""
    side_effect = mock_call_api.side_effect

    async def off_season(url):
        if "/massif/BRA" in url:
            return load_resource("offseason_bulletin.xml")
        return await side_effect(url)

    mock_call_api.side_effect = off_season
    await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    coordinator = next(iter(config_entry.runtime_data.values()))
    assert coordinator.data["hors_saison"] is True
    assert coordinator.update_interval == timedelta(hours=OFF_SEASON_UPDATE_INTERVAL)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{MASSIF_ID}_risque_max"
    )
    state = hass.states.get(entity_id)
    assert state.state == "unknown"
    assert state.attributes["hors_saison"] is True
    assert "la saison est terminée" in state.attributes["message"]

    mock_call_api.side_effect = side_effect
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(hours=OFF_SEASON_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.update_interval == timedelta(hours=UPDATE_INTERVAL)
    assert hass.states.get(entity_id).state == "3"


async def test_images_fetched_once_per_bulletin(
    hass: HomeAssistant, config_entry, mock_call_api
):
    """Download the images again only when the bulletin changes."""
    await setup_entry(hass, config_entry)
    assert mock_call_api.await_count == 7

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=UPDATE_INTERVAL))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_call_api.await_count == 8


async def test_migration_from_v2(hass: HomeAssistant):
    """Turn the version 2 massif entries into subentries, keeping their entities."""
    parent = MockConfigEntry(
        domain=DOMAIN, title="API", data={CONF_TOKEN: TOKEN}, version=2
    )
    parent.add_to_hass(hass)
    child = MockConfigEntry(
        domain=DOMAIN,
        title=f"Ariège - {MASSIF_NAME}",
        data={
            "parent_entry_id": parent.entry_id,
            CONF_MASSIF: MASSIF_ID,
            CONF_MASSIF_NAME: MASSIF_NAME,
        },
        version=2,
    )
    child.add_to_hass(hass)

    registry = er.async_get(hass)
    risque = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MASSIF_ID}_risque_max",
        config_entry=child,
        suggested_object_id="orlu_st_barthelemy_risque_max",
    )
    disabled = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MASSIF_ID}_qualite_neige",
        config_entry=child,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
    )

    await async_migrate_integration(hass)

    assert hass.config_entries.async_get_entry(child.entry_id) is None
    assert parent.version == 3
    assert parent.title == NAME
    (subentry,) = parent.subentries.values()
    assert subentry.subentry_type == SUBENTRY_TYPE_MASSIF
    assert subentry.unique_id == str(MASSIF_ID)
    assert subentry.title == f"Ariège - {MASSIF_NAME}"

    migrated = registry.async_get(risque.entity_id)
    assert migrated.entity_id == "sensor.orlu_st_barthelemy_risque_max"
    assert migrated.config_entry_id == parent.entry_id
    assert migrated.config_subentry_id == subentry.subentry_id
    assert registry.async_get(disabled.entity_id).disabled_by is (
        er.RegistryEntryDisabler.USER
    )


async def test_migration_orphan_massif(hass: HomeAssistant):
    """Refuse to load a version 2 massif whose API entry was deleted."""
    orphan = MockConfigEntry(
        domain=DOMAIN,
        title=MASSIF_NAME,
        data={
            "parent_entry_id": "deleted",
            CONF_MASSIF: MASSIF_ID,
            CONF_MASSIF_NAME: MASSIF_NAME,
        },
        version=2,
    )
    await setup_entry(hass, orphan)
    assert orphan.state is ConfigEntryState.MIGRATION_ERROR
