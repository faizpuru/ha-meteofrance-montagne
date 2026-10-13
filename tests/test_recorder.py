"""Tests for the Météo-France Montagne attributes kept out of the recorder."""
from datetime import timedelta

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.meteofrance_montagne.const import DOMAIN

from .conftest import MASSIF_ID


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations):
    """Set the recorder up before Home Assistant."""
    return enable_custom_integrations


@pytest.mark.usefixtures("mock_call_api")
async def test_unrecorded_attributes(
    recorder_mock: Recorder, hass: HomeAssistant, config_entry
):
    """Keep the large lists out of the recorder."""
    start = dt_util.utcnow()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    registry = er.async_get(hass)
    meteo = registry.async_get_entity_id("sensor", DOMAIN, f"{MASSIF_ID}_meteo")
    neige = registry.async_get_entity_id("sensor", DOMAIN, f"{MASSIF_ID}_neige_fraiche")
    states = await hass.async_add_executor_job(
        get_significant_states, hass, start, start + timedelta(hours=1), [meteo, neige]
    )

    meteo_attrs = states[meteo][0].attributes
    assert "echeances" not in meteo_attrs
    assert "echeances_historique" not in meteo_attrs
    assert "commentaire" in meteo_attrs

    neige_attrs = states[neige][0].attributes
    for attr in ("historique", "mesures", "previsions"):
        assert attr not in neige_attrs
    assert neige_attrs["date_mesure"] == "2025-11-20T00:00:00"
