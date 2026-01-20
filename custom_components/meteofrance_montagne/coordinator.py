"""Coordinator for fetching Météo-France Montagne data."""
from datetime import timedelta, datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
import aiohttp
import homeassistant.util.dt as dt_util

from .api import MeteoFranceMontagneApi
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MeteoFranceMontagneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to coordinate data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        massif_id: str,
        massif_name: str,
        token: str
    ) -> None:
        """Initialize."""
        self.api = MeteoFranceMontagneApi(session, hass, token)
        self.massif_id = massif_id
        self.massif_name = massif_name
        self.updated_at = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            bulletin = await self.api.bulletin(self.massif_id)
            bulletin_date = bulletin["dateBulletin"]
            bulletin_datetime = datetime.fromisoformat(bulletin_date)

            # Check if bulletin date has changed since last update
            if self.updated_at is not None and bulletin_datetime == self.updated_at:
                _LOGGER.debug(
                    "Bulletin date unchanged (%s) for massif %s, skipping image download",
                    bulletin_date,
                    self.massif_name
                )
                # Return existing data without re-downloading images
                if self.data:
                    return self.data

            # Bulletin has changed or first fetch, download everything
            _LOGGER.debug(
                "Bulletin date changed (old: %s, new: %s) for massif %s, downloading images",
                self.updated_at,
                bulletin_datetime,
                self.massif_name
            )
            self.updated_at = bulletin_datetime

            # Fetch different images
            images = {
                "rose_pentes": await self.api.rose_pentes(self.massif_id),
                "montagne_risques": await self.api.montagne_risques(self.massif_id),
                "montagne_enneigement": await self.api.montagne_enneigement(self.massif_id),
                "graphe_neige_fraiche": await self.api.graphe_neige_fraiche(self.massif_id),
                "apercu_meteo": await self.api.apercu_meteo(self.massif_id),
                "sept_derniers_jours": await self.api.sept_derniers_jours(self.massif_id)
            }

            return {
                "date": bulletin_date,
                "risque": bulletin["risque"],
                "qualite": bulletin["qualite"],
                "enneigement": bulletin["enneigement"],
                "neige_fraiche": bulletin["neige_fraiche"],
                "stabilite": bulletin["stabilite"],
                "meteo": bulletin["meteo"],
                "massif_name": self.massif_name,
                **images
            }

        except Exception as error:
            _LOGGER.error("Error fetching data: %s", error)
            return None
