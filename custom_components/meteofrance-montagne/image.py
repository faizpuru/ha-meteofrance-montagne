"""Support for Meteo France Montagne images."""
from __future__ import annotations

import logging
from typing import Any
import secrets
from homeassistant.components.image import ImageEntity, Image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN, IMAGE_TYPES
from .coordinator import MeteoFranceMontagneDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Meteo France Montagne image platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for image_type in IMAGE_TYPES:
        entities.append(
            MeteoFranceMontagneImage(
                coordinator,
                image_type
            )
        )

    async_add_entities(entities)


class MeteoFranceMontagneImage(CoordinatorEntity, ImageEntity):
    """Representation of a Météo France Montagne image."""

    _attr_content_type = "image/png"

    def __init__(
        self,
        coordinator: MeteoFranceMontagneDataUpdateCoordinator,
        image_type: str,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(coordinator)
        self._image_type = image_type
        self._attr_unique_id = f"{coordinator.massif_id}_{image_type}"
        self._attr_name = f"{coordinator.massif_name} {
            image_type.replace('_', ' ').title()}"
        self._access_tokens = [secrets.token_hex()]
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

    @property
    def access_tokens(self) -> list[str]:
        """Return access tokens."""
        return self._access_tokens

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if hasattr(self, '_cached_image') and self._cached_image:
            return self._cached_image.content
        return None
