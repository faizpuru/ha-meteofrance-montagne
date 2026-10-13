"""Tests for the Météo-France Montagne entities."""
import pytest
from homeassistant.components.image import async_get_image
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.meteofrance_montagne.const import DOMAIN

from .conftest import MASSIF_ID, PNG, load_resource

pytestmark = pytest.mark.usefixtures("mock_call_api")

# Evening of the bulletin day: the next forecast step is 06:00 the next day
BULLETIN_EVENING = "2025-11-21T18:00:00+01:00"


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry to Home Assistant and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    """Return the entity id of a massif entity."""
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{MASSIF_ID}_{key}")


def get_state(hass: HomeAssistant, platform: str, key: str):
    """Return the state of a massif entity."""
    return hass.states.get(entity_id(hass, platform, key))


async def test_risque(hass: HomeAssistant, config_entry):
    """Expose the risk level, its zones, slopes and validity."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "sensor", "risque_max")
    assert state.state == "3"
    assert state.attributes["options"] == ["1", "2", "3", "4", "5"]
    assert state.attributes["entity_picture"].endswith("/RISQUE/3_transparent.png")
    assert state.attributes[ATTR_ATTRIBUTION].startswith("Rédigé par Météo-France")
    assert state.attributes["risque_max_texte"] == "Marqué"
    assert state.attributes["date_validite"] == "2025-11-22T18:00:00"
    assert state.attributes["amendement"] is False
    assert state.attributes["zones"] == [
        {"valeur": "3", "texte": "Marqué", "couleur": "#FF9900"}
    ]
    assert state.attributes["pentes_dangereuses_E"] is True
    assert state.attributes["pentes_dangereuses_N"] is False
    assert "\n" not in state.attributes["resume"]

    state = get_state(hass, "sensor", "risque_prevision")
    assert state.state == "3"
    assert state.attributes["date_prevision"] == "2025-11-23T00:00:00"


@pytest.mark.parametrize(
    "bulletin_xml",
    [
        load_resource("sample_bulletin.xml")
        .replace(b'LOC1="" ALTITUDE="" RISQUE2=""', b'LOC1="E" ALTITUDE="" RISQUE2="2"')
        .replace(b'LOC2=""', b'LOC2="O"')
    ],
    ids=["east_west"],
)
async def test_risque_zones_by_orientation(hass: HomeAssistant, config_entry):
    """List both zones of a massif split east/west."""
    await setup_entry(hass, config_entry)

    assert get_state(hass, "sensor", "risque_max").attributes["zones"] == [
        {"valeur": "3", "texte": "Marqué", "couleur": "#FF9900", "localisation": "E"},
        {"valeur": "2", "texte": "Limité", "couleur": "#FFFF00", "localisation": "O"},
    ]


async def test_snow(hass: HomeAssistant, config_entry):
    """Expose the snow lines, the fresh snow and the snowpack."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "sensor", "enneigement_nord")
    assert state.state == "600"
    assert state.attributes["niveaux"][0] == {"altitude_m": 1500, "enneigement_cm": 25}

    # Last analysed 24h before the bulletin day, the next ones are forecasts
    state = get_state(hass, "sensor", "neige_fraiche")
    assert state.state == "40"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "cm"
    assert state.attributes["date_mesure"] == "2025-11-20T00:00:00"
    assert state.attributes["min_cm"] == 20
    assert [p["date"] for p in state.attributes["previsions"]] == [
        "2025-11-21T00:00:00",
        "2025-11-22T00:00:00",
    ]

    state = get_state(hass, "sensor", "stabilite")
    assert state.state == "Neige fraîche"
    assert state.attributes["situations"] == [
        {"code": "1", "type": "Neige fraîche"},
        {"code": "2", "type": "Neige ventée"},
    ]

    state = get_state(hass, "sensor", "qualite_neige")
    assert len(state.state) == 100
    assert state.attributes["texte_complet"].startswith(state.state)


async def test_meteo(hass: HomeAssistant, config_entry):
    """Expose the weather comment and the cleaned forecast steps."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "sensor", "meteo")
    assert state.state == "Températures très froides le matin malgré le soleil !"
    first, *_, last = state.attributes["echeances"]
    assert first["temps_sensible_texte"] == "Neige faible"
    assert first["mer_nuages"] is None
    assert last["pluie_neige"] is None


LONG_COMMENT = "Vent de nord-ouest fort en altitude, " * 10


@pytest.mark.parametrize(
    "bulletin_xml",
    [
        load_resource("sample_bulletin.xml").replace(
            "Températures très froides le matin malgré le soleil !".encode(),
            LONG_COMMENT.encode(),
        )
    ],
    ids=["long_comment"],
)
async def test_meteo_long_comment(hass: HomeAssistant, config_entry):
    """Shorten a comment too long for a state, keep it whole in the attribute."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "sensor", "meteo")
    assert len(state.state) == 255
    assert state.state.endswith("…")
    assert LONG_COMMENT.strip().startswith(state.state[:-1])
    assert state.attributes["commentaire"] == LONG_COMMENT.strip()


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (
            BULLETIN_EVENING,
            {
                "isotherme_0": "500",
                "limite_pluie_neige": "300",
                "vent_bas": "45",
                "vent_haut": "85",
                "date_echeance": "2025-11-22T06:00:00",
            },
        ),
        (
            # Dry weather at 18:00: no rain-snow limit
            "2025-11-22T13:00:00+01:00",
            {
                "isotherme_0": "1200",
                "limite_pluie_neige": STATE_UNKNOWN,
                "vent_bas": "35",
                "vent_haut": "55",
                "date_echeance": "2025-11-22T18:00:00",
            },
        ),
        (
            # All the forecast steps are past
            "2025-11-23T01:00:00+01:00",
            {
                "isotherme_0": STATE_UNKNOWN,
                "limite_pluie_neige": STATE_UNKNOWN,
                "vent_bas": STATE_UNKNOWN,
                "vent_haut": STATE_UNKNOWN,
                "date_echeance": None,
            },
        ),
    ],
)
async def test_prochaine_echeance(
    hass: HomeAssistant, config_entry, freezer, now, expected
):
    """Give the values of the next forecast step, read in French local time."""
    freezer.move_to(now)
    await setup_entry(hass, config_entry)

    for key in ("isotherme_0", "limite_pluie_neige", "vent_bas", "vent_haut"):
        state = get_state(hass, "sensor", key)
        assert state.state == expected[key], key
        assert state.attributes["date_echeance"] == expected["date_echeance"]

    state = get_state(hass, "sensor", "vent_haut")
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "km/h"
    assert state.attributes["altitude_m"] == 3000


async def test_avis_off(hass: HomeAssistant, config_entry):
    """Stay off without warning."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "binary_sensor", "avis_risque_fort")
    assert state.state == "off"
    assert state.attributes["avis"] == ""


@pytest.mark.parametrize(
    "bulletin_xml",
    [
        load_resource("sample_bulletin.xml").replace(
            b"<AVIS/>", b"<AVIS>fort risque d'avalanche</AVIS>"
        )
    ],
    ids=["avis"],
)
async def test_avis_on(hass: HomeAssistant, config_entry):
    """Turn on with a high risk warning."""
    await setup_entry(hass, config_entry)

    state = get_state(hass, "binary_sensor", "avis_risque_fort")
    assert state.state == "on"
    assert state.attributes["avis"] == "fort risque d'avalanche"


async def test_images(hass: HomeAssistant, config_entry, freezer):
    """Serve the downloaded images, dated by the bulletin in UTC."""
    freezer.move_to(BULLETIN_EVENING)
    await setup_entry(hass, config_entry)

    image_id = entity_id(hass, "image", "rose_pentes")
    image = await async_get_image(hass, image_id)
    assert image.content == PNG
    assert image.content_type == "image/png"
    # DATEBULLETIN 16:00 in Paris, winter time
    assert hass.states.get(image_id).state == "2025-11-21T15:00:00+00:00"

