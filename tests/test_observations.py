"""Tests for the observations of the nivo-meteorological network."""
from datetime import timedelta
import gzip
from http import HTTPStatus

import pytest
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from meteofrance_montagne.const import NIVO_URL
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.meteofrance_montagne.const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_STATIONS,
    DOMAIN,
    SUBENTRY_TYPE_MASSIF,
    UPDATE_INTERVAL,
)

from .conftest import (
    NIVO_ETAG,
    OBSERVATIONS_DAY,
    STATION_ID,
    STATION_MASSIF_ID,
    STATION_NAME,
    load_resource,
    nivo_file,
)

pytestmark = pytest.mark.usefixtures("mock_call_api")


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry to Home Assistant and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def get_state(hass: HomeAssistant, key: str, station_id: str = STATION_ID):
    """Return the state of a station sensor, None once removed."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"station_{station_id}_{key}"
    )
    return hass.states.get(entity_id) if entity_id else None


@pytest.mark.usefixtures("mock_nivo")
async def test_station_sensors(hass: HomeAssistant, station_entry):
    """Expose the last observation of the station under its device, in the massif."""
    await setup_entry(hass, station_entry)

    state = get_state(hass, "hauteur_neige")
    assert state.state == "151"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "cm"
    assert state.attributes["date_observation"] == "2026-02-12T12:02:00Z"
    assert state.attributes["altitude_m"] == 1854
    assert state.attributes[ATTR_ATTRIBUTION].startswith("Données Météo-France")

    state = get_state(hass, "neige_fraiche_24h")
    assert state.state == "31"
    assert state.attributes["neige_fraiche_altitude_cm"] is None

    state = get_state(hass, "temps_observe")
    assert state.state == "Neige modérée"
    assert state.attributes["code_temps_present"] == 73
    assert state.attributes["nebulosite_pct"] == 100

    state = get_state(hass, "precipitations_24h")
    assert state.state == "24.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "mm"

    state = get_state(hass, "humidite")
    assert state.state == "95"
    assert state.attributes["point_rosee"] == -2.4

    state = get_state(hass, "temperature")
    assert state.state == "-1.7"
    assert state.attributes["temperature_min_24h"] == -6.6
    assert get_state(hass, "temperature_neige").state == "0.0"

    state = get_state(hass, "vent")
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "km/h"
    assert float(state.state) == pytest.approx(7.2)
    assert state.attributes["direction"] == 360
    assert state.attributes["chasse_neige"] is None

    state = get_state(hass, "neige_surface")
    assert state.state == "Neige fraîche"
    assert state.attributes["grains_sous_surface"] == "Neige roulée"
    assert state.attributes["masse_volumique_kg_m3"] == 80

    state = get_state(hass, "risque_observe")
    assert state.state == "5"
    assert state.attributes["entity_picture"].endswith("/RISQUE/5_transparent.png")

    (subentry_id,) = station_entry.subentries
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"station_{STATION_ID}"), station_entry.entry_id
    )
    massif = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(STATION_MASSIF_ID)), station_entry.entry_id
    )
    assert device.name == STATION_NAME
    assert device.via_device_id == massif.id
    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    assert len(entities) == 10
    assert {entity.config_subentry_id for entity in entities} == {subentry_id}


@pytest.mark.parametrize(
    ("weather", "cloud_cover", "expected", "percent"),
    [("0", "8", "Couvert", 100), ("2", "3", "Nuageux", 38), ("0", "9", "Ciel invisible", None)],
)
async def test_temps_observe_sky(
    hass: HomeAssistant,
    station_entry,
    mock_nivo,
    weather,
    cloud_cover,
    expected,
    percent,
):
    """Give the sky when nothing is falling."""
    content = load_resource("nivo_sample.csv").replace(
        b"2026-02-12T12:02:00Z;360;2.0;271.45;270.75;95;73;7;7;8;",
        f"2026-02-12T12:02:00Z;360;2.0;271.45;270.75;95;{weather};7;7;{cloud_cover};".encode(),
    )
    mock_nivo.clear_requests()
    mock_nivo.get(NIVO_URL.format(year=2026), content=gzip.compress(content))
    await setup_entry(hass, station_entry)

    state = get_state(hass, "temps_observe")
    assert state.state == expected
    assert state.attributes["nebulosite_pct"] == percent


@pytest.mark.usefixtures("mock_nivo")
async def test_station_stopped_observing(hass: HomeAssistant, station_entry, freezer):
    """Leave unknown an observation too old, giving its date."""
    freezer.move_to("2026-02-16T13:00:00+00:00")
    await setup_entry(hass, station_entry)

    state = get_state(hass, "hauteur_neige")
    assert state.state == STATE_UNKNOWN
    assert state.attributes["date_observation"] == "2026-02-12T12:02:00Z"
    assert "hauteur_neige_altitude_cm" not in state.attributes
    assert get_state(hass, "risque_observe").attributes.get("entity_picture") is None


async def test_file_unchanged(hass: HomeAssistant, station_entry, mock_nivo):
    """Ask for the file only if it changed, and keep the observations."""
    await setup_entry(hass, station_entry)

    mock_nivo.clear_requests()
    mock_nivo.get(NIVO_URL.format(year=2026), status=HTTPStatus.NOT_MODIFIED)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=UPDATE_INTERVAL))
    await hass.async_block_till_done(wait_background_tasks=True)

    ((_, _, _, headers),) = mock_nivo.mock_calls
    assert headers["If-None-Match"] == NIVO_ETAG
    assert get_state(hass, "hauteur_neige").state == "151"


def shifted_file() -> bytes:
    """Return the sample file moved to the last days of 2026."""
    content = load_resource("nivo_sample.csv")
    for day, new_day in (("10", "29"), ("11", "30"), ("12", "31")):
        content = content.replace(f"2026-02-{day}".encode(), f"2026-12-{new_day}".encode())
    return gzip.compress(content)


async def test_new_year(hass: HomeAssistant, station_entry, aioclient_mock, freezer):
    """Read the previous file while the file of the year is not published."""
    freezer.move_to("2027-01-01T09:00:00+00:00")
    aioclient_mock.get(NIVO_URL.format(year=2026), content=shifted_file())
    aioclient_mock.get(NIVO_URL.format(year=2027), status=404)
    await setup_entry(hass, station_entry)

    state = get_state(hass, "hauteur_neige")
    assert state.state == "151"
    assert state.attributes["date_observation"] == "2026-12-31T12:02:00Z"


async def test_observations_down(
    hass: HomeAssistant, station_entry, aioclient_mock, freezer
):
    """Load the massifs when the observations are down, and recover them later."""
    freezer.move_to(OBSERVATIONS_DAY)
    aioclient_mock.get(NIVO_URL.format(year=2026), status=500)
    await setup_entry(hass, station_entry)

    assert station_entry.state is ConfigEntryState.LOADED
    massif = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{STATION_MASSIF_ID}_risque_max"
    )
    assert hass.states.get(massif).state == "3"
    assert get_state(hass, "hauteur_neige").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(NIVO_URL.format(year=2026), content=nivo_file())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=UPDATE_INTERVAL))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert get_state(hass, "hauteur_neige").state == "151"


async def start_massif_flow(
    hass: HomeAssistant, entry: MockConfigEntry, department: str, massif: str
):
    """Pick a department and a massif in the massif flow."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_MASSIF), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"department": department}
    )
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"massif": massif}
    )


def massif_subentry(entry: MockConfigEntry, massif_id: int):
    """Return the subentry of a massif."""
    return next(
        sub for sub in entry.subentries.values() if sub.unique_id == str(massif_id)
    )


@pytest.mark.usefixtures("mock_nivo")
async def test_add_massif_with_stations(hass: HomeAssistant, config_entry):
    """Check stations among the ones of the massif."""
    config_entry.add_to_hass(hass)

    result = await start_massif_flow(hass, config_entry, "Savoie", "Haute-Tarentaise")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "stations"
    assert result["description_placeholders"] == {"massif": "Haute-Tarentaise"}
    # LE TOUR BALME is in another massif
    options = result["data_schema"].schema[CONF_STATIONS].config["options"]
    assert options == [{"value": STATION_ID, "label": "Val d'Isère (Joseray) (1854 m)"}]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATIONS: [STATION_ID]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(massif_subentry(config_entry, STATION_MASSIF_ID).data) == {
        CONF_MASSIF: STATION_MASSIF_ID,
        CONF_MASSIF_NAME: "Haute-Tarentaise",
        CONF_STATIONS: {STATION_ID: STATION_NAME},
    }


@pytest.mark.usefixtures("mock_nivo")
async def test_add_massif_without_station(hass: HomeAssistant, config_entry):
    """Add a massif without station directly."""
    config_entry.add_to_hass(hass)

    result = await start_massif_flow(hass, config_entry, "Hautes-Alpes", "Champsaur")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert massif_subentry(config_entry, 19).data[CONF_STATIONS] == {}


async def test_add_massif_stations_down(
    hass: HomeAssistant, config_entry, aioclient_mock, freezer
):
    """Add the massif without stations when they cannot be listed."""
    freezer.move_to(OBSERVATIONS_DAY)
    aioclient_mock.get(NIVO_URL.format(year=2025), status=500)
    aioclient_mock.get(NIVO_URL.format(year=2026), status=500)
    config_entry.add_to_hass(hass)

    result = await start_massif_flow(hass, config_entry, "Savoie", "Haute-Tarentaise")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert massif_subentry(config_entry, STATION_MASSIF_ID).data[CONF_STATIONS] == {}


async def start_reconfigure(hass: HomeAssistant, entry: MockConfigEntry, massif_id: int):
    """Start the reconfiguration of the stations of a massif."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_MASSIF),
        context={
            "source": SOURCE_RECONFIGURE,
            "subentry_id": massif_subentry(entry, massif_id).subentry_id,
        },
    )


@pytest.mark.usefixtures("mock_nivo")
async def test_reconfigure_uncheck_station(hass: HomeAssistant, station_entry):
    """Remove the device and the entities of an unchecked station."""
    await setup_entry(hass, station_entry)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"station_{STATION_ID}"), station_entry.entry_id
    )

    result = await start_reconfigure(hass, station_entry, STATION_MASSIF_ID)
    assert result["step_id"] == "reconfigure"
    schema = result["data_schema"].schema
    (key,) = schema
    assert key.description == {"suggested_value": [STATION_ID]}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATIONS: []}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert massif_subentry(station_entry, STATION_MASSIF_ID).data[CONF_STATIONS] == {}
    assert device_registry.async_get(device.id) is None
    assert not er.async_entries_for_device(
        er.async_get(hass), device.id, include_disabled_entities=True
    )
    assert get_state(hass, "hauteur_neige") is None
    assert hass.states.get(
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{STATION_MASSIF_ID}_risque_max"
        )
    ).state == "3"


@pytest.mark.usefixtures("mock_nivo")
async def test_reconfigure_check_station(hass: HomeAssistant, station_entry):
    """Add the entities of a station checked later."""
    station_entry.add_to_hass(hass)
    hass.config_entries.async_update_subentry(
        station_entry,
        massif_subentry(station_entry, STATION_MASSIF_ID),
        data={
            CONF_MASSIF: STATION_MASSIF_ID,
            CONF_MASSIF_NAME: "Haute-Tarentaise",
            CONF_STATIONS: {},
        },
    )
    await hass.config_entries.async_setup(station_entry.entry_id)
    await hass.async_block_till_done()
    assert get_state(hass, "hauteur_neige") is None

    result = await start_reconfigure(hass, station_entry, STATION_MASSIF_ID)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_STATIONS: [STATION_ID]}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert get_state(hass, "hauteur_neige").state == "151"


@pytest.mark.usefixtures("mock_nivo")
async def test_reconfigure_no_station(hass: HomeAssistant, config_entry):
    """Abort for a massif without station."""
    config_entry.add_to_hass(hass)

    result = await start_reconfigure(hass, config_entry, 72)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_station"
    assert result["description_placeholders"] == {"massif": "Orlu St-Barthelemy"}
