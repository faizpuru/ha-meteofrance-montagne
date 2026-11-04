"""Names of the stations of the nivo-meteorological network."""
import re

# The nivo file gives technical names ("CEILLAC_NIVO", "ST FRANCOIS LONG"):
# usual names of the stations, keyed by WMO id as written in the file
STATION_NAMES = {
    "7393": "Le Tour (Balme)",
    "7454": "Bernex",
    "7457": "Vacheresse",
    "7466": "Saint-Sorlin-d'Arves",
    "7470": "La Flégère",
    "7498": "Val d'Isère (Joseray)",
    "7499": "Chamonix",
    "7566": "Bonneval-sur-Arc",
    "7567": "Val Cenis (La Berche)",
    "7575": "Montgenèvre",
    "7582": "Olmet",
    "7583": "Les 2 Alpes (Jandri)",
    "7584": "La Bérarde",
    "7585": "Font d'Urle",
    "7589": "Saint-Christophe-en-Oisans",
    "7590": "Les Portes-en-Valgaudemar",
    "7595": "Super Dévoluy 2",
    "7596": "Réallon",
    "7598": "Le Sauze",
    "7599": "Super Dévoluy",
    "7608": "Iraty",
    "7696": "Estenc",
    "7708": "La Grave 3200 m",
    "7709": "Névache",
    "7711": "Sainte-Foy-Tarentaise",
    "7715": "Risoul",
    "7721": "Les Carroz (Kédeusaz)",
    "7725": "Boutx (Le Mourtis)",
    "7730": "Goulier",
    "7746": "Le Chioula",
    "7811": "L'Alpe d'Huez 2350",
    "7813": "La Giettaz",
    "7815": "Orelle",
    "7818": "Gresse-en-Vercors",
    "7856": "Flaine",
    "7858": "Avoriaz",
    "7859": "Le Semnoz",
    "7861": "Châtel",
    "7863": "La Norma",
    "7865": "Plateau de Cacadogne",
    "7872": "Prapoutel",
    "7873": "Le Tour",
    "7875": "L'Alpe d'Huez (SATA)",
    "7876": "Le Grand-Bornand",
    "7877": "Le Collet d'Allevard",
    "7878": "Auris-en-Oisans",
    "7881": "Les 2 Alpes (Toura)",
    "7882": "L'Alpe du Grand-Serre",
    "7884": "Les Aillons (Margériaz)",
    "7885": "Les Karellis",
    "7886": "Villard-de-Lans (Côte 2000)",
    "7887": "La Clusaz",
    "7888": "Valmeinier",
    "7889": "Les Menuires",
    "7890": "Val Fréjus",
    "7891": "Arêches",
    "7892": "Méribel-Mottaret",
    "7893": "Courchevel",
    "7894": "Valmorel",
    "7895": "La Plagne",
    "7896": "Pralognan-la-Vanoise",
    "7897": "Les Contamines-Montjoie",
    "7900": "Les Arcs",
    "7901": "La Rosière",
    "7902": "Chamrousse (Niverolles)",
    "7903": "Lans-en-Vercors",
    "7904": "Tignes",
    "7907": "Le Corbier",
    "7908": "Lognan",
    "7911": "Les Saisies",
    "7912": "Bessans",
    "7915": "La Grave (La Meije)",
    "7916": "Saint-François-Longchamp",
    "7918": "Val Thorens",
    "7919": "Orcières",
    "7920": "Vaujany",
    "7921": "Puy-Saint-Vincent",
    "7922": "Valloire",
    "7923": "Les Orres",
    "7925": "Serre Chevalier (Chantemerle)",
    "7926": "Serre Chevalier (Le Monêtier)",
    "7927": "Pra-Loup",
    "7928": "Les Gets",
    "7929": "Vars",
    "7930": "Molines-en-Queyras",
    "7931": "Ceillac",
    "7933": "Maljasset",
    "7936": "Abriès",
    "7939": "Isola",
    "7940": "La Foux d'Allos",
    "7941": "Valberg",
    "7942": "Auron",
    "7943": "La Pierre-Saint-Martin",
    "7949": "Artouste",
    "7950": "Gourette",
    "7952": "Cauterets (Lys)",
    "7953": "Luz-Ardiden",
    "7954": "Saint-Paul-d'Oueil",
    "7955": "Gavarnie (Espécières)",
    "7957": "Barèges",
    "7958": "Hautacam",
    "7959": "Piau-Engaly",
    "7960": "Nistos",
    "7964": "Saint-Lary (Lita)",
    "7965": "Val Louron",
    "7966": "Sentein (Eylie)",
    "7968": "Les Agudes",
    "7969": "Superbagnères",
    "7970": "Plateau de Beille",
    "7971": "Guzet",
    "7972": "Ax-les-Thermes (Saquet)",
    "7973": "Monts d'Olmes",
    "7974": "Ascou-Pailhères",
    "7976": "Mijanès",
    "7977": "Porté-Puymorens",
    "7979": "Puigmal",
    "7980": "Font-Romeu (Galinera)",
    "7981": "Les Angles",
    "7982": "Formiguères",
    "7984": "Cambre d'Aze",
    "7985": "Vergio",
    "7986": "Bastelica",
    "7987": "Asco (Stagnu)",
    "7989": "Ghisoni (Capaghjolu)",
    "7990": "Capcir (nordique)",
}

# Words left in lower case inside a name
_LOWER_WORDS = {"d", "de", "des", "du", "en", "et", "l", "la", "le", "les", "sur"}


def _clean_station_name(name: str) -> str:
    """Make a technical name readable, without its accents."""
    # "SUPER DEVOLUY_NIVO2", "VAUJANY-NIVO", "CHATEL NIVO"
    name = re.sub(r"[\s_-]*NIVO(\d*)$", r" \1", name.strip(), flags=re.IGNORECASE)
    name = re.sub(r"[\s_]+", " ", name).strip()
    if name.isupper():
        words = [
            word.lower() if index and word.lower() in _LOWER_WORDS else word.capitalize()
            for index, word in enumerate(name.split(" "))
        ]
        name = " ".join(words)
        # Capitalize after a hyphen too: "Serre Che-chantemerle"
        name = re.sub(r"-(\w)", lambda match: "-" + match.group(1).upper(), name)
    # "Val d Isere", "L Alpe d Huez"
    return re.sub(r"\b([dlDL]) (?=[aeiouyhAEIOUYH])", r"\1'", name)


def station_name(station_id: str, name: str) -> str:
    """Return the usual name of a station."""
    return STATION_NAMES.get(station_id) or _clean_station_name(name)
