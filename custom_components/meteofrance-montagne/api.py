"""API for Météo-France Montagne."""
import aiohttp
import asyncio
import logging
import json
from lxml import etree


from .const import TIMEOUT, BASE_URL

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class MeteoFranceMontagneApi:

    def __init__(self, session: aiohttp.ClientSession, hass: HomeAssistant, token: str):
        """Initialize the API."""
        self.session = session
        self.hass = hass
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

    def parse_bulletin_xml(self, xml_doc):
        """Parse XML bulletin and convert to JSON structure."""
        root = xml_doc

        def get_attr(element, attr, default=''):
            """Get attribute value or default."""
            value = element.get(attr, default)
            return value if value else default

        def get_text(element, default=''):
            """Get element text or default."""
            if element is not None and element.text:
                return element.text.strip()
            return default

        def to_int_or_null(value):
            """Convert to int or None."""
            if value and value != '':
                try:
                    return int(value)
                except ValueError:
                    return None
            return None

        # Parse CARTOUCHERISQUE
        cartouche = root.find('CARTOUCHERISQUE')
        risque_elem = cartouche.find('RISQUE') if cartouche is not None else None
        pente_elem = cartouche.find('PENTE') if cartouche is not None else None

        risque = {
            'risque_max': get_attr(risque_elem, 'RISQUEMAXI') if risque_elem is not None else '',
            'risque_1': {
                'valeur': get_attr(risque_elem, 'RISQUE1') if risque_elem is not None else '',
                'evolution': get_attr(risque_elem, 'EVOLURISQUE1') if risque_elem is not None else '',
                'localisation': get_attr(risque_elem, 'LOC1') if risque_elem is not None else ''
            },
            'risque_2': {
                'valeur': get_attr(risque_elem, 'RISQUE2') if risque_elem is not None else '',
                'evolution': get_attr(risque_elem, 'EVOLURISQUE2') if risque_elem is not None else '',
                'localisation': get_attr(risque_elem, 'LOC2') if risque_elem is not None else ''
            },
            'altitude_limite': to_int_or_null(get_attr(risque_elem, 'ALTITUDE')) if risque_elem is not None else None,
            'commentaire': get_attr(risque_elem, 'COMMENTAIRE') if risque_elem is not None else '',
            'naturel': get_text(cartouche.find('NATUREL')) if cartouche is not None else '',
            'accidentel': get_text(cartouche.find('ACCIDENTEL')) if cartouche is not None else '',
            'resume': get_text(cartouche.find('RESUME')) if cartouche is not None else '',
            'estimation_j2': {
                'date': get_attr(risque_elem, 'DATE_RISQUE_J2') if risque_elem is not None else '',
                'risque_max': get_attr(risque_elem, 'RISQUEMAXIJ2') if risque_elem is not None else '',
                'description': get_text(cartouche.find('RisqueJ2')) if cartouche is not None else '',
                'commentaire': get_text(cartouche.find('CommentaireRisqueJ2')) if cartouche is not None else ''
            },
            'pentes_particulieres': {
                'NE': to_int_or_null(get_attr(pente_elem, 'NE')) if pente_elem is not None else None,
                'E': to_int_or_null(get_attr(pente_elem, 'E')) if pente_elem is not None else None,
                'SE': to_int_or_null(get_attr(pente_elem, 'SE')) if pente_elem is not None else None,
                'S': to_int_or_null(get_attr(pente_elem, 'S')) if pente_elem is not None else None,
                'SW': to_int_or_null(get_attr(pente_elem, 'SW')) if pente_elem is not None else None,
                'W': to_int_or_null(get_attr(pente_elem, 'W')) if pente_elem is not None else None,
                'NW': to_int_or_null(get_attr(pente_elem, 'NW')) if pente_elem is not None else None,
                'N': to_int_or_null(get_attr(pente_elem, 'N')) if pente_elem is not None else None,
                'commentaire': get_attr(pente_elem, 'COMMENTAIRE') if pente_elem is not None else ''
            }
        }

        # Parse STABILITE
        stabilite_elem = root.find('STABILITE')
        situations_avalancheuses = []
        if stabilite_elem is not None:
            sitaval = stabilite_elem.find('SitAvalTyp')
            if sitaval is not None:
                sat1 = get_attr(sitaval, 'SAT1')
                if sat1:
                    situations_avalancheuses.append({'type': sat1})
                sat2 = get_attr(sitaval, 'SAT2')
                if sat2:
                    situations_avalancheuses.append({'type': sat2})

        stabilite = {
            'situations_avalancheuses': situations_avalancheuses,
            'titre': get_text(stabilite_elem.find('TITRE')) if stabilite_elem is not None else '',
            'texte': get_text(stabilite_elem.find('TEXTE')) if stabilite_elem is not None else ''
        }

        # Parse QUALITE
        qualite_elem = root.find('QUALITE')
        qualite = get_text(qualite_elem.find('TEXTE')) if qualite_elem is not None else ''

        # Parse ENNEIGEMENT
        enneigement_elem = root.find('ENNEIGEMENT')
        niveaux = []
        if enneigement_elem is not None:
            for niveau in enneigement_elem.findall('NIVEAU'):
                niveaux.append({
                    'altitude': to_int_or_null(get_attr(niveau, 'ALTI')),
                    'nord': to_int_or_null(get_attr(niveau, 'N')),
                    'sud': to_int_or_null(get_attr(niveau, 'S'))
                })

        enneigement = {
            'date': get_attr(enneigement_elem, 'DATE') if enneigement_elem is not None else '',
            'limite_sud': to_int_or_null(get_attr(enneigement_elem, 'LimiteSud')) if enneigement_elem is not None else None,
            'limite_nord': to_int_or_null(get_attr(enneigement_elem, 'LimiteNord')) if enneigement_elem is not None else None,
            'niveaux': niveaux
        }

        # Parse NEIGEFRAICHE
        neige_fraiche_elem = root.find('NEIGEFRAICHE')
        mesures = []
        if neige_fraiche_elem is not None:
            for neige24h in neige_fraiche_elem.findall('NEIGE24H'):
                mesures.append({
                    'date': get_attr(neige24h, 'DATE'),
                    'min': to_int_or_null(get_attr(neige24h, 'SS24Min')),
                    'max': to_int_or_null(get_attr(neige24h, 'SS24Max'))
                })

        neige_fraiche = {
            'altitude_ss': to_int_or_null(get_attr(neige_fraiche_elem, 'ALTITUDESS')) if neige_fraiche_elem is not None else None,
            'mesures': mesures
        }

        # Parse METEO
        meteo_elem = root.find('METEO')
        echeances = []
        if meteo_elem is not None:
            for echeance in meteo_elem.findall('ECHEANCE'):
                echeances.append({
                    'date': get_attr(echeance, 'DATE'),
                    'vent': {
                        'force_1': to_int_or_null(get_attr(echeance, 'FF1')),
                        'direction_1': get_attr(echeance, 'DD1'),
                        'force_2': to_int_or_null(get_attr(echeance, 'FF2')),
                        'direction_2': get_attr(echeance, 'DD2')
                    },
                    'iso_0': to_int_or_null(get_attr(echeance, 'ISO0')),
                    'pluie_neige': to_int_or_null(get_attr(echeance, 'PLUIENEIGE')),
                    'temps_sensible': to_int_or_null(get_attr(echeance, 'TEMPSSENSIBLE')),
                    'mer_nuages': to_int_or_null(get_attr(echeance, 'MERNUAGES'))
                })

        meteo = {
            'altitude_vent_1': to_int_or_null(get_attr(meteo_elem, 'ALTITUDEVENT1')) if meteo_elem is not None else None,
            'altitude_vent_2': to_int_or_null(get_attr(meteo_elem, 'ALTITUDEVENT2')) if meteo_elem is not None else None,
            'commentaire': get_text(meteo_elem.find('COMMENTAIRE')) if meteo_elem is not None else '',
            'echeances': echeances
        }

        # Build final structure
        result = {
            'type': 'bulletins_neige_avalanche',
            'id': get_attr(root, 'ID'),
            'massif': get_attr(root, 'MASSIF'),
            'dateBulletin': get_attr(root, 'DATEBULLETIN'),
            'dateEcheance': get_attr(root, 'DATEECHEANCE'),
            'dateValidite': get_attr(root, 'DATEVALIDITE'),
            'dateDiffusion': get_attr(root, 'DATEDIFFUSION'),
            'amendement': root.get('AMENDEMENT') == 'true',
            'risque': risque,
            'stabilite': stabilite,
            'qualite': qualite,
            'enneigement': enneigement,
            'neige_fraiche': neige_fraiche,
            'meteo': meteo
        }

        return result

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
            result = self.parse_bulletin_xml(xml_doc)
            return result

        except etree.XMLSyntaxError as e:
            _LOGGER.error("XML parsing error: %s", str(e))
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
