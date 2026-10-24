# geo/geo_utils.py

import numpy as np
import geopandas as gpd
import requests
from shapely.validation import make_valid
from shapely.geometry import Polygon, MultiPolygon

from src.settings.settings import GEOSAMPA_WFS, CRS_GEOGRAFICO


# REMOVER NAMESPACE XML (WFS)
def strip_namespace(obj):
    if isinstance(obj, dict):
        return {k.split(":")[-1]: strip_namespace(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_namespace(i) for i in obj]
    return obj


# CÁLCULO DE ÁREA (m²)
def calcular_area_m2(gdf):

    if gdf.empty:
        return 0

    # Remove geometrias nulas
    gdf = gdf[gdf.geometry.notnull()]

    # Corrige geometrias inválidas
    gdf["geometry"] = gdf["geometry"].apply(lambda geom: make_valid(geom) if not geom.is_valid else geom)

    # Remove geometrias vazias
    gdf = gdf[~gdf.geometry.is_empty]

    if gdf.empty:
        return 0

    return gdf.to_crs(epsg=31983).area.sum()


# CARREGAR LAYER DO GEOSAMPA (WFS)
def carregar_layer(layer_name):
    """
    Carrega camada WFS do GeoSampa em GeoDataFrame.
    Retorna no CRS geográfico original definido em settings.
    """

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer_name,
        "outputFormat": "application/json"
    }

    r = requests.get(GEOSAMPA_WFS, params=params, timeout=60)
    r.raise_for_status()

    gdf = gpd.read_file(r.content)

    # Garante CRS consistente
    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_GEOGRAFICO, allow_override=True)

    return gdf


# NORMALIZAÇÃO MIN-MAX 
def normalizar_minmax(serie):
    """
    Aplica normalização min-max a uma Series pandas.
    """
    min_val = serie.min()
    max_val = serie.max()

    if max_val - min_val == 0:
        return np.zeros(len(serie))

    return (serie - min_val) / (max_val - min_val)