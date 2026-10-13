"""Coordinator for fetching Météo-France Montagne data."""
import asyncio
from datetime import timedelta, datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
import aiohttp

from .api import (
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
    MeteoFranceMontagneOffSeason,
)
from .const import DOMAIN, IMAGE_TYPES, OFF_SEASON_UPDATE_INTERVAL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


def parse_bulletin_time(value: str) -> datetime:
    """Parse a bulletin time, a French local time unless it carries an offset."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_time_zone("Europe/Paris"))
    return dt_util.as_utc(parsed)


class MeteoFranceMontagneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to coordinate data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
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
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL),
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            data = await self._async_fetch()
        except MeteoFranceMontagneOffSeason as off_season:
            return self._off_season_data(str(off_season))
        except MeteoFranceMontagneAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except MeteoFranceMontagneApiError as error:
            raise UpdateFailed(
                f"Error fetching data for massif {self.massif_name}: {error}") from error
        except (KeyError, ValueError) as error:
            raise UpdateFailed(
                f"Invalid bulletin for massif {self.massif_name}: {error}") from error

        if self.update_interval != timedelta(hours=UPDATE_INTERVAL):
            _LOGGER.info("Bulletins are back for massif %s", self.massif_name)
            self.update_interval = timedelta(hours=UPDATE_INTERVAL)
        return data

    def _off_season_data(self, message: str) -> dict:
        """Return the data of a massif without bulletin, polled less often."""
        if self.update_interval != timedelta(hours=OFF_SEASON_UPDATE_INTERVAL):
            _LOGGER.info(
                "No bulletin for massif %s outside the season: %s",
                self.massif_name,
                message,
            )
            self.update_interval = timedelta(hours=OFF_SEASON_UPDATE_INTERVAL)
        # Download the images again with the first bulletin of the season
        self.updated_at = None
        return {
            "hors_saison": True,
            "message": message,
            "massif_name": self.massif_name,
        }

    async def _async_fetch(self):
        """Fetch the bulletin, and the images when the bulletin has changed."""
        bulletin = await self.api.bulletin(self.massif_id)
        bulletin_date = bulletin["dateBulletin"]
        bulletin_datetime = parse_bulletin_time(bulletin_date)

        # Check if bulletin date has changed since last update
        if self.data and bulletin_datetime == self.updated_at:
            _LOGGER.debug(
                "Bulletin date unchanged (%s) for massif %s, skipping image download",
                bulletin_date,
                self.massif_name
            )
            # Return existing data without re-downloading images
            return self.data

        # Bulletin has changed or first fetch, download everything
        _LOGGER.debug(
            "Bulletin date changed (old: %s, new: %s) for massif %s, downloading images",
            self.updated_at,
            bulletin_datetime,
            self.massif_name
        )

        # Fetch the images in parallel
        contents = await asyncio.gather(*(
            getattr(self.api, image_type)(self.massif_id) for image_type in IMAGE_TYPES
        ))
        images = dict(zip(IMAGE_TYPES, contents))

        # Only mark the bulletin as processed once everything was downloaded
        self.updated_at = bulletin_datetime

        return {
            "date": bulletin_date,
            "date_validite": bulletin["dateValidite"],
            "amendement": bulletin["amendement"],
            "attribution": bulletin["partenaires"],
            "risque": bulletin["risque"],
            "qualite": bulletin["qualite"],
            "enneigement": bulletin["enneigement"],
            "neige_fraiche": bulletin["neige_fraiche"],
            "stabilite": bulletin["stabilite"],
            "meteo": bulletin["meteo"],
            "massif_name": self.massif_name,
            **images
        }
