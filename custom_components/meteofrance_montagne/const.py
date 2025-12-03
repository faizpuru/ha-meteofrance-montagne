DOMAIN = "meteofrance_montagne"
TIMEOUT = 5
BASE_URL = "https://public-api.meteofrance.fr/public/DPBRA/v1"
NAME = "Météo-France Montagne"
CONF_MASSIF = "massif"
CONF_TOKEN = "token"
DEFAULT_TOKEN = ""
UPDATE_INTERVAL = 1
IMAGE_TYPES = [
    "rose_pentes",
    "montagne_risques",
    "montagne_enneigement",
    "graphe_neige_fraiche",
    "apercu_meteo",
    "sept_derniers_jours"
]
# Note: sept_derniers_jours_portrait existe dans le XML mais n'est pas accessible via l'API images

# European avalanche risk scale (1-5)
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

# Weather condition codes
WEATHER_CONDITIONS = {
    0: "Dégagé",
    1: "Peu nuageux",
    2: "Nuageux",
    3: "Très nuageux",
    4: "Couvert",
    6: "Voilé",
    7: "Mer de nuages",
    32: "Brouillard",
    38: "Brouillard givrant",
    51: "Pluie faible",
    53: "Pluie forte",
    58: "Pluie et neige mêlées",
    59: "Pluie verglaçante",
    61: "Neige faible",
    63: "Neige forte",
    70: "Averses",
    71: "Averses éparses",
    77: "Averses de pluie et neige",
    80: "Averses de neige",
    85: "Averses de grêle",
    90: "Orages",
    99: "Violents orages"
}
