"""Base entity for Météo-France Montagne."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from meteofrance_montagne import Observation

from .const import ATTRIBUTION, DOMAIN, NIVO_ATTRIBUTION, OBSERVATION_MAX_AGE
from .coordinator import (
    MeteoFranceMontagneDataUpdateCoordinator,
    MeteoFranceNivoDataUpdateCoordinator,
)


def massif_device_info(massif_id: int, massif_name: str) -> DeviceInfo:
    """Return the device info of a massif."""
    return DeviceInfo(
        identifiers={(DOMAIN, str(massif_id))},
        name=massif_name,
        manufacturer="Météo-France",
        entry_type=DeviceEntryType.SERVICE,
    )


def station_device_info(station_id: str, station_name: str) -> DeviceInfo:
    """Return the device info of an observation station."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"station_{station_id}")},
        name=station_name,
        manufacturer="Météo-France",
        model="Station nivo-météorologique",
        entry_type=DeviceEntryType.SERVICE,
    )


class MeteoFranceMontagneEntity(
    CoordinatorEntity[MeteoFranceMontagneDataUpdateCoordinator]
):
    """Entity of a massif, grouped under the massif device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MeteoFranceMontagneDataUpdateCoordinator, key: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        # Massifs are unique across the integration (single config entry)
        self._attr_unique_id = f"{coordinator.massif_id}_{key}"
        self._attr_device_info = massif_device_info(
            coordinator.massif_id, coordinator.massif_name
        )

    @property
    def attribution(self) -> str:
        """Return the credits of the bulletin."""
        bulletin = self.coordinator.data.bulletin if self.coordinator.data else None
        return (bulletin.partenaires if bulletin else "") or ATTRIBUTION


class MeteoFranceMontagneStationEntity(
    CoordinatorEntity[MeteoFranceNivoDataUpdateCoordinator]
):
    """Entity of an observation station, grouped under the station device."""

    _attr_has_entity_name = True
    _attr_attribution = NIVO_ATTRIBUTION

    def __init__(
        self,
        coordinator: MeteoFranceNivoDataUpdateCoordinator,
        station_id: str,
        station_name: str,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_unique_id = f"station_{station_id}_{key}"
        self._attr_device_info = station_device_info(station_id, station_name)

    @property
    def observation(self) -> Observation | None:
        """Return the last observation of the station, None when too old."""
        if (observation := self.last_observation) is None:
            return None
        try:
            observed_at = dt_util.parse_datetime(observation.date)
        except ValueError:
            return None
        if observed_at is None or dt_util.utcnow() - observed_at > timedelta(
            hours=OBSERVATION_MAX_AGE
        ):
            return None
        return observation

    @property
    def last_observation(self) -> Observation | None:
        """Return the last observation of the station, whatever its age."""
        return (self.coordinator.data or {}).get(self._station_id)
