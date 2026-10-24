from pathlib import Path
import geopandas as gpd

from shapely.validation import make_valid

from src.settings.settings import CRS_METRICO


BASE_DIR = Path(__file__).resolve().parents[3]

RISCO_HIDRO_PATH = (
    BASE_DIR
    / "datasets"
    / "geosampa"
    / "risco_hidrologico"
    / "SIRGAS_SHP_riscohidrologico_SANTOAMARO.shp"
)


_risco_hidrologico_gdf = None


def carregar_risco_hidrologico_geosampa():
    """
    Carrega a camada oficial de risco hidrológico do GeoSampa.

    Esta camada é usada como referência territorial externa,
    não como variável de treinamento do modelo.
    """

    global _risco_hidrologico_gdf

    if _risco_hidrologico_gdf is not None:
        return _risco_hidrologico_gdf

    print("Caminho esperado GeoSampa:", RISCO_HIDRO_PATH)

    if not RISCO_HIDRO_PATH.exists():
        print(f"Dataset GeoSampa não encontrado: {RISCO_HIDRO_PATH}")

        _risco_hidrologico_gdf = gpd.GeoDataFrame(
            geometry=[],
            crs=CRS_METRICO
        )

        return _risco_hidrologico_gdf

    gdf = gpd.read_file(RISCO_HIDRO_PATH)

    print("GeoSampa CRS original:", gdf.crs)
    print("GeoSampa colunas:", gdf.columns.tolist())
    print("GeoSampa quantidade original:", len(gdf))
    print("GeoSampa bounds original:", gdf.total_bounds)

    if gdf.crs is None:
        print(
            "GeoSampa sem CRS informado. "
            f"Aplicando CRS padrão do projeto: {CRS_METRICO}"
        )
        gdf = gdf.set_crs(CRS_METRICO, allow_override=True)

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[~gdf.geometry.is_empty]

    gdf["geometry"] = gdf["geometry"].apply(
        lambda geom: make_valid(geom) if not geom.is_valid else geom
    )

    gdf = gdf.to_crs(CRS_METRICO)

    print("GeoSampa CRS convertido:", gdf.crs)
    print("GeoSampa quantidade final:", len(gdf))
    print("GeoSampa bounds convertido:", gdf.total_bounds)

    _risco_hidrologico_gdf = gdf

    print(
        f"GeoSampa carregado: "
        f"{len(gdf)} feições de risco hidrológico"
    )

    return _risco_hidrologico_gdf


def verificar_risco_hidrologico_oficial(geom_metrico):
    """
    Verifica se a geometria analisada intersecta alguma área oficial
    de risco hidrológico do GeoSampa.
    """

    try:
        gdf = carregar_risco_hidrologico_geosampa()

        print("Geom análise área m²:", geom_metrico.area)
        print("Geom análise bounds:", geom_metrico.bounds)

        if gdf.empty:
            print("GeoSampa vazio. Nenhuma análise oficial aplicada.")

            return {
                "intersecta": False,
                "quantidade_areas": 0,
                "area_intersecao_m2": 0.0,
                "percentual_intersecao": 0.0
            }

        interseccoes = gdf[gdf.intersects(geom_metrico)]

        print("Interseções GeoSampa encontradas:", len(interseccoes))

        if interseccoes.empty:
            return {
                "intersecta": False,
                "quantidade_areas": 0,
                "area_intersecao_m2": 0.0,
                "percentual_intersecao": 0.0
            }

        area_intersecao = (
            interseccoes
            .geometry
            .intersection(geom_metrico)
            .area
            .sum()
        )

        percentual = (
            area_intersecao / geom_metrico.area
            if geom_metrico.area > 0
            else 0
        )

        return {
            "intersecta": True,
            "quantidade_areas": int(len(interseccoes)),
            "area_intersecao_m2": round(float(area_intersecao), 2),
            "percentual_intersecao": round(float(percentual), 4)
        }

    except Exception as e:
        print("Erro ao verificar risco hidrológico GeoSampa:", e)

        return {
            "intersecta": False,
            "quantidade_areas": 0,
            "area_intersecao_m2": 0.0,
            "percentual_intersecao": 0.0
        }