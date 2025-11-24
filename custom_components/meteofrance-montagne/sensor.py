"""Platform for Météo-France Montagne sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN, AVALANCHE_RISK, AVALANCHE_RISK_COLORS, AVALANCHE_SITUATIONS, WEATHER_CONDITIONS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Météo-France Montagne sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        MeteoFranceMontagneRisqueSensor(
            coordinator,
            "risque_max",
            "Risque Avalanche",
            "mdi:alert",
        ),
        MeteoFranceMontagneRisqueJ2Sensor(
            coordinator,
            "risque_prevision",
            "Risque Avalanche Prévision",
            "mdi:alert-outline",
        ),
        MeteoFranceMontagneEnneigementSensor(
            coordinator,
            "enneigement_nord",
            "Limite Enneigement Nord",
            "mdi:snowflake",
            "limite_nord"
        ),
        MeteoFranceMontagneEnneigementSensor(
            coordinator,
            "enneigement_sud",
            "Limite Enneigement Sud",
            "mdi:snowflake",
            "limite_sud"
        ),
        MeteoFranceMontagneNeigeFraicheSensor(
            coordinator,
            "neige_fraiche",
            "Neige Fraîche",
            "mdi:weather-snowy-heavy",
        ),
        MeteoFranceMontagneMeteoSensor(
            coordinator,
            "meteo",
            "Météo",
            "mdi:weather-windy",
        ),
        MeteoFranceMontagneStabiliteSensor(
            coordinator,
            "stabilite",
            "Stabilité du Manteau Neigeux",
            "mdi:layers",
        ),
        MeteoFranceMontagneQualiteSensor(
            coordinator,
            "qualite_neige",
            "Qualité de la Neige",
            "mdi:snowflake-variant",
        ),
    ]

    async_add_entities(entities)


class MeteoFranceMontagneRisqueSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return None
        risque = self.coordinator.data["risque"]
        risk_value = risque.get("risque_max")
        # Return text description instead of number
        return AVALANCHE_RISK.get(str(risk_value), risk_value)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return None
        risk_value = self.coordinator.data["risque"].get("risque_max")
        return f"/api/meteofrance-montagne/resources/RISQUE/{risk_value}_transparent.png"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return {}

        risque = self.coordinator.data["risque"]

        risk_max_value = risque.get("risque_max")
        altitude_limite = risque.get("altitude_limite")

        attrs = {
            "risque_max_valeur": risk_max_value,
            "risque_max_texte": AVALANCHE_RISK.get(str(risk_max_value), ""),
            "risque_max_couleur": AVALANCHE_RISK_COLORS.get(str(risk_max_value), ""),
            "resume": risque.get("resume", "").replace("\n", " ").strip(),
            "commentaire": risque.get("commentaire", "").replace("\n", " ").strip(),
            "departs_spontanes": risque.get("naturel", "").replace("\n", " ").strip(),
            "declenchements_skieurs": risque.get("accidentel", "").replace("\n", " ").strip(),
            "last_update": self.coordinator.data.get("date"),
        }

        # Add altitude limit if exists
        if altitude_limite is not None:
            attrs["altitude_limite_m"] = altitude_limite

        # Build zones list
        zones = []

        if "risque_1" in risque and risque["risque_1"]:
            risk_1 = risque["risque_1"]
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
        if altitude_limite is not None and "risque_2" in risque and risque["risque_2"]:
            risk_2 = risque["risque_2"]
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

        if "pentes_particulieres" in risque and risque["pentes_particulieres"]:
            pentes = risque["pentes_particulieres"]
            attrs.update({
                "pentes_dangereuses_NE": pentes.get("NE"),
                "pentes_dangereuses_E": pentes.get("E"),
                "pentes_dangereuses_SE": pentes.get("SE"),
                "pentes_dangereuses_S": pentes.get("S"),
                "pentes_dangereuses_SW": pentes.get("SW"),
                "pentes_dangereuses_W": pentes.get("W"),
                "pentes_dangereuses_NW": pentes.get("NW"),
                "pentes_dangereuses_N": pentes.get("N"),
                "pentes_commentaire": pentes.get("commentaire", ""),
            })

        return attrs


class MeteoFranceMontagneEnneigementSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Snow Sensor."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
        limite_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._limite_type = limite_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "enneigement" not in self.coordinator.data:
            return None
        return self.coordinator.data["enneigement"].get(self._limite_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "enneigement" not in self.coordinator.data:
            return {}

        enneigement = self.coordinator.data["enneigement"]
        niveaux = enneigement.get("niveaux", [])

        # Determine which orientation we're tracking
        is_nord = self._limite_type == "limite_nord"
        orientation_key = "nord" if is_nord else "sud"

        attrs = {
            "date": enneigement.get("date"),
            "last_update": self.coordinator.data.get("date"),
        }

        # Add only the relevant limit
        if is_nord:
            attrs["limite_nord_m"] = enneigement.get("limite_nord")
        else:
            attrs["limite_sud_m"] = enneigement.get("limite_sud")

        # Add snow depth levels as a structured list
        attrs["niveaux"] = [
            {
                "altitude_m": niveau.get("altitude"),
                "enneigement_cm": niveau.get(orientation_key)
            }
            for niveau in niveaux
        ]

        return attrs


class MeteoFranceMontagneMeteoSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Weather Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "meteo" not in self.coordinator.data:
            return None
        return self.coordinator.data["meteo"].get("commentaire", "").replace("\n", " ").strip()

    def _clean_echeance(self, echeance: dict) -> dict:
        """Clean forecast values, replace -1 with None and add weather condition text."""
        cleaned = {}
        for key, value in echeance.items():
            if value == -1:
                cleaned[key] = None
            elif key == "temps_sensible" and value is not None:
                cleaned[key] = value
                cleaned["temps_sensible_texte"] = WEATHER_CONDITIONS.get(
                    value, "")
            else:
                cleaned[key] = value
        return cleaned

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "meteo" not in self.coordinator.data:
            return {}
        meteo = self.coordinator.data["meteo"]
        echeances = meteo.get("echeances", [])

        # Nettoyer les échéances et ajouter les traductions
        clean_echeances = [self._clean_echeance(
            echeance) for echeance in echeances]

        attrs = {
            "altitude_vent_1_m": meteo.get("altitude_vent_1"),
            "altitude_vent_2_m": meteo.get("altitude_vent_2"),
            "commentaire": meteo.get("commentaire", ""),
            "echeances": clean_echeances,
            "last_update": self.coordinator.data.get("date"),
        }
        return attrs


class MeteoFranceMontagneNeigeFraicheSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Fresh Snow Sensor."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "neige_fraiche" not in self.coordinator.data:
            return None
        return self.coordinator.data["neige_fraiche"].get("altitude_ss")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "neige_fraiche" not in self.coordinator.data:
            return {}

        neige = self.coordinator.data["neige_fraiche"]
        mesures = neige.get("mesures", [])

        attrs = {
            "altitude_mesure_m": neige.get("altitude_ss"),
            "last_update": self.coordinator.data.get("date"),
        }

        # Add measurements as a structured list
        attrs["mesures"] = [
            {
                "date": mesure.get("date"),
                "min_cm": mesure.get("min"),
                "max_cm": mesure.get("max")
            }
            for mesure in mesures
        ]

        return attrs


class MeteoFranceMontagneRisqueJ2Sensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Forecast Risk Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return None
        risque = self.coordinator.data["risque"]
        if "estimation_j2" not in risque or not risque["estimation_j2"]:
            return None
        risk_value = risque["estimation_j2"].get("risque_max")
        return AVALANCHE_RISK.get(str(risk_value), risk_value)

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return None
        risque = self.coordinator.data["risque"]
        if "estimation_j2" not in risque or not risque["estimation_j2"]:
            return None
        risk_value = risque["estimation_j2"].get("risque_max")
        return f"/api/meteofrance-montagne/resources/RISQUE/{risk_value}_transparent.png"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "risque" not in self.coordinator.data:
            return {}

        risque = self.coordinator.data["risque"]
        if "estimation_j2" not in risque or not risque["estimation_j2"]:
            return {}

        j2 = risque["estimation_j2"]
        risk_value = j2.get("risque_max")

        return {
            "risque_max_valeur": risk_value,
            "risque_max_texte": AVALANCHE_RISK.get(str(risk_value), ""),
            "risque_max_couleur": AVALANCHE_RISK_COLORS.get(str(risk_value), ""),
            "commentaire": j2.get("commentaire", "").replace("\n", " ").strip(),
            "description": j2.get("description", "").replace("\n", " ").strip(),
            "date_prevision": j2.get("date"),
            "last_update": self.coordinator.data.get("date"),
        }


class MeteoFranceMontagneStabiliteSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Stability Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "stabilite" not in self.coordinator.data:
            return None
        stabilite = self.coordinator.data["stabilite"]
        situations = stabilite.get("situations_avalancheuses", [])
        if situations and len(situations) > 0:
            situation_type = situations[0].get("type")
            return AVALANCHE_SITUATIONS.get(str(situation_type), situation_type)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "stabilite" not in self.coordinator.data:
            return {}

        stabilite = self.coordinator.data["stabilite"]
        attrs = {
            "titre": stabilite.get("titre", ""),
            "texte": stabilite.get("texte", "").replace("\n", " ").strip(),
            "last_update": self.coordinator.data.get("date"),
        }

        # Typical avalanche situations (SAT) as a structured list
        situations_list = stabilite.get("situations_avalancheuses", [])
        attrs["situations"] = [
            {
                "code": situation.get("type"),
                "type": AVALANCHE_SITUATIONS.get(str(situation.get("type")), "")
            }
            for situation in situations_list
        ]

        return attrs


class MeteoFranceMontagneQualiteSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Météo-France Montagne Snow Quality Sensor."""

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._sensor_type = sensor_type
        self._attr_name = f"{coordinator.massif_name} {name}"
        self._attr_unique_id = f"{coordinator.massif_id}_{sensor_type}"
        self._attr_icon = icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if not self.coordinator.data or "qualite" not in self.coordinator.data:
            return None
        qualite = self.coordinator.data["qualite"]
        # Return first 100 chars as state
        return qualite[:100] if qualite else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data or "qualite" not in self.coordinator.data:
            return {}

        return {
            "texte_complet": self.coordinator.data["qualite"],
            "last_update": self.coordinator.data.get("date"),
        }
