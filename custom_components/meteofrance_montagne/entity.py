"""Base entity for Météo-France Montagne."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, NIVO_ATTRIBUTION, OBSERVATION_MAX_AGE
from .coordinator import (
    MeteoFranceMontagneDataUpdateCoordinator,
    MeteoFranceNivoDataUpdateCoordinator,
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.massif_id))},
            name=coordinator.massif_name,
            manufacturer="Météo-France",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def attribution(self) -> str:
        """Return the credits of the bulletin."""
        return (self.coordinator.data or {}).get("attribution") or ATTRIBUTION


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
        massif_id: int,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._station_id = station_id
        self._attr_unique_id = f"station_{station_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"station_{station_id}")},
            name=station_name,
            manufacturer="Météo-France",
            model="Station nivo-météorologique",
            entry_type=DeviceEntryType.SERVICE,
            via_device=(DOMAIN, str(massif_id)),
        )

    @property
    def observation(self) -> dict | None:
        """Return the last observation of the station, None when too old."""
        if (observation := self.last_observation) is None:
            return None
        try:
            observed_at = dt_util.parse_datetime(observation["date"])
        except (KeyError, TypeError, ValueError):
            return None
        if observed_at is None or dt_util.utcnow() - observed_at > timedelta(
            hours=OBSERVATION_MAX_AGE
        ):
            return None
        return observation

    @property
    def last_observation(self) -> dict | None:
        """Return the last observation of the station, whatever its age."""
        return (self.coordinator.data or {}).get(self._station_id)
