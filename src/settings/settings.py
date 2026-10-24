# config/settings.py

GEOSAMPA_WFS = "http://wms.geosampa.prefeitura.sp.gov.br/geoserver/wfs"

CRS_GEOGRAFICO = "EPSG:4326"
CRS_METRICO = "EPSG:31983"

LAYER_ALAGAMENTO = "geoportal:risco_ocorrencia_alagamento"

BUFFER_ALAGAMENTO_METROS = 100

GEOSAMPA_WMS = "http://wms.geosampa.prefeitura.sp.gov.br/geoserver/wms"
LAYER_IMAGEM_BASE = "geoportal:Articulacao_Orto_2020"
LAYER_AREA_VERDE = "geoportal:GEOSAMPA_zoneamento_geoambiental_apa_cm"


# ==========================================================
# INMET (chuva em tempo real para estimar risco de alagamento)
# ==========================================================

INMET_API_BASE = "https://apitempo.inmet.gov.br"

# estação meteorológica mais próxima de São Paulo
INMET_ESTACAO_SP = "A701"

# limite de chuva para risco de alagamento (mm em 24h)
LIMITE_CHUVA_ALAGAMENTO_MM = 50

NDVI = "https://planetarycomputer.microsoft.com/api/stac/v1"


