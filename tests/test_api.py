"""Tests for the Météo-France Montagne API client and XML parser."""
import xml.etree.ElementTree as ET

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.meteofrance_montagne.api import (
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
    MeteoFranceMontagneOffSeason,
)
from custom_components.meteofrance_montagne.const import BASE_URL

from .conftest import MASSIFS, TOKEN, load_resource

BULLETIN_URL = f"{BASE_URL}/massif/BRA?id-massif=72&format=xml"


def parse(xml: bytes) -> dict:
    """Parse a bulletin with the integration parser."""
    return MeteoFranceMontagneApi(None, None, TOKEN).parse_bulletin_xml(
        ET.fromstring(xml)
    )


@pytest.fixture
def bulletin() -> dict:
    """Return the parsed sample bulletin."""
    return parse(load_resource("sample_bulletin.xml"))


def test_parse_header(bulletin):
    """Parse the bulletin identification and dates."""
    assert bulletin["type"] == "bulletins_neige_avalanche"
    assert bulletin["id"] == "72"
    assert bulletin["massif"] == "Orlu St-Barthelemy"
    assert bulletin["dateBulletin"] == "2025-11-21T16:00:00"
    assert bulletin["dateEcheance"] == "2025-11-22T18:00:00"
    assert bulletin["dateValidite"] == "2025-11-22T18:00:00"
    assert bulletin["dateDiffusion"] == "2025-11-21T16:25:00"
    assert bulletin["amendement"] is False
    assert bulletin["partenaires"].startswith("Rédigé par Météo-France")


def test_parse_risque(bulletin):
    """Parse the avalanche risk."""
    risque = bulletin["risque"]
    assert risque["risque_max"] == "3"
    assert risque["risque_1"] == {"valeur": "3", "evolution": "", "localisation": ""}
    assert risque["risque_2"]["valeur"] == ""
    assert risque["altitude_limite"] is None
    assert risque["commentaire"] == "Indice de risque marqué."
    assert risque["naturel"] == "Nombreux départs pendant les chutes puis au soleil"
    assert risque["accidentel"] == "Nombreuses plaques friables facilement déclenchables"
    assert "Départs spontanés" in risque["resume"]
    assert risque["avis"] == ""

    assert risque["estimation_j2"] == {
        "date": "2025-11-23T00:00:00",
        "risque_max": "3",
        "description": "Indice de risque marqué",
        "commentaire": "Stabilisation progressive du manteau neigeux.",
    }

    assert len(risque["historique"]) == 7
    assert risque["historique"][-1] == {"date": "2025-11-21T00:00:00", "risque_max": "2"}


def test_parse_pentes(bulletin):
    """Convert the dangerous slopes to booleans."""
    assert bulletin["risque"]["pentes_particulieres"] == {
        "NE": False,
        "E": True,
        "SE": True,
        "S": True,
        "SW": True,
        "W": True,
        "NW": False,
        "N": False,
        "commentaire": "",
    }


def test_parse_stabilite_qualite(bulletin):
    """Parse the snowpack stability and the snow quality."""
    stabilite = bulletin["stabilite"]
    assert stabilite["situations_avalancheuses"] == [{"type": "1"}, {"type": "2"}]
    assert stabilite["titre"] == "Manteau neigeux récent encore instable"
    assert "Déclenchements provoqués" in stabilite["texte"]
    assert "Le jour se lève samedi" in bulletin["qualite"]


def test_parse_enneigement(bulletin):
    """Parse the snow cover and its history."""
    enneigement = bulletin["enneigement"]
    assert enneigement["date"] == "2025-11-21T00:00:00"
    assert enneigement["limite_sud"] == 600
    assert enneigement["limite_nord"] == 600
    assert len(enneigement["niveaux"]) == 3
    assert enneigement["niveaux"][0] == {"altitude": 1500, "nord": 25, "sud": 25}
    assert enneigement["niveaux"][2]["altitude"] == 2500
    assert enneigement["niveaux"][2]["nord"] == 50

    assert enneigement["historique"]
    assert set(enneigement["historique"][0]) == {
        "date", "limite_sud", "limite_nord", "niveaux"
    }


def test_parse_neige_fraiche(bulletin):
    """Parse the fresh snow measures and their history."""
    neige = bulletin["neige_fraiche"]
    assert neige["altitude_ss"] == 1800
    assert len(neige["mesures"]) == 6
    assert neige["mesures"][0] == {"date": "2025-11-17T00:00:00", "min": 0, "max": 3}
    assert neige["mesures"][3] == {"date": "2025-11-20T00:00:00", "min": 20, "max": 40}

    assert neige["historique"]
    assert set(neige["historique"][0]) == {"date", "min", "max"}


def test_parse_meteo(bulletin):
    """Parse the weather forecast and its history."""
    meteo = bulletin["meteo"]
    assert meteo["altitude_vent_1"] == 2000
    assert meteo["altitude_vent_2"] == 3000
    assert meteo["commentaire"] == "Températures très froides le matin malgré le soleil !"
    assert len(meteo["echeances"]) == 4

    assert meteo["echeances"][0] == {
        "date": "2025-11-22T06:00:00",
        "vent": {"force_1": 45, "direction_1": "NO", "force_2": 85, "direction_2": "NO"},
        "iso_0": 500,
        "pluie_neige": 300,
        "temps_sensible": 61,
        "mer_nuages": -1,
    }
    assert meteo["echeances"][3]["date"] == "2025-11-23T00:00:00"
    assert meteo["echeances"][3]["pluie_neige"] == -1

    assert meteo["echeances_historique"]
    assert set(meteo["echeances_historique"][0]) == {
        "date", "vent", "iso_0", "pluie_neige", "temps_sensible", "mer_nuages"
    }


def test_parse_zones_by_orientation():
    """Keep the second risk of a massif split east/west, without altitude limit."""
    xml = load_resource("sample_bulletin.xml").replace(
        b'RISQUE1="3" EVOLURISQUE1="" LOC1="" ALTITUDE="" RISQUE2=""',
        b'RISQUE1="3" EVOLURISQUE1="" LOC1="E" ALTITUDE="" RISQUE2="2"',
    ).replace(b'LOC2=""', b'LOC2="O"')
    risque = parse(xml)["risque"]
    assert risque["altitude_limite"] is None
    assert risque["risque_1"]["localisation"] == "E"
    assert risque["risque_2"] == {"valeur": "2", "evolution": "", "localisation": "O"}


def test_parse_avis():
    """Read the high risk warning."""
    xml = load_resource("sample_bulletin.xml").replace(
        b"<AVIS/>", b"<AVIS>fort risque d'avalanche</AVIS>"
    )
    assert parse(xml)["risque"]["avis"] == "fort risque d'avalanche"


async def test_bulletin_off_season(hass: HomeAssistant, aioclient_mock):
    """Raise off season when the API answers a message instead of a bulletin."""
    aioclient_mock.get(BULLETIN_URL, content=load_resource("offseason_bulletin.xml"))
    api = MeteoFranceMontagneApi(async_get_clientsession(hass), hass, TOKEN)

    with pytest.raises(MeteoFranceMontagneOffSeason, match="la saison est terminée"):
        await api.bulletin(72)


async def test_bulletin_invalid_xml(hass: HomeAssistant, aioclient_mock):
    """Raise an API error on a malformed answer."""
    aioclient_mock.get(BULLETIN_URL, content=b"<BULLETINS")
    api = MeteoFranceMontagneApi(async_get_clientsession(hass), hass, TOKEN)

    with pytest.raises(MeteoFranceMontagneApiError, match="XML parsing error"):
        await api.bulletin(72)


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, MeteoFranceMontagneAuthError),
        (404, MeteoFranceMontagneOffSeason),
        (500, MeteoFranceMontagneApiError),
    ],
)
async def test_call_api_errors(hass: HomeAssistant, aioclient_mock, status, error):
    """Map the HTTP errors to the integration exceptions."""
    aioclient_mock.get(BULLETIN_URL, status=status)
    api = MeteoFranceMontagneApi(async_get_clientsession(hass), hass, TOKEN)

    with pytest.raises(error):
        await api.call_api(BULLETIN_URL)


async def test_call_api_sends_key(hass: HomeAssistant, aioclient_mock):
    """Send the API key and organize the massifs by department."""
    aioclient_mock.get(f"{BASE_URL}/liste-massifs", json=MASSIFS)
    api = MeteoFranceMontagneApi(async_get_clientsession(hass), hass, TOKEN)

    assert await api.list_massif() == {
        "Ariège": [
            {"title": "Orlu St-Barthelemy", "code": 72},
            {"title": "Haute-Ariège", "code": 71},
        ],
        "Hautes-Alpes": [{"title": "Champsaur", "code": 16}],
    }
    assert aioclient_mock.mock_calls[0][3]["apikey"] == TOKEN
