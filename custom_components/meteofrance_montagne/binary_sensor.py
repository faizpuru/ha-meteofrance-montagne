"""Binary sensors for Météo-France Montagne."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeteoFranceMontagneConfigEntry
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator
from .entity import MeteoFranceMontagneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoFranceMontagneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Météo-France Montagne binary sensors."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [MeteoFranceMontagneAvisSensor(coordinator)],
            config_subentry_id=subentry_id,
        )


class MeteoFranceMontagneAvisSensor(MeteoFranceMontagneEntity, BinarySensorEntity):
    """On when the bulletin carries a high or very high avalanche risk warning."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_translation_key = "avis_risque_fort"
    _attr_icon = "mdi:alert-octagon"

    def __init__(self, coordinator: MeteoFranceMontagneDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, "avis_risque_fort")

    @property
    def _avis(self) -> str | None:
        """Return the warning text, None without bulletin."""
        data = self.coordinator.data
        if not data or data.get("hors_saison"):
            return None
        return data["risque"].get("avis", "")

    @property
    def is_on(self) -> bool | None:
        """Return true when a warning is issued."""
        if (avis := self._avis) is None:
            return None
        return bool(avis)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the warning text."""
        if (avis := self._avis) is None:
            return {}
        return {"avis": avis}
