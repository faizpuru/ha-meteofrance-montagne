"""Support for Météo-France Montagne images."""
from __future__ import annotations

import logging
from homeassistant.components.image import ImageEntity, Image
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeteoFranceMontagneConfigEntry
from .const import IMAGE_TYPES
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator
from .entity import MeteoFranceMontagneEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoFranceMontagneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Météo-France Montagne image platform."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [
                MeteoFranceMontagneImage(coordinator, image_type)
                for image_type in IMAGE_TYPES
            ],
            config_subentry_id=subentry_id,
        )


class MeteoFranceMontagneImage(MeteoFranceMontagneEntity, ImageEntity):
    """Representation of a Météo-France Montagne image."""

    _attr_content_type = "image/png"

    def __init__(
        self,
        coordinator: MeteoFranceMontagneDataUpdateCoordinator,
        image_type: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator, image_type)
        # CoordinatorEntity does not chain __init__: set up the rotating access tokens
        ImageEntity.__init__(self, coordinator.hass)
        self._image_type = image_type
        self._attr_translation_key = image_type
        self._attr_image_last_updated = coordinator.updated_at
        if coordinator.data is not None:
            self._cached_image = Image(
                "image/png", coordinator.data.get(image_type))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data and self.coordinator.data.get(self._image_type):
            self._attr_image_last_updated = self.coordinator.updated_at
            self._cached_image = Image(
                "image/png", self.coordinator.data.get(self._image_type))
            self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if hasattr(self, '_cached_image') and self._cached_image:
            return self._cached_image.content
        return None
