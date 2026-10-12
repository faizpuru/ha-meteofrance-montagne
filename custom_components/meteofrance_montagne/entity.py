"""Base entity for Météo-France Montagne."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator


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
