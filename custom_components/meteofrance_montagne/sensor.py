"""Platform for Météo-France Montagne sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime
import logging
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    MAX_LENGTH_STATE_STATE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util
from meteofrance_montagne import (
    Bulletin,
    Echeance,
    NeigeFraicheJour,
    NiveauEnneigement,
    Observation,
)

from . import MeteoFranceMontagneConfigEntry
from .const import (
    AVALANCHE_RISK,
    AVALANCHE_RISK_COLORS,
    AVALANCHE_RISK_LEVELS,
    AVALANCHE_SITUATIONS,
    BLOWING_SNOW,
    CONF_STATIONS,
    PRESENT_WEATHER,
    RESOURCES_URL,
    SKY_CONDITIONS,
    SNOW_GRAINS,
    WEATHER_CONDITIONS,
)
from .coordinator import (
    MeteoFranceMontagneDataUpdateCoordinator,
    MassifData,
    MeteoFranceNivoDataUpdateCoordinator,
    parse_bulletin_time,
)
from .entity import (
    MeteoFranceMontagneEntity,
    MeteoFranceMontagneStationEntity,
    massif_device_info,
    station_device_info,
)

_LOGGER = logging.getLogger(__name__)


def _clean_text(value: str | None) -> str:
    """Flatten a multiline text from the bulletin."""
    return (value or "").replace("\n", " ").strip()


def _first_sentence(value: str | None, attribute: str) -> str | None:
    """Return the first sentence of a text, short enough for a state."""
    if not (text := _clean_text(value)):
        return None
    # Sentences are sometimes glued: "non skiable.Enneigement : ..."
    text = re.split(r"(?<=[.!?])\s+|(?<=[a-zà-ÿ][.!?])(?=[A-ZÀ-Ý])", text, maxsplit=1)[0]
    if len(text) <= MAX_LENGTH_STATE_STATE:
        return text
    # Point to the attribute holding the whole text
    suffix = f"… (suite dans l'attribut {attribute})"
    return text[:MAX_LENGTH_STATE_STATE - len(suffix)].rstrip() + suffix


def _risk_level(value: Any) -> str | None:
    """Return the risk level if it is on the European scale."""
    return str(value) if str(value) in AVALANCHE_RISK_LEVELS else None


def _risk_picture(value: Any) -> str:
    """Return the official pictogram of a risk level."""
    if (level := _risk_level(value)) is None:
        return f"{RESOURCES_URL}/RISQUE/9_PasdinfoV1.png"
    return f"{RESOURCES_URL}/RISQUE/{level}_transparent.png"


# Avalanche risk

def _risque_attrs(bulletin: Bulletin) -> dict[str, Any]:
    risque = bulletin.risque
    risk_max_value = risque.risque_max
    altitude_limite = risque.altitude_limite

    attrs: dict[str, Any] = {
        "risque_max_valeur": risk_max_value,
        "risque_max_texte": AVALANCHE_RISK.get(risk_max_value, ""),
        "risque_max_couleur": AVALANCHE_RISK_COLORS.get(risk_max_value, ""),
        "resume": _clean_text(risque.resume),
        "commentaire": _clean_text(risque.commentaire),
        "departs_spontanes": _clean_text(risque.naturel),
        "declenchements_skieurs": _clean_text(risque.accidentel),
        "avis": _clean_text(risque.avis),
        "date_validite": bulletin.date_validite,
        "amendement": bulletin.amendement,
        "date_diffusion": bulletin.date_diffusion,
        "last_update": bulletin.date_bulletin,
    }

    # Add altitude limit if exists
    if altitude_limite is not None:
        attrs["altitude_limite_m"] = altitude_limite

    # Build zones list: split by altitude (LOC "<2100" / ">2100") or by
    # orientation (LOC "E"/"O" or "S"/"N", no altitude limit)
    zones = []
    for index, risk in enumerate((risque.risque_1, risque.risque_2), start=1):
        if not (value := risk.valeur):
            continue
        zone = {
            "valeur": value,
            "texte": AVALANCHE_RISK.get(value, ""),
            "couleur": AVALANCHE_RISK_COLORS.get(value, ""),
        }
        if altitude_limite is not None:
            zone["altitude"] = f"{'<' if index == 1 else '>'}{altitude_limite}m"
        elif risk.localisation:
            zone["localisation"] = risk.localisation
        # Add evolution only if not empty
        if risk.evolution:
            zone["evolution"] = risk.evolution
        zones.append(zone)

    if zones:
        attrs["zones"] = zones

    attrs.update({
        f"pentes_dangereuses_{orientation}": dangerous
        for orientation, dangerous in risque.pentes.orientations.items()
    })
    attrs["pentes_commentaire"] = risque.pentes.commentaire

    attrs["historique"] = [
        # No risk on the days without bulletin
        {"date": jour.date, "risque_max": jour.risque_max or None}
        for jour in risque.historique
    ]

    return attrs


def _risque_j2_attrs(bulletin: Bulletin) -> dict[str, Any]:
    j2 = bulletin.risque.estimation_j2
    return {
        "risque_max_valeur": j2.risque_max,
        "risque_max_texte": AVALANCHE_RISK.get(j2.risque_max, ""),
        "risque_max_couleur": AVALANCHE_RISK_COLORS.get(j2.risque_max, ""),
        "commentaire": _clean_text(j2.commentaire),
        "description": _clean_text(j2.description),
        "date_prevision": j2.date,
        "last_update": bulletin.date_bulletin,
    }


# Snow cover

def _limite_enneigement(value: int | None) -> int | None:
    """Return a snow line, None without continuous snow cover.

    The bulletin gives -1 in that case, and 0 in the history.
    """
    return None if value is None or value <= 0 else value


def _enneigement_attrs(orientation: str) -> Callable[[Bulletin], dict[str, Any]]:
    """Return the attributes builder of the north or south snow limit."""

    def niveaux(niveaux: tuple[NiveauEnneigement, ...]) -> list[dict[str, Any]]:
        """Return the snow depth levels for this orientation."""
        return [
            {
                "altitude_m": niveau.altitude,
                "enneigement_cm": getattr(niveau, orientation),
            }
            for niveau in niveaux
        ]

    def attrs_fn(bulletin: Bulletin) -> dict[str, Any]:
        enneigement = bulletin.enneigement
        return {
            "date": enneigement.date,
            "last_update": bulletin.date_bulletin,
            f"limite_{orientation}_m": _limite_enneigement(
                getattr(enneigement, f"limite_{orientation}")
            ),
            "niveaux": niveaux(enneigement.niveaux),
            # Historical snow cover data, filtered by orientation
            "historique": [
                {
                    "date": jour.date,
                    f"limite_{orientation}": _limite_enneigement(
                        getattr(jour, f"limite_{orientation}")
                    ),
                    "niveaux": niveaux(jour.niveaux),
                }
                for jour in enneigement.historique
            ],
        }

    return attrs_fn


def _parse_day(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _neige_fraiche_split(
    bulletin: Bulletin,
) -> tuple[list[NeigeFraicheJour], list[NeigeFraicheJour]]:
    """Split the 24h fresh snow measures into analyses and forecasts.

    Each measure covers 06 UTC to 06 UTC the next day, starting on its date:
    the ones starting on the bulletin day or later are forecasts.
    """
    bulletin_day = _parse_day(bulletin.date_bulletin)
    analyses, previsions = [], []
    for mesure in bulletin.neige_fraiche.mesures:
        day = _parse_day(mesure.date)
        if bulletin_day and day and day >= bulletin_day:
            previsions.append(mesure)
        else:
            analyses.append(mesure)
    return analyses, previsions


def _mesure_attrs(mesure: NeigeFraicheJour) -> dict[str, Any]:
    return {
        "date": mesure.date,
        "min_cm": mesure.min,
        "max_cm": mesure.max,
    }


def _neige_fraiche_value(bulletin: Bulletin) -> StateType:
    analyses, _ = _neige_fraiche_split(bulletin)
    return analyses[-1].max if analyses else None


def _neige_fraiche_attrs(bulletin: Bulletin) -> dict[str, Any]:
    neige = bulletin.neige_fraiche
    analyses, previsions = _neige_fraiche_split(bulletin)
    derniere = analyses[-1] if analyses else None
    return {
        "min_cm": derniere.min if derniere else None,
        "date_mesure": derniere.date if derniere else None,
        "previsions": [_mesure_attrs(mesure) for mesure in previsions],
        "altitude_mesure_m": neige.altitude_ss,
        "last_update": bulletin.date_bulletin,
        "mesures": [_mesure_attrs(mesure) for mesure in neige.mesures],
        "historique": [_mesure_attrs(mesure) for mesure in neige.historique],
    }


# Weather

def _clean_echeance(echeance: Echeance) -> dict[str, Any]:
    """Clean forecast values, replace -1 with None and add weather condition text."""
    cleaned: dict[str, Any] = {}
    for key, value in asdict(echeance).items():
        if value == -1:
            cleaned[key] = None
        elif key == "temps_sensible" and value is not None:
            cleaned[key] = value
            cleaned["temps_sensible_texte"] = WEATHER_CONDITIONS.get(value, "")
        else:
            cleaned[key] = value
    return cleaned


def _prochaine_echeance(bulletin: Bulletin) -> Echeance | None:
    """Return the first forecast step still to come, None once all are past."""
    now = dt_util.utcnow()
    for echeance in bulletin.meteo.echeances:
        try:
            if parse_bulletin_time(echeance.date) >= now:
                return echeance
        except ValueError:
            continue
    return None


def _echeance_value(value: int | None) -> int | None:
    """Return a forecast value, None for the -1 "not applicable" marker."""
    return None if value == -1 else value


def _prochaine_valeur(
    bulletin: Bulletin, value_fn: Callable[[Echeance], int | None]
) -> int | None:
    """Return a value of the next forecast step."""
    if (echeance := _prochaine_echeance(bulletin)) is None:
        return None
    return _echeance_value(value_fn(echeance))


def _echeance_attrs(bulletin: Bulletin) -> dict[str, Any]:
    echeance = _prochaine_echeance(bulletin)
    return {"date_echeance": echeance.date if echeance else None}


def _vent(
    index: int,
) -> tuple[Callable[[Bulletin], StateType], Callable[[Bulletin], dict[str, Any]]]:
    """Return the value and attributes builders of the low (1) or high (2) wind."""

    def force(echeance: Echeance) -> int | None:
        return echeance.vent.force_1 if index == 1 else echeance.vent.force_2

    def value_fn(bulletin: Bulletin) -> StateType:
        return _prochaine_valeur(bulletin, force)

    def attrs_fn(bulletin: Bulletin) -> dict[str, Any]:
        echeance = _prochaine_echeance(bulletin)
        meteo = bulletin.meteo
        return {
            "direction": (
                (echeance.vent.direction_1 if index == 1 else echeance.vent.direction_2)
                if echeance
                else None
            ),
            "altitude_m": meteo.altitude_vent_1 if index == 1 else meteo.altitude_vent_2,
            "date_echeance": echeance.date if echeance else None,
        }

    return value_fn, attrs_fn


VENT_BAS = _vent(1)
VENT_HAUT = _vent(2)


def _temps_sensible(bulletin: Bulletin) -> StateType:
    """Return the weather condition of the next forecast step."""
    echeance = _prochaine_echeance(bulletin)
    if echeance is None or (code := echeance.temps_sensible) is None:
        return None
    return WEATHER_CONDITIONS.get(code, code)


def _meteo_attrs(bulletin: Bulletin) -> dict[str, Any]:
    meteo = bulletin.meteo
    return {
        "date_echeance": _echeance_attrs(bulletin)["date_echeance"],
        "altitude_vent_1_m": meteo.altitude_vent_1,
        "altitude_vent_2_m": meteo.altitude_vent_2,
        "commentaire": meteo.commentaire,
        "echeances": [_clean_echeance(e) for e in meteo.echeances],
        "echeances_historique": [_clean_echeance(e) for e in meteo.echeances_historique],
        "last_update": bulletin.date_bulletin,
    }


# Snowpack stability

def _situation(bulletin: Bulletin) -> str | None:
    """Return the code of the main typical avalanche situation."""
    situations = bulletin.stabilite.situations_avalancheuses
    return situations[0] if situations else None


def _stabilite_value(bulletin: Bulletin) -> StateType:
    if (situation_type := _situation(bulletin)) is None:
        return None
    return AVALANCHE_SITUATIONS.get(situation_type, situation_type)


def _stabilite_picture(bulletin: Bulletin) -> str | None:
    situation_type = str(_situation(bulletin))
    if situation_type not in AVALANCHE_SITUATIONS:
        return None
    return f"{RESOURCES_URL}/SAT/SAT{situation_type}.png"


def _stabilite_attrs(bulletin: Bulletin) -> dict[str, Any]:
    stabilite = bulletin.stabilite
    return {
        "titre": stabilite.titre,
        "texte": _clean_text(stabilite.texte),
        "last_update": bulletin.date_bulletin,
        # Typical avalanche situations (SAT) as a structured list
        "situations": [
            {"code": code, "type": AVALANCHE_SITUATIONS.get(code, "")}
            for code in stabilite.situations_avalancheuses
        ],
    }


@dataclass(frozen=True, kw_only=True)
class MeteoFranceMontagneSensorEntityDescription(SensorEntityDescription):
    """Describes a Météo-France Montagne sensor."""

    value_fn: Callable[[Bulletin], StateType]
    attrs_fn: Callable[[Bulletin], dict[str, Any]]
    picture_fn: Callable[[Bulletin], str | None] = lambda bulletin: None

SENSOR_TYPES: tuple[MeteoFranceMontagneSensorEntityDescription, ...] = (
    MeteoFranceMontagneSensorEntityDescription(
        key="risque_max",
        translation_key="risque_max",
        icon="mdi:alert",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_RISK_LEVELS,
        value_fn=lambda bulletin: _risk_level(bulletin.risque.risque_max),
        picture_fn=lambda bulletin: _risk_picture(bulletin.risque.risque_max),
        attrs_fn=_risque_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="risque_prevision",
        translation_key="risque_prevision",
        icon="mdi:alert-outline",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_RISK_LEVELS,
        value_fn=lambda bulletin: _risk_level(bulletin.risque.estimation_j2.risque_max),
        picture_fn=lambda bulletin: _risk_picture(bulletin.risque.estimation_j2.risque_max),
        attrs_fn=_risque_j2_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="enneigement_nord",
        translation_key="enneigement_nord",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda bulletin: _limite_enneigement(bulletin.enneigement.limite_nord),
        attrs_fn=_enneigement_attrs("nord"),
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="enneigement_sud",
        translation_key="enneigement_sud",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda bulletin: _limite_enneigement(bulletin.enneigement.limite_sud),
        attrs_fn=_enneigement_attrs("sud"),
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="neige_fraiche",
        translation_key="neige_fraiche",
        icon="mdi:weather-snowy-heavy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        # Snow fallen during the last analysed 24h
        value_fn=_neige_fraiche_value,
        attrs_fn=_neige_fraiche_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="meteo",
        translation_key="meteo",
        icon="mdi:weather-windy",
        # Weather condition of the next forecast step
        value_fn=_temps_sensible,
        attrs_fn=_meteo_attrs,
    ),
    # Next forecast step of the bulletin
    MeteoFranceMontagneSensorEntityDescription(
        key="isotherme_0",
        translation_key="isotherme_0",
        icon="mdi:snowflake-thermometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda bulletin: _prochaine_valeur(bulletin, lambda e: e.iso_0),
        attrs_fn=_echeance_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="limite_pluie_neige",
        translation_key="limite_pluie_neige",
        icon="mdi:weather-snowy-rainy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        # -1 when the weather is dry
        value_fn=lambda bulletin: _prochaine_valeur(bulletin, lambda e: e.pluie_neige),
        attrs_fn=_echeance_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="mer_nuages",
        translation_key="mer_nuages",
        icon="mdi:weather-fog",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        # -1 without a sea of clouds
        value_fn=lambda bulletin: _prochaine_valeur(bulletin, lambda e: e.mer_nuages),
        attrs_fn=_echeance_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="vent_bas",
        translation_key="vent_bas",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=VENT_BAS[0],
        attrs_fn=VENT_BAS[1],
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="vent_haut",
        translation_key="vent_haut",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=VENT_HAUT[0],
        attrs_fn=VENT_HAUT[1],
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="stabilite",
        translation_key="stabilite",
        icon="mdi:layers",
        value_fn=_stabilite_value,
        picture_fn=_stabilite_picture,
        attrs_fn=_stabilite_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="qualite_neige",
        translation_key="qualite_neige",
        icon="mdi:snowflake-variant",
        value_fn=lambda bulletin: _first_sentence(bulletin.qualite, "texte_complet"),
        attrs_fn=lambda bulletin: {
            "texte_complet": bulletin.qualite,
            "last_update": bulletin.date_bulletin,
        },
    ),
)


def _code_text(texts: dict[int, str], code: int | None) -> str | None:
    """Return the text of a code of the nivo file, None when not observed."""
    return None if code is None else texts.get(code)


def _temps_observe(observation: Observation) -> StateType:
    """Return the observed weather, the sky when nothing is falling."""
    if (weather := _code_text(PRESENT_WEATHER, observation.temps_present)) is not None:
        return weather
    return _code_text(SKY_CONDITIONS, observation.nebulosite)


def _nebulosite_pct(observation: Observation) -> int | None:
    """Return the cloud cover in percent, None when the sky is hidden."""
    octas = observation.nebulosite
    return None if octas is None or octas > 8 else round(octas * 12.5)


@dataclass(frozen=True, kw_only=True)
class MeteoFranceMontagneStationSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor of an observation station."""

    value_fn: Callable[[Observation], StateType]
    attrs_fn: Callable[[Observation], dict[str, Any]] = lambda observation: {}
    picture_fn: Callable[[Observation], str | None] = lambda observation: None


STATION_SENSOR_TYPES: tuple[MeteoFranceMontagneStationSensorEntityDescription, ...] = (
    MeteoFranceMontagneStationSensorEntityDescription(
        key="hauteur_neige",
        translation_key="hauteur_neige",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.hauteur_neige,
        attrs_fn=lambda observation: {
            # Estimated by the observer higher up
            "hauteur_neige_altitude_cm": observation.hauteur_neige_altitude,
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="neige_fraiche_24h",
        translation_key="neige_fraiche_24h",
        icon="mdi:weather-snowy-heavy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.neige_fraiche_24h,
        attrs_fn=lambda observation: {
            # Estimated by the observer higher up
            "neige_fraiche_altitude_cm": observation.neige_fraiche_altitude,
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.temperature,
        attrs_fn=lambda observation: {
            "temperature_min_24h": observation.temperature_min_24h,
            "temperature_max_24h": observation.temperature_max_24h,
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="humidite",
        translation_key="humidite",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.humidite,
        attrs_fn=lambda observation: {"point_rosee": observation.point_rosee},
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="precipitations_24h",
        translation_key="precipitations_24h",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.precipitations_24h,
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="temps_observe",
        translation_key="temps_observe",
        icon="mdi:weather-partly-snowy",
        value_fn=_temps_observe,
        attrs_fn=lambda observation: {
            "code_temps_present": observation.temps_present,
            "nebulosite_octas": observation.nebulosite,
            "nebulosite_pct": _nebulosite_pct(observation),
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="temperature_neige",
        translation_key="temperature_neige",
        icon="mdi:snowflake-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        # At the surface of the snow
        value_fn=lambda observation: observation.temperature_neige,
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="vent",
        translation_key="vent",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda observation: observation.vent_force,
        attrs_fn=lambda observation: {
            "direction": observation.vent_direction,
            "vent_altitude_force_ms": observation.vent_altitude_force,
            "vent_altitude_direction": observation.vent_altitude_direction,
            "chasse_neige": _code_text(BLOWING_SNOW, observation.chasse_neige),
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="neige_surface",
        translation_key="neige_surface",
        icon="mdi:snowflake-variant",
        value_fn=lambda observation: _code_text(SNOW_GRAINS, observation.grain_surface),
        attrs_fn=lambda observation: {
            # Between the surface and 10 cm below
            "grains_sous_surface": _code_text(SNOW_GRAINS, observation.grain_sous_surface),
            "masse_volumique_kg_m3": observation.masse_volumique,
        },
    ),
    MeteoFranceMontagneStationSensorEntityDescription(
        key="risque_observe",
        translation_key="risque_observe",
        icon="mdi:alert",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_RISK_LEVELS,
        # Estimated by the observer, not the risk of the bulletin
        value_fn=lambda observation: _risk_level(observation.risque),
        picture_fn=lambda observation: (
            _risk_picture(observation.risque)
            if _risk_level(observation.risque)
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoFranceMontagneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Météo-France Montagne sensors."""
    for subentry_id, coordinator in entry.runtime_data.massifs.items():
        async_add_entities(
            [
                MeteoFranceMontagneSensor(coordinator, description)
                for description in SENSOR_TYPES
            ],
            config_subentry_id=subentry_id,
        )

    if (observations := entry.runtime_data.observations) is None:
        return
    device_registry = dr.async_get(hass)
    for subentry_id, coordinator in entry.runtime_data.massifs.items():
        stations = entry.subentries[subentry_id].data.get(CONF_STATIONS, {})
        if not stations:
            continue
        # Link the stations to their massif by device id: the via_device of
        # DeviceInfo is deprecated, and via_device_id requires HA 2026.8
        massif = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry_id,
            **massif_device_info(coordinator.massif_id, coordinator.massif_name),
        )
        for station_id, name in stations.items():
            station = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                config_subentry_id=subentry_id,
                **station_device_info(station_id, name),
            )
            device_registry.async_update_device(station.id, via_device_id=massif.id)
        async_add_entities(
            [
                MeteoFranceMontagneStationSensor(
                    observations, station_id, name, description
                )
                for station_id, name in stations.items()
                for description in STATION_SENSOR_TYPES
            ],
            config_subentry_id=subentry_id,
        )


class MeteoFranceMontagneSensor(MeteoFranceMontagneEntity, SensorEntity):
    """Representation of a Météo-France Montagne sensor."""

    entity_description: MeteoFranceMontagneSensorEntityDescription

    # Large lists, already holding the last days of the bulletin: keep them
    # out of the recorder database
    _unrecorded_attributes = frozenset({
        "echeances",
        "echeances_historique",
        "historique",
        "mesures",
        "niveaux",
        "previsions",
    })

    def __init__(
        self,
        coordinator: MeteoFranceMontagneDataUpdateCoordinator,
        description: MeteoFranceMontagneSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def _bulletin(self) -> Bulletin | None:
        """Return the bulletin, None outside the season."""
        return self.coordinator.data.bulletin if self.coordinator.data else None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (data := self._bulletin) is None:
            return None
        return self.entity_description.value_fn(data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if (data := self._bulletin) is None:
            return None
        return self.entity_description.picture_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        # None while the first refresh failed
        data: MassifData | None = self.coordinator.data
        if data is None:
            return {}
        if data.bulletin is None:
            return {"hors_saison": True, "message": data.message}
        return self.entity_description.attrs_fn(data.bulletin)


class MeteoFranceMontagneStationSensor(MeteoFranceMontagneStationEntity, SensorEntity):
    """Sensor of an observation station."""

    entity_description: MeteoFranceMontagneStationSensorEntityDescription

    def __init__(
        self,
        coordinator: MeteoFranceNivoDataUpdateCoordinator,
        station_id: str,
        station_name: str,
        description: MeteoFranceMontagneStationSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station_id, station_name, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if (observation := self.observation) is None:
            return None
        return self.entity_description.value_fn(observation)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if (observation := self.observation) is None:
            return None
        return self.entity_description.picture_fn(observation)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if (last := self.last_observation) is None:
            return {}
        # The date tells why a station that stopped observing is unknown
        attrs = {"date_observation": last.date, "altitude_m": last.altitude}
        if (observation := self.observation) is not None:
            attrs.update(self.entity_description.attrs_fn(observation))
        return attrs
