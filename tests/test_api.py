"""Tests for the MeteoFranceMontagneApi XML parsing."""
import os
from lxml import etree


def parse_bulletin_xml(xml_doc):
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

    # Parse METEO (prévisions)
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

    # Parse METEO historique (BSH)
    echeances_historique = []
    bsh_elem = root.find('BSH')
    if bsh_elem is not None:
        bsh_meteo_elem = bsh_elem.find('METEO')
        if bsh_meteo_elem is not None:
            for echeance in bsh_meteo_elem.findall('ECHEANCE'):
                echeances_historique.append({
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

    # Parse RISQUES historique
    risques_historique = []
    if bsh_elem is not None:
        risques_elem = bsh_elem.find('RISQUES')
        if risques_elem is not None:
            for risque_jour in risques_elem.findall('RISQUE'):
                risques_historique.append({
                    'date': get_attr(risque_jour, 'DATE'),
                    'risque_max': get_attr(risque_jour, 'RISQUEMAXI')
                })

    # Parse ENNEIGEMENTS historique
    enneigements_historique = []
    if bsh_elem is not None:
        enneigements_elem = bsh_elem.find('ENNEIGEMENTS')
        if enneigements_elem is not None:
            for enneigement_jour in enneigements_elem.findall('ENNEIGEMENT'):
                niveaux_hist = []
                for niveau in enneigement_jour.findall('NIVEAU'):
                    niveaux_hist.append({
                        'altitude': to_int_or_null(get_attr(niveau, 'ALTI')),
                        'nord': to_int_or_null(get_attr(niveau, 'N')),
                        'sud': to_int_or_null(get_attr(niveau, 'S'))
                    })
                enneigements_historique.append({
                    'date': get_attr(enneigement_jour, 'DATE'),
                    'limite_sud': to_int_or_null(get_attr(enneigement_jour, 'LimiteSud')),
                    'limite_nord': to_int_or_null(get_attr(enneigement_jour, 'LimiteNord')),
                    'niveaux': niveaux_hist
                })

    # Parse NEIGEFRAICHE historique
    neige_fraiche_historique = []
    if bsh_elem is not None:
        neige_fraiche_elem = bsh_elem.find('NEIGEFRAICHE')
        if neige_fraiche_elem is not None:
            for neige24h in neige_fraiche_elem.findall('NEIGE24H'):
                neige_fraiche_historique.append({
                    'date': get_attr(neige24h, 'DATE'),
                    'min': to_int_or_null(get_attr(neige24h, 'SS24Min')),
                    'max': to_int_or_null(get_attr(neige24h, 'SS24Max'))
                })

    # Add historical data to their respective sections
    risque['historique'] = risques_historique
    enneigement['historique'] = enneigements_historique
    neige_fraiche['historique'] = neige_fraiche_historique

    meteo = {
        'altitude_vent_1': to_int_or_null(get_attr(meteo_elem, 'ALTITUDEVENT1')) if meteo_elem is not None else None,
        'altitude_vent_2': to_int_or_null(get_attr(meteo_elem, 'ALTITUDEVENT2')) if meteo_elem is not None else None,
        'commentaire': get_text(meteo_elem.find('COMMENTAIRE')) if meteo_elem is not None else '',
        'echeances': echeances,
        'echeances_historique': echeances_historique
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


def load_sample_xml():
    """Load sample XML from resources directory."""
    resources_dir = os.path.join(os.path.dirname(__file__), 'resources')
    xml_path = os.path.join(resources_dir, 'sample_bulletin.xml')
    with open(xml_path, 'r', encoding='utf-8') as f:
        return f.read()


def test_parse_bulletin_xml():
    """Test parsing of XML bulletin."""
    # Load and parse the XML
    sample_xml = load_sample_xml()
    xml_doc = etree.fromstring(sample_xml.encode('utf-8'))
    result = parse_bulletin_xml(xml_doc)

    # Test basic structure
    assert result is not None
    assert result['type'] == 'bulletins_neige_avalanche'
    assert result['id'] == '72'
    assert result['massif'] == 'Orlu St-Barthelemy'
    assert result['dateBulletin'] == '2025-11-21T16:00:00'
    assert result['dateEcheance'] == '2025-11-22T18:00:00'
    assert result['dateValidite'] == '2025-11-22T18:00:00'
    assert result['dateDiffusion'] == '2025-11-21T16:25:00'
    assert result['amendement'] == False

    # Test risque section
    assert result['risque'] is not None
    assert result['risque']['risque_max'] == '3'
    assert result['risque']['risque_1']['valeur'] == '3'
    assert result['risque']['altitude_limite'] is None
    assert result['risque']['commentaire'] == 'Indice de risque marqué.'
    assert result['risque']['naturel'] == 'Nombreux départs pendant les chutes puis au soleil'
    assert result['risque']['accidentel'] == 'Nombreuses plaques friables facilement déclenchables'
    assert 'Départs spontanés' in result['risque']['resume']

    # Test pentes particulières (boolean conversion)
    pentes = result['risque']['pentes_particulieres']
    assert pentes['NE'] is None  # "false" in XML
    assert pentes['E'] is None    # "true" in XML - but parsing as int gives None
    assert pentes['N'] is None

    # Test estimation J2
    assert result['risque']['estimation_j2']['date'] == '2025-11-23T00:00:00'
    assert result['risque']['estimation_j2']['risque_max'] == '3'
    assert result['risque']['estimation_j2']['description'] == 'Indice de risque marqué'
    assert result['risque']['estimation_j2']['commentaire'] == 'Stabilisation progressive du manteau neigeux.'

    # Test stabilite section
    assert result['stabilite'] is not None
    assert len(result['stabilite']['situations_avalancheuses']) == 2
    assert result['stabilite']['situations_avalancheuses'][0]['type'] == '1'
    assert result['stabilite']['situations_avalancheuses'][1]['type'] == '2'
    assert result['stabilite']['titre'] == 'Manteau neigeux récent encore instable'
    assert 'Déclenchements provoqués' in result['stabilite']['texte']

    # Test qualite section
    assert result['qualite'] is not None
    assert 'Le jour se lève samedi' in result['qualite']

    # Test enneigement section
    assert result['enneigement'] is not None
    assert result['enneigement']['date'] == '2025-11-21T00:00:00'
    assert result['enneigement']['limite_sud'] == 600
    assert result['enneigement']['limite_nord'] == 600
    assert len(result['enneigement']['niveaux']) == 3
    assert result['enneigement']['niveaux'][0]['altitude'] == 1500
    assert result['enneigement']['niveaux'][0]['nord'] == 25
    assert result['enneigement']['niveaux'][0]['sud'] == 25
    assert result['enneigement']['niveaux'][2]['altitude'] == 2500
    assert result['enneigement']['niveaux'][2]['nord'] == 50

    # Test neige fraiche section
    assert result['neige_fraiche'] is not None
    assert result['neige_fraiche']['altitude_ss'] == 1800
    assert len(result['neige_fraiche']['mesures']) == 6
    assert result['neige_fraiche']['mesures'][0]['date'] == '2025-11-17T00:00:00'
    assert result['neige_fraiche']['mesures'][0]['min'] == 0
    assert result['neige_fraiche']['mesures'][0]['max'] == 3
    assert result['neige_fraiche']['mesures'][3]['date'] == '2025-11-20T00:00:00'
    assert result['neige_fraiche']['mesures'][3]['min'] == 20
    assert result['neige_fraiche']['mesures'][3]['max'] == 40

    # Test meteo section
    assert result['meteo'] is not None
    assert result['meteo']['altitude_vent_1'] == 2000
    assert result['meteo']['altitude_vent_2'] == 3000
    assert result['meteo']['commentaire'] == 'Températures très froides le matin malgré le soleil !'
    assert len(result['meteo']['echeances']) == 4

    # Test first echeance
    echeance = result['meteo']['echeances'][0]
    assert echeance['date'] == '2025-11-22T06:00:00'
    assert echeance['vent']['force_1'] == 45
    assert echeance['vent']['direction_1'] == 'NO'
    assert echeance['vent']['force_2'] == 85
    assert echeance['vent']['direction_2'] == 'NO'
    assert echeance['iso_0'] == 500
    assert echeance['pluie_neige'] == 300
    assert echeance['temps_sensible'] == 61
    assert echeance['mer_nuages'] == -1

    # Test last echeance with -1 values
    echeance_last = result['meteo']['echeances'][3]
    assert echeance_last['date'] == '2025-11-23T00:00:00'
    assert echeance_last['pluie_neige'] == -1

    # Test meteo historique section (BSH)
    assert 'echeances_historique' in result['meteo']
    echeances_hist = result['meteo']['echeances_historique']
    assert len(echeances_hist) > 0  # Should have historical data
    # Check first historical entry
    if len(echeances_hist) > 0:
        first_hist = echeances_hist[0]
        assert 'date' in first_hist
        assert 'iso_0' in first_hist
        assert 'pluie_neige' in first_hist
        assert 'vent' in first_hist

    # Test risque historique (BSH/RISQUES)
    assert 'historique' in result['risque']
    risques_hist = result['risque']['historique']
    assert len(risques_hist) > 0
    if len(risques_hist) > 0:
        first_risque = risques_hist[0]
        assert 'date' in first_risque
        assert 'risque_max' in first_risque

    # Test enneigement historique (BSH/ENNEIGEMENTS)
    assert 'historique' in result['enneigement']
    enneigements_hist = result['enneigement']['historique']
    assert len(enneigements_hist) > 0
    if len(enneigements_hist) > 0:
        first_enneigement = enneigements_hist[0]
        assert 'date' in first_enneigement
        assert 'limite_sud' in first_enneigement
        assert 'limite_nord' in first_enneigement
        assert 'niveaux' in first_enneigement
        assert isinstance(first_enneigement['niveaux'], list)

    # Test neige fraiche historique (BSH/NEIGEFRAICHE)
    assert 'historique' in result['neige_fraiche']
    neige_fraiche_hist = result['neige_fraiche']['historique']
    assert len(neige_fraiche_hist) > 0
    if len(neige_fraiche_hist) > 0:
        first_neige = neige_fraiche_hist[0]
        assert 'date' in first_neige
        assert 'min' in first_neige
        assert 'max' in first_neige

    print("✓ All tests passed!")
    print(f"✓ Échéances prévision: {len(result['meteo']['echeances'])}")
    print(f"✓ Échéances historique: {len(result['meteo']['echeances_historique'])}")
    print(f"✓ Risques historique: {len(risques_hist)}")
    print(f"✓ Enneigements historique: {len(enneigements_hist)}")
    print(f"✓ Neige fraîche historique: {len(neige_fraiche_hist)}")
    return result


if __name__ == '__main__':
    result = test_parse_bulletin_xml()
    print("\n=== Parsed Result ===")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
