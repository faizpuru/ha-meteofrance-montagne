"""Coordinator for fetching Météo-France Montagne data."""
import asyncio
from dataclasses import dataclass, field
from datetime import timedelta, datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
import aiohttp
from meteofrance_montagne import (
    Bulletin,
    MeteoFranceMontagneApi,
    MeteoFranceMontagneApiError,
    MeteoFranceMontagneAuthError,
    MeteoFranceMontagneOffSeason,
    MeteoFranceNivoApi,
    Observation,
)

from .const import (
    DOMAIN,
    IMAGE_TYPES,
    OBSERVATION_MAX_AGE,
    OFF_SEASON_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def parse_bulletin_time(value: str) -> datetime:
    """Parse a bulletin time, a French local time unless it carries an offset."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_time_zone("Europe/Paris"))
    return dt_util.as_utc(parsed)


@dataclass(frozen=True, slots=True)
class MassifData:
    """Bulletin of a massif and its images, or the reason why there is none."""

    # None outside the season
    bulletin: Bulletin | None
    # PNG of each image type, None when not published
    images: dict[str, bytes | None] = field(default_factory=dict)
    # Message of Météo-France outside the season
    message: str = ""


class MeteoFranceMontagneDataUpdateCoordinator(DataUpdateCoordinator[MassifData]):
    """Class to coordinate data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: aiohttp.ClientSession,
        massif_id: int,
        massif_name: str,
        token: str
    ) -> None:
        """Initialize."""
        self.api = MeteoFranceMontagneApi(session, token)
        self.massif_id = massif_id
        self.massif_name = massif_name
        self.updated_at: datetime | None = None
        # Writing and diffusion times of the bulletin whose images were downloaded
        self._published: tuple[datetime, str] | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> MassifData:
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

    def _off_season_data(self, message: str) -> MassifData:
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
        self._published = None
        return MassifData(bulletin=None, message=message)

    async def _async_fetch(self) -> MassifData:
        """Fetch the bulletin, and the images when a new bulletin is published."""
        bulletin = await self.api.bulletin(self.massif_id)
        bulletin_date = bulletin.date_bulletin
        bulletin_datetime = parse_bulletin_time(bulletin_date)
        # An amended bulletin may keep its writing time, not its diffusion time
        published = (bulletin_datetime, bulletin.date_diffusion)

        if self.data and published == self._published:
            _LOGGER.debug(
                "Bulletin unchanged (%s) for massif %s, skipping image download",
                bulletin_date,
                self.massif_name
            )
            # Keep the images, the texts are taken from the bulletin just read
            images = self.data.images
        else:
            _LOGGER.debug(
                "New bulletin (old: %s, new: %s) for massif %s, downloading images",
                self._published,
                published,
                self.massif_name
            )

            # Fetch the images in parallel
            contents = await asyncio.gather(*(
                getattr(self.api, image_type)(self.massif_id) for image_type in IMAGE_TYPES
            ))
            images = dict(zip(IMAGE_TYPES, contents))

            # Only mark the bulletin as processed once everything was downloaded
            self.updated_at = bulletin_datetime
            self._published = published

        return MassifData(bulletin=bulletin, images=images)


class MeteoFranceNivoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Observation]]):
    """Coordinate the observations of all the stations, read from the same file."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize."""
        self.api = MeteoFranceNivoApi(session)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_observations",
            # Cheap while the file is unchanged, answered 304
            update_interval=timedelta(hours=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Observation]:
        """Fetch the last observation of each station."""
        now = dt_util.utcnow()
        # Early January, the last observations are still in the previous file
        years = sorted({
            now.year,
            (now - timedelta(hours=OBSERVATION_MAX_AGE)).year,
        })
        try:
            files = await asyncio.gather(*(self.api.observations(year) for year in years))
        except MeteoFranceMontagneApiError as error:
            raise UpdateFailed(f"Error fetching the observations: {error}") from error

        observations = {}
        for observations_of_year in files:
            observations.update(observations_of_year)
        return observations
