DOMAIN = "meteofrance_montagne"
TIMEOUT = 5
BASE_URL = "https://public-api.meteofrance.fr/public/DPBRA/v1"
API_PORTAL_URL = "https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesBRA"
NAME = "Météo-France Montagne"
ATTRIBUTION = "Données Météo-France"
CONF_MASSIF = "massif"
CONF_MASSIF_NAME = "massif_name"
CONF_TOKEN = "token"
SUBENTRY_TYPE_MASSIF = "massif"
DEFAULT_TOKEN = ""
UPDATE_INTERVAL = 1
OFF_SEASON_UPDATE_INTERVAL = 6
RESOURCES_URL = "/api/meteofrance_montagne/resources"
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
