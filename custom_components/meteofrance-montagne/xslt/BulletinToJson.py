xslt = '''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="text" encoding="UTF-8"/>
  <xsl:strip-space elements="*"/>

  <!-- Template principal -->
  <xsl:template match="BULLETINS_NEIGE_AVALANCHE">
    {
      "type": "bulletins_neige_avalanche",
      "id": "<xsl:value-of select="@ID"/>",
      "massif": "<xsl:value-of select="@MASSIF"/>",
      "dateBulletin": "<xsl:value-of select="@DATEBULLETIN"/>",
      "dateEcheance": "<xsl:value-of select="@DATEECHEANCE"/>",
      "dateValidite": "<xsl:value-of select="@DATEVALIDITE"/>",
      "dateDiffusion": "<xsl:value-of select="@DATEDIFFUSION"/>",
      "amendement": <xsl:value-of select="@AMENDEMENT"/>,

      "risque": <xsl:apply-templates select="CARTOUCHERISQUE"/>,

      "stabilite": {
        "situations_avalancheuses": [
          <xsl:if test="STABILITE/SitAvalTyp/@SAT1 != ''">
          {
            "type": "<xsl:value-of select="STABILITE/SitAvalTyp/@SAT1"/>"
          }<xsl:if test="STABILITE/SitAvalTyp/@SAT2 != ''">,</xsl:if>
          </xsl:if>
          <xsl:if test="STABILITE/SitAvalTyp/@SAT2 != ''">
          {
            "type": "<xsl:value-of select="STABILITE/SitAvalTyp/@SAT2"/>"
          }
          </xsl:if>
        ],
        "titre": "<xsl:value-of select="normalize-space(STABILITE/TITRE)"/>",
        "texte": "<xsl:value-of select="normalize-space(STABILITE/TEXTE)"/>"
      },

      "qualite": "<xsl:value-of select="normalize-space(QUALITE/TEXTE)"/>",

      "enneigement": {
        "date": "<xsl:value-of select="ENNEIGEMENT/@DATE"/>",
        "limite_sud": <xsl:choose>
          <xsl:when test="ENNEIGEMENT/@LimiteSud != ''"><xsl:value-of select="ENNEIGEMENT/@LimiteSud"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "limite_nord": <xsl:choose>
          <xsl:when test="ENNEIGEMENT/@LimiteNord != ''"><xsl:value-of select="ENNEIGEMENT/@LimiteNord"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "niveaux": [
          <xsl:for-each select="ENNEIGEMENT/NIVEAU">
          {
            "altitude": <xsl:choose>
              <xsl:when test="@ALTI != ''"><xsl:value-of select="@ALTI"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "nord": <xsl:choose>
              <xsl:when test="@N != ''"><xsl:value-of select="@N"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "sud": <xsl:choose>
              <xsl:when test="@S != ''"><xsl:value-of select="@S"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>
          }<xsl:if test="position() != last()">,</xsl:if>
          </xsl:for-each>
        ]
      },

      "neige_fraiche": {
        "altitude_ss": <xsl:choose>
          <xsl:when test="NEIGEFRAICHE/@ALTITUDESS != ''"><xsl:value-of select="NEIGEFRAICHE/@ALTITUDESS"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "mesures": [
          <xsl:for-each select="NEIGEFRAICHE/NEIGE24H">
          {
            "date": "<xsl:value-of select="@DATE"/>",
            "min": <xsl:choose>
              <xsl:when test="@SS24Min != ''"><xsl:value-of select="@SS24Min"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "max": <xsl:choose>
              <xsl:when test="@SS24Max != ''"><xsl:value-of select="@SS24Max"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>
          }<xsl:if test="position() != last()">,</xsl:if>
          </xsl:for-each>
        ]
      },

      "meteo": {
        "altitude_vent_1": <xsl:choose>
          <xsl:when test="METEO/@ALTITUDEVENT1 != ''"><xsl:value-of select="METEO/@ALTITUDEVENT1"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "altitude_vent_2": <xsl:choose>
          <xsl:when test="METEO/@ALTITUDEVENT2 != ''"><xsl:value-of select="METEO/@ALTITUDEVENT2"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "commentaire": "<xsl:value-of select="normalize-space(METEO/COMMENTAIRE)"/>",
        "echeances": [
          <xsl:for-each select="METEO/ECHEANCE">
          {
            "date": "<xsl:value-of select="@DATE"/>",
            "vent": {
              "force_1": <xsl:choose>
                <xsl:when test="@FF1 != ''"><xsl:value-of select="@FF1"/></xsl:when>
                <xsl:otherwise>null</xsl:otherwise>
              </xsl:choose>,
              "direction_1": "<xsl:value-of select="@DD1"/>",
              "force_2": <xsl:choose>
                <xsl:when test="@FF2 != ''"><xsl:value-of select="@FF2"/></xsl:when>
                <xsl:otherwise>null</xsl:otherwise>
              </xsl:choose>,
              "direction_2": "<xsl:value-of select="@DD2"/>"
            },
            "iso_0": <xsl:choose>
              <xsl:when test="@ISO0 != ''"><xsl:value-of select="@ISO0"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "pluie_neige": <xsl:choose>
              <xsl:when test="@PLUIENEIGE != ''"><xsl:value-of select="@PLUIENEIGE"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "temps_sensible": <xsl:choose>
              <xsl:when test="@TEMPSSENSIBLE != ''"><xsl:value-of select="@TEMPSSENSIBLE"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>,
            "mer_nuages": <xsl:choose>
              <xsl:when test="@MERNUAGES != ''"><xsl:value-of select="@MERNUAGES"/></xsl:when>
              <xsl:otherwise>null</xsl:otherwise>
            </xsl:choose>
          }<xsl:if test="position() != last()">,</xsl:if>
          </xsl:for-each>
        ]
      }
    }
  </xsl:template>

  <!-- Template pour le risque -->
  <xsl:template match="CARTOUCHERISQUE">
    {
      "risque_max": "<xsl:value-of select="RISQUE/@RISQUEMAXI"/>",
      "risque_1": {
        "valeur": "<xsl:value-of select="RISQUE/@RISQUE1"/>",
        "evolution": "<xsl:value-of select="RISQUE/@EVOLURISQUE1"/>",
        "localisation": "<xsl:value-of select="RISQUE/@LOC1"/>"
      },
      "risque_2": {
        "valeur": "<xsl:value-of select="RISQUE/@RISQUE2"/>",
        "evolution": "<xsl:value-of select="RISQUE/@EVOLURISQUE2"/>",
        "localisation": "<xsl:value-of select="RISQUE/@LOC2"/>"
      },
      "altitude_limite": <xsl:choose>
        <xsl:when test="RISQUE/@ALTITUDE != ''"><xsl:value-of select="RISQUE/@ALTITUDE"/></xsl:when>
        <xsl:otherwise>null</xsl:otherwise>
      </xsl:choose>,
      "commentaire": "<xsl:value-of select="normalize-space(RISQUE/@COMMENTAIRE)"/>",
      "naturel": "<xsl:value-of select="normalize-space(NATUREL)"/>",
      "accidentel": "<xsl:value-of select="normalize-space(ACCIDENTEL)"/>",
      "resume": "<xsl:value-of select="normalize-space(RESUME)"/>",
      "estimation_j2": {
        "date": "<xsl:value-of select="RISQUE/@DATE_RISQUE_J2"/>",
        "risque_max": "<xsl:value-of select="RISQUE/@RISQUEMAXIJ2"/>",
        "description": "<xsl:value-of select="normalize-space(RisqueJ2)"/>",
        "commentaire": "<xsl:value-of select="normalize-space(CommentaireRisqueJ2)"/>"
      },
      "pentes_particulieres": {
        "NE": <xsl:choose>
          <xsl:when test="PENTE/@NE != ''"><xsl:value-of select="PENTE/@NE"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "E": <xsl:choose>
          <xsl:when test="PENTE/@E != ''"><xsl:value-of select="PENTE/@E"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "SE": <xsl:choose>
          <xsl:when test="PENTE/@SE != ''"><xsl:value-of select="PENTE/@SE"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "S": <xsl:choose>
          <xsl:when test="PENTE/@S != ''"><xsl:value-of select="PENTE/@S"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "SW": <xsl:choose>
          <xsl:when test="PENTE/@SW != ''"><xsl:value-of select="PENTE/@SW"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "W": <xsl:choose>
          <xsl:when test="PENTE/@W != ''"><xsl:value-of select="PENTE/@W"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "NW": <xsl:choose>
          <xsl:when test="PENTE/@NW != ''"><xsl:value-of select="PENTE/@NW"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "N": <xsl:choose>
          <xsl:when test="PENTE/@N != ''"><xsl:value-of select="PENTE/@N"/></xsl:when>
          <xsl:otherwise>null</xsl:otherwise>
        </xsl:choose>,
        "commentaire": "<xsl:value-of select="normalize-space(PENTE/@COMMENTAIRE)"/>"
      }
    }
  </xsl:template>

</xsl:stylesheet>
'''
