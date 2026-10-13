"""Common fixtures for Météo-France Montagne tests."""
from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteofrance_montagne.const import (
    CONF_MASSIF,
    CONF_MASSIF_NAME,
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

# Answer of /liste-massifs, reduced to the properties the integration reads
MASSIFS = {
    "features": [
        {"properties": {"title": "Orlu St-Barthelemy", "code": 72, "Departemen": "Ariège"}},
        {"properties": {"title": "Haute-Ariège", "code": 71, "Departemen": "Ariège"}},
        {"properties": {"title": "Champsaur", "code": 16, "Departemen": "Hautes-Alpes"}},
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
        "custom_components.meteofrance_montagne.api.MeteoFranceMontagneApi.call_api",
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
                "title": f"Ariège - {MASSIF_NAME}",
                "unique_id": str(MASSIF_ID),
            }
        ],
    )
