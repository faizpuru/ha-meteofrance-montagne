"""Platform for Météo-France Montagne sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MeteoFranceMontagneConfigEntry
from .const import (
    AVALANCHE_RISK,
    AVALANCHE_RISK_COLORS,
    AVALANCHE_RISK_LEVELS,
    AVALANCHE_SITUATIONS,
    RESOURCES_URL,
    WEATHER_CONDITIONS,
)
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator
from .entity import MeteoFranceMontagneEntity

_LOGGER = logging.getLogger(__name__)


def _clean_text(value: str | None) -> str:
    """Flatten a multiline text from the bulletin."""
    return (value or "").replace("\n", " ").strip()


def _risk_level(value: Any) -> str | None:
    """Return the risk level if it is on the European scale."""
    return str(value) if str(value) in AVALANCHE_RISK_LEVELS else None


def _risk_picture(value: Any) -> str:
    """Return the official pictogram of a risk level."""
    if (level := _risk_level(value)) is None:
        return f"{RESOURCES_URL}/RISQUE/9_PasdinfoV1.png"
    return f"{RESOURCES_URL}/RISQUE/{level}_transparent.png"


# Avalanche risk

def _risque_attrs(data: dict) -> dict[str, Any]:
    risque = data["risque"]

    risk_max_value = risque.get("risque_max")
    altitude_limite = risque.get("altitude_limite")

    attrs = {
        "risque_max_valeur": risk_max_value,
        "risque_max_texte": AVALANCHE_RISK.get(str(risk_max_value), ""),
        "risque_max_couleur": AVALANCHE_RISK_COLORS.get(str(risk_max_value), ""),
        "resume": _clean_text(risque.get("resume")),
        "commentaire": _clean_text(risque.get("commentaire")),
        "departs_spontanes": _clean_text(risque.get("naturel")),
        "declenchements_skieurs": _clean_text(risque.get("accidentel")),
        "last_update": data.get("date"),
    }

    # Add altitude limit if exists
    if altitude_limite is not None:
        attrs["altitude_limite_m"] = altitude_limite

    # Build zones list
    zones = []

    if risk_1 := risque.get("risque_1"):
        risk_1_value = risk_1.get("valeur")
        zone_1 = {
            "valeur": risk_1_value,
            "texte": AVALANCHE_RISK.get(str(risk_1_value), "") if risk_1_value else "",
            "couleur": AVALANCHE_RISK_COLORS.get(str(risk_1_value), "") if risk_1_value else "",
        }
        # Add altitude range only if there's a limit (2 zones)
        if altitude_limite is not None:
            zone_1["altitude"] = f"<{altitude_limite}m"
        # Add evolution only if not empty
        if risk_1.get("evolution"):
            zone_1["evolution"] = risk_1.get("evolution")
        zones.append(zone_1)

    # Only add zone 2 if there's an altitude limit
    if altitude_limite is not None and (risk_2 := risque.get("risque_2")):
        risk_2_value = risk_2.get("valeur")
        zone_2 = {
            "valeur": risk_2_value,
            "texte": AVALANCHE_RISK.get(str(risk_2_value), "") if risk_2_value else "",
            "couleur": AVALANCHE_RISK_COLORS.get(str(risk_2_value), "") if risk_2_value else "",
            "altitude": f">{altitude_limite}m",
        }
        # Add evolution only if not empty
        if risk_2.get("evolution"):
            zone_2["evolution"] = risk_2.get("evolution")
        zones.append(zone_2)

    if zones:
        attrs["zones"] = zones

    if pentes := risque.get("pentes_particulieres"):
        attrs.update({
            f"pentes_dangereuses_{orientation}": pentes.get(orientation)
            for orientation in ("NE", "E", "SE", "S", "SW", "W", "NW", "N")
        })
        attrs["pentes_commentaire"] = pentes.get("commentaire", "")

    # Add historical risk data
    if "historique" in risque:
        attrs["historique"] = risque.get("historique", [])

    return attrs


def _risque_j2(data: dict) -> dict:
    return data["risque"].get("estimation_j2") or {}


def _risque_j2_attrs(data: dict) -> dict[str, Any]:
    if not (j2 := _risque_j2(data)):
        return {}

    risk_value = j2.get("risque_max")
    return {
        "risque_max_valeur": risk_value,
        "risque_max_texte": AVALANCHE_RISK.get(str(risk_value), ""),
        "risque_max_couleur": AVALANCHE_RISK_COLORS.get(str(risk_value), ""),
        "commentaire": _clean_text(j2.get("commentaire")),
        "description": _clean_text(j2.get("description")),
        "date_prevision": j2.get("date"),
        "last_update": data.get("date"),
    }


# Snow cover

def _enneigement_attrs(orientation: str) -> Callable[[dict], dict[str, Any]]:
    """Return the attributes builder of the north or south snow limit."""

    def attrs_fn(data: dict) -> dict[str, Any]:
        enneigement = data["enneigement"]
        attrs = {
            "date": enneigement.get("date"),
            "last_update": data.get("date"),
            f"limite_{orientation}_m": enneigement.get(f"limite_{orientation}"),
            # Snow depth levels for this orientation
            "niveaux": [
                {
                    "altitude_m": niveau.get("altitude"),
                    "enneigement_cm": niveau.get(orientation),
                }
                for niveau in enneigement.get("niveaux", [])
            ],
        }

        # Historical snow cover data, filtered by orientation
        if "historique" in enneigement:
            attrs["historique"] = [
                {
                    "date": h.get("date"),
                    f"limite_{orientation}": h.get(f"limite_{orientation}"),
                    "niveaux": [
                        {
                            "altitude_m": n.get("altitude"),
                            "enneigement_cm": n.get(orientation),
                        }
                        for n in h.get("niveaux", [])
                    ],
                }
                for h in enneigement.get("historique", [])
            ]

        return attrs

    return attrs_fn


def _neige_fraiche_attrs(data: dict) -> dict[str, Any]:
    neige = data["neige_fraiche"]
    attrs = {
        "altitude_mesure_m": neige.get("altitude_ss"),
        "last_update": data.get("date"),
        "mesures": [
            {
                "date": mesure.get("date"),
                "min_cm": mesure.get("min"),
                "max_cm": mesure.get("max"),
            }
            for mesure in neige.get("mesures", [])
        ],
    }

    # Add historical fresh snow data
    if "historique" in neige:
        attrs["historique"] = neige.get("historique", [])

    return attrs


# Weather

def _clean_echeance(echeance: dict) -> dict:
    """Clean forecast values, replace -1 with None and add weather condition text."""
    cleaned = {}
    for key, value in echeance.items():
        if value == -1:
            cleaned[key] = None
        elif key == "temps_sensible" and value is not None:
            cleaned[key] = value
            cleaned["temps_sensible_texte"] = WEATHER_CONDITIONS.get(value, "")
        else:
            cleaned[key] = value
    return cleaned


def _meteo_attrs(data: dict) -> dict[str, Any]:
    meteo = data["meteo"]
    return {
        "altitude_vent_1_m": meteo.get("altitude_vent_1"),
        "altitude_vent_2_m": meteo.get("altitude_vent_2"),
        "commentaire": meteo.get("commentaire", ""),
        "echeances": [_clean_echeance(e) for e in meteo.get("echeances", [])],
        "echeances_historique": [
            _clean_echeance(e) for e in meteo.get("echeances_historique", [])
        ],
        "last_update": data.get("date"),
    }


# Snowpack stability

def _situation(data: dict) -> Any:
    """Return the code of the main typical avalanche situation."""
    situations = data["stabilite"].get("situations_avalancheuses", [])
    return situations[0].get("type") if situations else None


def _stabilite_value(data: dict) -> StateType:
    if (situation_type := _situation(data)) is None:
        return None
    return AVALANCHE_SITUATIONS.get(str(situation_type), situation_type)


def _stabilite_picture(data: dict) -> str | None:
    situation_type = str(_situation(data))
    if situation_type not in AVALANCHE_SITUATIONS:
        return None
    return f"{RESOURCES_URL}/SAT/SAT{situation_type}.png"


def _stabilite_attrs(data: dict) -> dict[str, Any]:
    stabilite = data["stabilite"]
    return {
        "titre": stabilite.get("titre", ""),
        "texte": _clean_text(stabilite.get("texte")),
        "last_update": data.get("date"),
        # Typical avalanche situations (SAT) as a structured list
        "situations": [
            {
                "code": situation.get("type"),
                "type": AVALANCHE_SITUATIONS.get(str(situation.get("type")), ""),
            }
            for situation in stabilite.get("situations_avalancheuses", [])
        ],
    }


@dataclass(frozen=True, kw_only=True)
class MeteoFranceMontagneSensorEntityDescription(SensorEntityDescription):
    """Describes a Météo-France Montagne sensor."""

    value_fn: Callable[[dict], StateType]
    attrs_fn: Callable[[dict], dict[str, Any]]
    picture_fn: Callable[[dict], str | None] = lambda data: None


SENSOR_TYPES: tuple[MeteoFranceMontagneSensorEntityDescription, ...] = (
    MeteoFranceMontagneSensorEntityDescription(
        key="risque_max",
        translation_key="risque_max",
        icon="mdi:alert",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_RISK_LEVELS,
        value_fn=lambda data: _risk_level(data["risque"].get("risque_max")),
        picture_fn=lambda data: _risk_picture(data["risque"].get("risque_max")),
        attrs_fn=_risque_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="risque_prevision",
        translation_key="risque_prevision",
        icon="mdi:alert-outline",
        device_class=SensorDeviceClass.ENUM,
        options=AVALANCHE_RISK_LEVELS,
        value_fn=lambda data: _risk_level(_risque_j2(data).get("risque_max")),
        picture_fn=lambda data: _risk_picture(_risque_j2(data).get("risque_max")),
        attrs_fn=_risque_j2_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="enneigement_nord",
        translation_key="enneigement_nord",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["enneigement"].get("limite_nord"),
        attrs_fn=_enneigement_attrs("nord"),
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="enneigement_sud",
        translation_key="enneigement_sud",
        icon="mdi:snowflake",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["enneigement"].get("limite_sud"),
        attrs_fn=_enneigement_attrs("sud"),
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="neige_fraiche",
        translation_key="neige_fraiche",
        icon="mdi:weather-snowy-heavy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data["neige_fraiche"].get("altitude_ss"),
        attrs_fn=_neige_fraiche_attrs,
    ),
    MeteoFranceMontagneSensorEntityDescription(
        key="meteo",
        translation_key="meteo",
        icon="mdi:weather-windy",
        value_fn=lambda data: _clean_text(data["meteo"].get("commentaire")),
        attrs_fn=_meteo_attrs,
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
        # Return first 100 chars as state
        value_fn=lambda data: data["qualite"][:100] if data["qualite"] else None,
        attrs_fn=lambda data: {
            "texte_complet": data["qualite"],
            "last_update": data.get("date"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoFranceMontagneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Météo-France Montagne sensors."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [
                MeteoFranceMontagneSensor(coordinator, description)
                for description in SENSOR_TYPES
            ],
            config_subentry_id=subentry_id,
        )


class MeteoFranceMontagneSensor(MeteoFranceMontagneEntity, SensorEntity):
    """Representation of a Météo-France Montagne sensor."""

    entity_description: MeteoFranceMontagneSensorEntityDescription

    def __init__(
        self,
        coordinator: MeteoFranceMontagneDataUpdateCoordinator,
        description: MeteoFranceMontagneSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if not self.coordinator.data:
            return None
        return self.entity_description.picture_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)
