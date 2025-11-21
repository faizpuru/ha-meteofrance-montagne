# Météo France Montagne pour Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/faizpuru/ha-meteofrance-montagne.svg?style=for-the-badge)](https://github.com/faizpuru/ha-meteofrance-montagne/releases)
[![License](https://img.shields.io/github/license/faizpuru/ha-meteofrance-montagne.svg?style=for-the-badge)](LICENSE)

Intégration Home Assistant pour consulter les **Bulletins d'estimation du Risque d'Avalanche (BRA)** de Météo France. Surveillez les conditions de neige et le risque d'avalanche dans tous les massifs montagneux français (Alpes, Pyrénées, Corse).


## ✨ Fonctionnalités

- 🚨 **Risque d'avalanche actuel** : Échelle européenne 1-5 avec pictogrammes officiels
- 📅 **Prévision du risque** : Estimation pour le lendemain (J+1 ou J+2)
- ❄️ **Enneigement** : Limites d'enneigement nord et sud avec hauteurs de neige par altitude
- 🌨️ **Neige fraîche** : Mesures quotidiennes de cumuls de neige
- 🏔️ **Stabilité du manteau neigeux** : Situations avalancheuses typiques (SAT)
- 🌤️ **Météo montagne** : Prévisions avec températures, vent et temps sensible
- 🧊 **Qualité de la neige** : Description de l'état du manteau neigeux
- 🖼️ **6 images PNG** : Rose des pentes, risques, enneigement, graphiques, météo

## 📦 Installation

### Prérequis : Obtenir un token API Météo France (gratuit)

1. Créez un compte sur [https://portail-api.meteofrance.fr](https://portail-api.meteofrance.fr)
2. Souscrivez à l'API **"Données Publiques BRA"** (gratuite)
3. Copiez votre token API depuis votre espace personnel

### Via HACS (recommandé)

1. Ouvrez HACS dans Home Assistant
2. Allez dans **"Intégrations"**
3. Cliquez sur les **trois points** en haut à droite
4. Sélectionnez **"Dépôts personnalisés"**
5. Ajoutez l'URL : `https://github.com/faizpuru/ha-meteofrance-montagne`
6. Sélectionnez la catégorie **"Intégration"**
7. Cliquez sur **"Ajouter"**
8. Recherchez **"Météo France Montagne"** dans HACS
9. Cliquez sur **"Télécharger"**
10. **Redémarrez Home Assistant**

### Installation manuelle

1. Téléchargez la dernière release depuis [GitHub](https://github.com/faizpuru/ha-meteofrance-montagne/releases)
2. Copiez le dossier `custom_components/meteofrance-montagne` dans votre dossier `custom_components`
3. Redémarrez Home Assistant

## ⚙️ Configuration

### Première utilisation

1. Allez dans **Paramètres > Appareils et Services**
2. Cliquez sur **"Ajouter une intégration"**
3. Recherchez **"Météo France Montagne"**
4. Entrez votre **token API Météo France**
5. Sélectionnez le **département** puis le **massif** à surveiller

### Ajouter d'autres massifs

1. Réexécutez l'intégration (Ajouter une intégration > Météo France Montagne)
2. L'intégration utilisera automatiquement votre token API existant
3. Sélectionnez un nouveau département et massif

### Modifier le token API

1. Allez dans **Paramètres > Appareils et Services**
2. Trouvez l'entrée **"API Météo France Montagne"**
3. Cliquez sur **"Reconfigurer"**
4. Entrez le nouveau token

> ⚠️ **Note** : Le changement de token affectera tous vos massifs configurés.

## 🎯 Entités créées

Pour chaque massif configuré, l'intégration crée **8 sensors** et **6 images** :

### 📊 Sensors

#### 1. Risque Avalanche (`sensor.{massif}_risque_avalanche`)
- **État** : Niveau de risque en texte (Faible, Limité, Marqué, Fort, Très Fort)
- **Image** : Pictogramme officiel du niveau de risque
- **Attributs** :
  - `risque_max_valeur` : Niveau numérique (1-5)
  - `risque_max_texte` : Texte descriptif (Faible, Limité, Marqué, Fort, Très Fort)
  - `risque_max_couleur` : Couleur hexadécimale (#CCFF66, #FFFF00, #FF9900, #FF0000, #990000)
  - `resume` : Résumé de la situation
  - `commentaire` : Commentaire général
  - `departs_spontanes` : Risque de départs naturels
  - `declenchements_skieurs` : Risque de déclenchements accidentels
  - `altitude_limite_m` : Altitude de séparation des zones (si 2 zones)
  - `zones` : Liste des zones d'altitude
    ```json
    // Cas 1 : 2 zones distinctes
    [
      {
        "valeur": "3",
        "texte": "Marqué",
        "couleur": "#FF9900",
        "altitude": "<2500m",
        "evolution": "stable"
      },
      {
        "valeur": "4",
        "texte": "Fort",
        "couleur": "#FF0000",
        "altitude": ">2500m"
      }
    ]

    // Cas 2 : Risque uniforme (pas d'attribut altitude)
    [
      {
        "valeur": "3",
        "texte": "Marqué",
        "couleur": "#FF9900"
      }
    ]
    ```
  - `pentes_dangereuses_N`, `pentes_dangereuses_NE`, etc. : Orientations à risque (true/false)
  - `pentes_commentaire` : Commentaire sur les pentes
  - `last_update` : Date du bulletin

#### 2. Risque Avalanche Prévision (`sensor.{massif}_risque_avalanche_prevision`)
- **État** : Niveau de risque prévu en texte
- **Image** : Pictogramme du niveau prévu
- **Attributs** :
  - `risque_max_valeur` : Niveau numérique (1-5)
  - `risque_max_texte` : Texte descriptif
  - `risque_max_couleur` : Couleur hexadécimale
  - `commentaire` : Commentaire pour la prévision
  - `description` : Description détaillée
  - `date_prevision` : Date de validité de la prévision
  - `last_update`

#### 3. Limite Enneigement Nord (`sensor.{massif}_limite_enneigement_nord`)
- **État** : Altitude limite d'enneigement (en mètres)
- **Classe** : Distance (METERS)
- **Attributs** :
  - `date` : Date des observations
  - `limite_nord_m` : Limite nord en mètres
  - `niveaux` : Liste des hauteurs de neige par altitude
    ```json
    [
      {"altitude_m": 1000, "enneigement_cm": 0},
      {"altitude_m": 1500, "enneigement_cm": 25},
      {"altitude_m": 2000, "enneigement_cm": 120}
    ]
    ```
  - `last_update`

#### 4. Limite Enneigement Sud (`sensor.{massif}_limite_enneigement_sud`)
- Structure identique au sensor Nord, avec données spécifiques au versant sud

#### 5. Neige Fraîche (`sensor.{massif}_neige_fraiche`)
- **État** : Altitude de la station de mesure (en mètres)
- **Classe** : Distance (METERS)
- **Attributs** :
  - `altitude_mesure_m` : Altitude de mesure
  - `mesures` : Liste des cumuls de neige fraîche
    ```json
    [
      {"date": "2025-11-18", "min_cm": 5, "max_cm": 10},
      {"date": "2025-11-19", "min_cm": 2, "max_cm": 8}
    ]
    ```
  - `last_update`

#### 6. Météo (`sensor.{massif}_meteo`)
- **État** : Commentaire météo général
- **Attributs** :
  - `altitude_vent_1_m`, `altitude_vent_2_m` : Altitudes de référence pour le vent
  - `commentaire` : Commentaire météo
  - `echeances` : Liste des prévisions horaires avec températures, vent, isotherme 0°C, temps sensible
  - `last_update`

#### 7. Stabilité du Manteau Neigeux (`sensor.{massif}_stabilite_du_manteau_neigeux`)
- **État** : Situation avalancheuse typique principale (SAT)
- **Attributs** :
  - `titre` : Titre de la section stabilité
  - `texte` : Analyse de la stabilité
  - `situations` : Liste des situations avalancheuses typiques
    ```json
    [
      {"code": 1, "type": "Neige fraîche"},
      {"code": 4, "type": "Neige humide"}
    ]
    ```
  - `last_update`

#### 8. Qualité de la Neige (`sensor.{massif}_qualite_de_la_neige`)
- **État** : Extrait du texte (100 premiers caractères)
- **Attributs** :
  - `texte_complet` : Description complète de la qualité de la neige
  - `last_update`

### 🖼️ Images

Six images PNG actualisées quotidiennement :
- `image.{massif}_rose_pentes` : Rose des pentes dangereuses
- `image.{massif}_montagne_risques` : Cartographie des risques
- `image.{massif}_montagne_enneigement` : État de l'enneigement
- `image.{massif}_graphe_neige_fraiche` : Historique neige fraîche
- `image.{massif}_apercu_meteo` : Aperçu météo montagne
- `image.{massif}_sept_derniers_jours` : Synthèse 7 derniers jours

## 🤖 Exemples d'automatisations

### Alerte risque élevé

```yaml
    alias: "Alerte Risque Avalanche Élevé"
    triggers:
      - trigger: numeric_state
        entity_id:
          - sensor.aravis_risque_avalanche
        attribute: risque_max_valeur
        above: 1
    actions:
      - action: notify.persistent_notification
        data:
          message: >-
            Risque {{ states('sensor.aravis_risque_avalanche') }} dans les Aravis
            aujourd'hui  
```

### Notification neige fraîche

```yaml
    alias: "Neige Fraîche Détectée"
    trigger:
      - platform: state
        entity_id: sensor.aravis_neige_fraiche
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.aravis_neige_fraiche', 'mesures')[0].max_cm | int > 10 }}
    action:
      - service: notify.persistent_notification
        data:
          message: >
            🌨️ {{ state_attr('sensor.aravis_neige_fraiche', 'mesures')[0].max_cm }}cm
            de neige fraîche dans les Aravis !
```

### Dashboard Lovelace

```yaml
type: vertical-stack
cards:
  - type: entity
    entity: sensor.aravis_risque_avalanche
    name: Risque Avalanche Aravis

  - type: entity
    entity: sensor.aravis_limite_enneigement_nord
    name: Enneigement Versant Nord

  - type: picture-entity
    entity: image.aravis_montagne_risques
    show_state: false
    show_name: false

  - type: markdown
    content: >
      **Stabilité :** {{ states('sensor.aravis_stabilite_du_manteau_neigeux') }}

      **Qualité :** {{ state_attr('sensor.aravis_qualite_de_la_neige', 'texte_complet') }}
```

## 🔧 Dépannage

### Les données ne se mettent pas à jour

- Vérifiez votre connexion internet
- Les bulletins Météo France sont publiés quotidiennement vers **16h**
- L'intégration se met à jour automatiquement toutes les heures
- Rechargez l'intégration : Paramètres > Appareils et Services > Météo France Montagne > Recharger

### Erreur "cannot_connect"

- Vérifiez la validité de votre token API sur [portail-api.meteofrance.fr](https://portail-api.meteofrance.fr)
- Assurez-vous d'être bien inscrit à l'API "Données Publiques BRA"
- Vérifiez que le token n'a pas expiré

### Le sensor affiche "unavailable"

- Consultez les logs : Paramètres > Système > Logs
- Certains massifs peuvent ne pas publier de bulletin tous les jours
- Redémarrez Home Assistant

## 📚 Ressources

- [Documentation API Météo France](https://portail-api.meteofrance.fr/web/fr/api/DonneesPubliquesBRA)

## 🤝 Contribution

Les contributions sont les bienvenues !

- 🐛 Signalez des bugs via les [Issues](https://github.com/faizpuru/ha-meteofrance-montagne/issues)
- 💡 Proposez des améliorations
- 🔀 Soumettez des Pull Requests

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## 🙏 Crédits

- Données fournies par **[Météo France](https://meteofrance.com)**
- API publique : **Données Publiques BRA**
- Développé par **[@faizpuru](https://github.com/faizpuru)**

---

⭐ Si cette intégration vous est utile, n'hésitez pas à mettre une étoile sur GitHub !
