"""Common fixtures for Météo-France Montagne tests."""
from collections.abc import Generator
import gzip
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from meteofrance_montagne.const import NIVO_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteofrance_montagne.const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
    CONF_STATIONS,
    CONF_TOKEN,
    DOMAIN,
    NAME,
    SUBENTRY_TYPE_MASSIF,
)

RESOURCES = Path(__file__).parent / "resources"

TOKEN = "api-key"
MASSIF_ID = 72
MASSIF_NAME = "Orlu St-Barthelemy"
PNG = b"\x89PNG\r\n\x1a\n"

STATION_ID = "7498"
# Haute-Tarentaise, holding the station
STATION_MASSIF_ID = 6
STATION_NAME = "Val d'Isère (Joseray)"
NIVO_ETAG = '"nivo-2026"'
# A day after the last observations of the sample
OBSERVATIONS_DAY = "2026-02-13T09:00:00+00:00"



def square(longitude: float, latitude: float) -> dict:
    """Return a massif geometry of about 20 km around a point."""
    west, east = longitude - 0.15, longitude + 0.15
    south, north = latitude - 0.1, latitude + 0.1
    return {
        "type": "MultiPolygon",
        "coordinates": [[[
            [west, south], [east, south], [east, north], [west, north], [west, south]
        ]]],
    }


# Answer of /liste-massifs, reduced to the properties the integration reads
MASSIFS = {
    "features": [
        {
            "properties": {"title": "Orlu St-Barthelemy", "code": 72, "Departement": "Ariege"},
            "geometry": square(1.95, 42.65),
        },
        {
            "properties": {"title": "Haute-Ariege", "code": 70, "Departement": "Ariege"},
            "geometry": square(1.6, 42.7),
        },
        {
            "properties": {"title": "Champsaur", "code": 19, "Departement": "Hautes-Alpes"},
            "geometry": square(6.2, 44.7),
        },
        # Holds the station 7498 of the nivo sample, not 7393 in Mont-Blanc
        {
            "properties": {
                "title": "Haute-Tarentaise", "code": STATION_MASSIF_ID, "Departement": "Savoie"
            },
            "geometry": square(6.95, 45.5),
        },
    ]
}


def load_resource(name: str) -> bytes:
    """Return the content of a file of tests/resources."""
    return (RESOURCES / name).read_bytes()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return enable_custom_integrations


@pytest.fixture
def bulletin_xml() -> bytes:
    """Return the bulletin answered by the API."""
    return load_resource("sample_bulletin.xml")


@pytest.fixture
def mock_call_api(bulletin_xml: bytes) -> Generator[AsyncMock]:
    """Answer the API calls with the sample bulletin, massifs and images."""

    async def call_api(url: str) -> bytes:
        if url.endswith("/liste-massifs"):
            return json.dumps(MASSIFS).encode()
        if "/massif/BRA" in url:
            return bulletin_xml
        return PNG

    with patch(
        "meteofrance_montagne.MeteoFranceMontagneApi.call_api",
        AsyncMock(side_effect=call_api),
    ) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return the API entry with one massif."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_TOKEN: TOKEN},
        version=3,
        minor_version=1,
        subentries_data=[
            {
                "data": {CONF_MASSIF: MASSIF_ID, CONF_MASSIF_NAME: MASSIF_NAME},
                "subentry_type": SUBENTRY_TYPE_MASSIF,
                "title": f"Ariege - {MASSIF_NAME}",
                "unique_id": str(MASSIF_ID),
            }
        ],
    )


def nivo_file() -> bytes:
    """Return the sample nivo file, compressed as published."""
    return gzip.compress(load_resource("nivo_sample.csv"))


@pytest.fixture
def mock_nivo(aioclient_mock, freezer) -> Generator:
    """Publish the sample nivo file for 2026, and no file for 2025, the day after."""
    freezer.move_to(OBSERVATIONS_DAY)
    aioclient_mock.get(
        NIVO_URL.format(year=2026), content=nivo_file(), headers={"ETag": NIVO_ETAG}
    )
    aioclient_mock.get(NIVO_URL.format(year=2025), status=404)
    return aioclient_mock


@pytest.fixture
def station_entry() -> MockConfigEntry:
    """Return the API entry with a massif following one of its stations."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_TOKEN: TOKEN},
        version=3,
        minor_version=1,
        subentries_data=[
            {
                "data": {
                    CONF_MASSIF: STATION_MASSIF_ID,
                    CONF_MASSIF_NAME: "Haute-Tarentaise",
                    CONF_STATIONS: {STATION_ID: STATION_NAME},
                },
                "subentry_type": SUBENTRY_TYPE_MASSIF,
                "title": "Savoie - Haute-Tarentaise",
                "unique_id": str(STATION_MASSIF_ID),
            },
        ],
    )
