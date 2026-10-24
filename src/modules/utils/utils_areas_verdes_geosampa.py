# src/modules/utils/utils_areas_verdes_geosampa.py

from pathlib import Path
import geopandas as gpd

from shapely.validation import make_valid

from src.settings.settings import CRS_METRICO


BASE_DIR = Path(__file__).resolve().parents[3]

AREAS_VERDES_PATH = (
    BASE_DIR
    / "datasets"
    / "geosampa"
    / "verde_recursos_naturais"
    / "v_praca_largo.shp"
)


_areas_verdes_gdf = None


def carregar_areas_verdes_geosampa():
    global _areas_verdes_gdf

    if _areas_verdes_gdf is not None:
        return _areas_verdes_gdf

    print("Caminho esperado áreas verdes:", AREAS_VERDES_PATH)

    if not AREAS_VERDES_PATH.exists():
        print(f"Dataset de áreas verdes não encontrado: {AREAS_VERDES_PATH}")

        _areas_verdes_gdf = gpd.GeoDataFrame(
            geometry=[],
            crs=CRS_METRICO
        )

        return _areas_verdes_gdf

    gdf = gpd.read_file(AREAS_VERDES_PATH)

    print("Áreas verdes CRS original:", gdf.crs)
    print("Áreas verdes colunas:", gdf.columns.tolist())
    print("Áreas verdes quantidade original:", len(gdf))
    print("Áreas verdes bounds original:", gdf.total_bounds)

    if gdf.crs is None:
        gdf = gdf.set_crs(CRS_METRICO, allow_override=True)

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    gdf["geometry"] = gdf["geometry"].apply(
        lambda geom: make_valid(geom) if not geom.is_valid else geom
    )

    gdf = gdf.to_crs(CRS_METRICO)

    _areas_verdes_gdf = gdf

    print(f"Áreas verdes carregadas: {len(gdf)} feições")

    return _areas_verdes_gdf


def verificar_areas_verdes_oficiais(geom_metrico):
    try:
        gdf = carregar_areas_verdes_geosampa()

        retorno_vazio = {
            "intersecta": False,
            "quantidade_areas": 0,
            "area_intersecao_m2": 0.0,
            "percentual_intersecao": 0.0,
            "areas": [],
            "geojson": None
        }

        if gdf.empty:
            return retorno_vazio

        interseccoes = gdf[gdf.intersects(geom_metrico)].copy()

        if interseccoes.empty:
            return retorno_vazio

        interseccoes["geometry"] = interseccoes.geometry.intersection(geom_metrico)
        interseccoes = interseccoes[
            interseccoes.geometry.notnull() & ~interseccoes.geometry.is_empty
        ]

        area_intersecao = interseccoes.geometry.area.sum()

        percentual = (
            area_intersecao / geom_metrico.area
            if geom_metrico.area > 0
            else 0
        )

        areas = []

        for _, row in interseccoes.iterrows():
            areas.append({
                "nome": row.get("nome"),
                "categoria": row.get("categoria"),
                "distrito": row.get("distrito"),
                "subprefeitura": row.get("subprefeit"),
                "area_metro": float(row.get("area_metro") or 0)
            })

        interseccoes_wgs84 = interseccoes.to_crs("EPSG:4326")

        return {
            "intersecta": True,
            "quantidade_areas": int(len(interseccoes)),
            "area_intersecao_m2": round(float(area_intersecao), 2),
            "percentual_intersecao": round(float(percentual), 4),
            "areas": areas,
            "geojson": interseccoes_wgs84.__geo_interface__
        }

    except Exception as e:
        print("Erro ao verificar áreas verdes oficiais:", e)

        return {
            "intersecta": False,
            "quantidade_areas": 0,
            "area_intersecao_m2": 0.0,
            "percentual_intersecao": 0.0,
            "areas": [],
            "geojson": None
        }