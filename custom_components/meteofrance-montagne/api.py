"""API for Meteo France Montagne."""
from urllib import response
import aiohttp
import asyncio
import logging
import json
from lxml import etree
from .xslt.BulletinToJson import xslt as xslt_content


from .const import TIMEOUT, BASE_URL

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class MeteoFranceMontagneApi:

    def __init__(self, session: aiohttp.ClientSession, hass: HomeAssistant, token: str):
        """Initialize the API."""
        self.session = session
        self.hass = hass
        xslt_doc = etree.fromstring(xslt_content.encode('utf-8'))
        self.transform = etree.XSLT(xslt_doc)
        self.token = token

    def organize_by_department(self, json_data):
        """Organize massifs by department."""
        department_map = {}

        for feature in json_data['features']:
            properties = feature['properties']

            # Debug log if needed
            if not department_map:  # Log only for the first one
                _LOGGER.debug("Properties keys: %s", list(properties.keys()))

            massif_info = {
                'title': properties.get('title', 'Unknown'),
                'code': properties.get('code', 'Unknown')
            }

            # Try different key name variants
            dep = properties.get('Departemen') or properties.get('departement') or properties.get('Departement')
            if dep:
                if dep not in department_map:
                    department_map[dep] = []
                department_map[dep].append(massif_info)

            # Check for second department
            dep2 = properties.get('Dep2') or properties.get('dep2') or properties.get('Departement2')
            if dep2 and dep2 not in department_map:
                department_map[dep2] = []
            if dep2:
                department_map[dep2].append(massif_info)

        return department_map

    async def list_massif(self):
        """Get list of massifs organized by department."""
        response = await self.call_api(f"{BASE_URL}/liste-massifs")
        if response is None:
            raise Exception("Failed to fetch massifs list from API")
        json_data = self.as_json(response)
        by_department = self.organize_by_department(json_data)
        return by_department

    async def bulletin(self, massif):
        """Get avalanche bulletin for a massif."""
        response = await self.call_api(f"{BASE_URL}/massif/BRA?id-massif={massif}&format=xml")
        try:
            xml_doc = etree.fromstring(response)
            result = self.transform(xml_doc)
            json_str = str(result)
            # _LOGGER.debug("JSON from XSLT: %s", json_str)

            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                _LOGGER.error("JSON decode error: %s", str(e))
                _LOGGER.error("Problematic JSON (first 1000 chars): %s", json_str[:1000])
                return None

        except (etree.XMLSyntaxError, etree.XSLTError) as e:
            _LOGGER.error("XSLT transformation error: %s", str(e))
            return None

    async def image(self, image_type, massif):
        """Get image for a massif."""
        url = f"{BASE_URL}/massif/image/{image_type}?id-massif={massif}"
        result = await self.call_api(url)
        return result

    async def rose_pentes(self, massif):
        return await self.image("rose-pentes", massif)

    async def montagne_risques(self, massif):
        return await self.image("montagne-risques", massif)

    async def montagne_enneigement(self, massif):
        return await self.image("montagne-enneigement", massif)

    async def graphe_neige_fraiche(self, massif):
        return await self.image("graphe-neige-fraiche", massif)

    async def apercu_meteo(self, massif):
        return await self.image("apercu-meteo", massif)

    async def sept_derniers_jours(self, massif):
        return await self.image("sept-derniers-jours", massif)

    def as_json(self, bytes_data):
        """Convert bytes data to JSON."""
        string_data = bytes_data.decode('utf-8')
        json_data = json.loads(string_data)
        return json_data

    async def call_api(self, url):
        """Fetch data from a given URL."""
        try:
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            _LOGGER.debug("Executing URL fetch: %s", url)
            headers = {
                "accept": "*/*",
                "apikey": self.token
            }
            async with self.session.get(url, timeout=timeout, headers=headers) as response:
                if response.status == 401:
                    _LOGGER.error("Authentication failed (401). Check your API token.")
                    raise Exception("Invalid API token (401 Unauthorized)")
                if response.status != 200:
                    _LOGGER.error(
                        "HTTP request failed with status: %s for url: %s",
                        response.status,
                        url,
                    )
                    raise Exception(f"HTTP {response.status} error")
                return await response.read()

        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Client error during HTTP request for url: %s. Exception: %s", url, e)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error while fetching data from url: %s", url)
            raise
        except Exception as e:
            if "Invalid API token" in str(e) or "HTTP" in str(e):
                raise
            _LOGGER.error(
                "Unexpected exception with url: %s. Exception: %s", url, e)
            raise
