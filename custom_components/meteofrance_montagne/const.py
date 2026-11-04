DOMAIN = "meteofrance_montagne"
TIMEOUT = 5
BASE_URL = "https://public-api.meteofrance.fr/public/DPBRA/v1"
API_PORTAL_URL = "https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesBRA"
NAME = "Météo-France Montagne"
ATTRIBUTION = "Données Météo-France"
NIVO_ATTRIBUTION = "Données Météo-France, réseau nivo-météorologique"
CONF_MASSIF = "massif"
CONF_MASSIF_NAME = "massif_name"
CONF_TOKEN = "token"
SUBENTRY_TYPE_MASSIF = "massif"
# Observation stations of a massif, names keyed by station id
CONF_STATIONS = "stations"
DEFAULT_TOKEN = ""
UPDATE_INTERVAL = 1
OFF_SEASON_UPDATE_INTERVAL = 6
RESOURCES_URL = "/api/meteofrance_montagne/resources"

# Observations of the nivo-meteorological network, one file per year rebuilt
# every morning, published without key
NIVO_URL = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/OBS/NIVOSE/nivo_{year}.csv.gz"
NIVO_TIMEOUT = 30
# Hours: the morning observation is published the next morning, older ones
# come from a station that stopped observing
OBSERVATION_MAX_AGE = 72
IMAGE_TYPES = [
    "rose_pentes",
    "montagne_risques",
    "montagne_enneigement",
    "graphe_neige_fraiche",
    "apercu_meteo",
    "sept_derniers_jours"
]
# Note: sept_derniers_jours_portrait existe dans le XML mais n'est pas accessible via l'API images

# European avalanche risk scale (1-5), also the sensor state options
AVALANCHE_RISK_LEVELS = ["1", "2", "3", "4", "5"]
AVALANCHE_RISK = {
    "1": "Faible",
    "2": "Limité",
    "3": "Marqué",
    "4": "Fort",
    "5": "Très Fort"
}

# Avalanche risk colors (official European scale)
AVALANCHE_RISK_COLORS = {
    "1": "#CCFF66",  # Green
    "2": "#FFFF00",  # Yellow
    "3": "#FF9900",  # Orange
    "4": "#FF0000",  # Red
    "5": "#990000"   # Dark red
}

# Typical avalanche situations (SAT - Situations Avalancheuses Typiques)
AVALANCHE_SITUATIONS = {
    "1": "Neige fraîche",
    "2": "Neige ventée",
    "3": "Couche fragile persistante",
    "4": "Neige humide",
    "5": "Neige glissante",
    "6": "Pas de situation avalancheuse typique prédominante"
}

# Weather condition codes (TEMPSSENSIBLE), from the official BRA XML description
WEATHER_CONDITIONS = {
    0: "Clair",
    1: "Peu nuageux",
    2: "Nuageux",
    3: "Très nuageux",
    4: "Couvert",
    5: "Variable",
    6: "Voilé",
    7: "Mer de nuages",
    30: "Brume/brouillard",
    31: "Brume",
    32: "Brouillard",
    33: "Brouillard dense",
    38: "Brouillard givrant",
    39: "Brouillard givrant dense",
    40: "Bruine",
    49: "Bruine verglaçante",
    50: "Pluie",
    51: "Pluie faible",
    52: "Pluie modérée",
    53: "Pluie forte",
    58: "Pluie et neige mêlées",
    59: "Pluie verglaçante",
    60: "Neige",
    61: "Neige faible",
    62: "Neige modérée",
    63: "Neige forte",
    70: "Averses",
    71: "Rares averses",
    72: "Rares averses avec ciel couvert",
    73: "Averses avec ciel couvert",
    77: "Averses de pluie et neige mêlées",
    78: "Averses de pluie et neige mêlées avec ciel couvert",
    80: "Averses de neige",
    81: "Rares averses de neige",
    82: "Rares averses de neige avec ciel couvert",
    83: "Averses de neige avec ciel couvert",
    84: "Averses de grésil",
    85: "Averses de grêle",
    90: "Orages",
    91: "Orages possibles",
    92: "Averses orageuses",
    93: "Orages avec pluie",
    97: "Orages avec neige",
    98: "Orages avec grêle",
    99: "Orages violents",
}

# Snow grain types (grain_predom, grain_nombre), from the nivo network description
SNOW_GRAINS = {
    1: "Neige fraîche",
    2: "Particules reconnaissables",
    3: "Grains fins",
    4: "Faces planes",
    5: "Gobelets",
    6: "Grains ronds",
    7: "Croûtes",
    8: "Givre de surface",
    9: "Neige roulée",
}

# Blowing snow at altitude (chasse_neige), named after the wind producing it
BLOWING_SNOW = {
    0: "Absente",
    1: "Depuis la dernière observation, absente actuellement",
    2: "Modérée d'Est",
    3: "Modérée de Sud",
    4: "Modérée d'Ouest",
    5: "Modérée de Nord",
    6: "Forte d'Est",
    7: "Forte de Sud",
    8: "Forte d'Ouest",
    9: "Forte de Nord",
}

# Present weather (ww) of the observations, WMO code table 4677. Codes 0 to 3
# only tell the evolution of the clouds: the sky is given by the cloud cover
PRESENT_WEATHER = {
    4: "Fumée",
    5: "Brume sèche",
    6: "Poussière en suspension",
    7: "Poussière ou sable soulevés",
    8: "Tourbillons de poussière",
    9: "Tempête de poussière en vue",
    10: "Brume",
    11: "Bancs de brouillard bas",
    12: "Brouillard bas",
    13: "Éclairs",
    14: "Précipitations en vue",
    15: "Précipitations au loin",
    16: "Précipitations à proximité",
    17: "Orage sans précipitations",
    18: "Grains",
    19: "Trombe",
    20: "Bruine récente",
    21: "Pluie récente",
    22: "Neige récente",
    23: "Pluie et neige récentes",
    24: "Précipitations verglaçantes récentes",
    25: "Averses de pluie récentes",
    26: "Averses de neige récentes",
    27: "Averses de grêle récentes",
    28: "Brouillard récent",
    29: "Orage récent",
    30: "Tempête de poussière",
    31: "Tempête de poussière",
    32: "Tempête de poussière",
    33: "Forte tempête de poussière",
    34: "Forte tempête de poussière",
    35: "Forte tempête de poussière",
    36: "Chasse-neige basse",
    37: "Forte chasse-neige basse",
    38: "Chasse-neige élevée",
    39: "Forte chasse-neige élevée",
    40: "Brouillard au loin",
    41: "Bancs de brouillard",
    42: "Brouillard en diminution",
    43: "Brouillard en diminution",
    44: "Brouillard",
    45: "Brouillard",
    46: "Brouillard en augmentation",
    47: "Brouillard en augmentation",
    48: "Brouillard givrant",
    49: "Brouillard givrant",
    50: "Bruine faible",
    51: "Bruine faible",
    52: "Bruine modérée",
    53: "Bruine modérée",
    54: "Bruine forte",
    55: "Bruine forte",
    56: "Bruine verglaçante faible",
    57: "Bruine verglaçante",
    58: "Bruine et pluie faibles",
    59: "Bruine et pluie",
    60: "Pluie faible",
    61: "Pluie faible",
    62: "Pluie modérée",
    63: "Pluie modérée",
    64: "Pluie forte",
    65: "Pluie forte",
    66: "Pluie verglaçante faible",
    67: "Pluie verglaçante",
    68: "Pluie et neige mêlées faibles",
    69: "Pluie et neige mêlées",
    70: "Neige faible",
    71: "Neige faible",
    72: "Neige modérée",
    73: "Neige modérée",
    74: "Neige forte",
    75: "Neige forte",
    76: "Poudrin de glace",
    77: "Neige en grains",
    78: "Cristaux de neige",
    79: "Granules de glace",
    80: "Averses de pluie faibles",
    81: "Averses de pluie",
    82: "Averses de pluie violentes",
    83: "Averses de pluie et neige faibles",
    84: "Averses de pluie et neige",
    85: "Averses de neige faibles",
    86: "Averses de neige",
    87: "Averses de grésil faibles",
    88: "Averses de grésil",
    89: "Averses de grêle faibles",
    90: "Averses de grêle",
    91: "Pluie faible après orage",
    92: "Pluie après orage",
    93: "Neige faible après orage",
    94: "Neige après orage",
    95: "Orage",
    96: "Orage avec grêle",
    97: "Orage fort",
    98: "Orage avec tempête de poussière",
    99: "Orage fort avec grêle",
}

# Sky from the total cloud cover in octas, 9 when hidden by fog
SKY_CONDITIONS = {
    0: "Ciel clair",
    1: "Peu nuageux",
    2: "Peu nuageux",
    3: "Nuageux",
    4: "Nuageux",
    5: "Nuageux",
    6: "Très nuageux",
    7: "Très nuageux",
    8: "Couvert",
    9: "Ciel invisible",
}
