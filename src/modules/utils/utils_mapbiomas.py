from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask

from src.settings.settings import CRS_METRICO


BASE_DIR = Path(__file__).resolve().parents[3]

MAPBIOMAS_PATHS = {
    2022: {
        "cobertura": BASE_DIR / "datasets/mapbiomas/vegetacao/2022_coverage_lclu_1-1-1_2361a4a7-8905-4672-b3b9-498a52407de7.tif",
        "vegetacao_urbana": BASE_DIR / "datasets/mapbiomas/vegetacao_urbana/2022_urban_urban_vegetation_1-1-1_ce6e3dc8-a16f-4c40-8bb6-9a7c6c30ba6a.tif",
        "hidrografia": BASE_DIR / "datasets/mapbiomas/hidrografia/2022_water_water_surface_1-1-1_fde133b4-d5ec-45ac-a7f3-02051eee00c0.tif",
    },

    2023: {
        "cobertura": BASE_DIR / "datasets/mapbiomas/vegetacao/2023_coverage_lclu_1-1-1_2242342e-4c61-44e4-83ac-2a2e7e23b148.tif",
        "vegetacao_urbana": BASE_DIR / "datasets/mapbiomas/vegetacao_urbana/2023_urban_urban_vegetation_1-1-1_870138f4-a089-48b6-9af8-77abfccb2f61.tif",
        "hidrografia": BASE_DIR / "datasets/mapbiomas/hidrografia/2023_water_water_surface_1-1-1_5a1f70c7-7946-4bf9-ad75-95e85c65e7fa.tif",
    },

    2024: {
        "cobertura": BASE_DIR / "datasets/mapbiomas/vegetacao/2024_coverage_lclu_1-1-1_e04830ad-d1b1-4739-b27b-ffea882f0d77.tif",
        "vegetacao_urbana": BASE_DIR / "datasets/mapbiomas/vegetacao_urbana/2024_urban_urban_vegetation_1-1-1_0437ed04-f7d2-452f-a4b7-ece04442b48b.tif",
        "hidrografia": BASE_DIR / "datasets/mapbiomas/hidrografia/2024_water_water_surface_1-1-1_fa93a8d9-2237-4e26-95bc-a4c0800efd7d.tif",
    }
}

CLASSES_VEGETACAO = [3, 4, 5, 6, 9, 11, 12, 15, 49, 50]
CLASSE_URBANA = 24
CLASSE_AGUA_COBERTURA = 33

CODIGO_URBANO_SEM_VEGETACAO = 240
CODIGO_URBANO_COM_VEGETACAO = 241
CODIGO_HIDROGRAFIA_AGUA = 1


def recortar_raster_por_geometria(caminho_tif, geom_metrico):
    if not caminho_tif.exists():
        print(f"Raster MapBiomas não encontrado: {caminho_tif}")
        return None

    try:
        gdf = gpd.GeoDataFrame(
            geometry=[geom_metrico],
            crs=CRS_METRICO
        )

        with rasterio.open(caminho_tif) as src:
            gdf_raster = gdf.to_crs(src.crs)
            geometria = [gdf_raster.geometry.iloc[0].__geo_interface__]

            dados, _ = mask(
                src,
                geometria,
                crop=True,
                nodata=src.nodata or 0
            )

            banda = dados[0]

            return banda

    except Exception as e:
        print(f"Erro ao recortar raster MapBiomas {caminho_tif}: {e}")
        return None


def calcular_percentual_por_classes(array, classes):
    if array is None:
        return 0.0

    pixels_validos = array[array >= 0]

    if pixels_validos.size == 0:
        return 0.0

    mascara = np.isin(pixels_validos, classes)
    return float(np.sum(mascara) / pixels_validos.size)


def calcular_indicadores_mapbiomas(geom_metrico, ano=None):
    """
    Calcula indicadores do MapBiomas.

    Se ano=None:
        utiliza todos os anos disponíveis e retorna também a média.

    Se ano=2024:
        mantém comportamento antigo.
    """

    anos = [ano] if ano else sorted(MAPBIOMAS_PATHS.keys())

    resultados = []

    for ano_atual in anos:

        paths = MAPBIOMAS_PATHS.get(ano_atual)

        if paths is None:
            continue

        cobertura = recortar_raster_por_geometria(
            paths["cobertura"],
            geom_metrico
        )

        vegetacao_urbana = recortar_raster_por_geometria(
            paths["vegetacao_urbana"],
            geom_metrico
        )

        hidrografia = recortar_raster_por_geometria(
            paths["hidrografia"],
            geom_metrico
        )

        percentual_urbanizacao = calcular_percentual_por_classes(
            cobertura,
            [CLASSE_URBANA]
        )

        percentual_cobertura_vegetal = calcular_percentual_por_classes(
            cobertura,
            CLASSES_VEGETACAO
        )

        percentual_hidrografia_cobertura = calcular_percentual_por_classes(
            cobertura,
            [CLASSE_AGUA_COBERTURA]
        )

        percentual_hidrografia_raster = calcular_percentual_por_classes(
            hidrografia,
            [CODIGO_HIDROGRAFIA_AGUA]
        )

        percentual_hidrografia = max(
            percentual_hidrografia_cobertura,
            percentual_hidrografia_raster
        )

        if vegetacao_urbana is not None:

            pixels_validos = vegetacao_urbana[
                vegetacao_urbana >= 0
            ]

            if pixels_validos.size > 0:

                urbano_sem = np.sum(
                    pixels_validos ==
                    CODIGO_URBANO_SEM_VEGETACAO
                )

                urbano_com = np.sum(
                    pixels_validos ==
                    CODIGO_URBANO_COM_VEGETACAO
                )

                urbano_total = urbano_sem + urbano_com

                percentual_vegetacao_urbana_total = (
                    urbano_com /
                    pixels_validos.size
                )

                if urbano_total > 0:

                    percentual_vegetacao_urbana = (
                        urbano_com /
                        urbano_total
                    )

                else:

                    percentual_vegetacao_urbana = 0.0

            else:

                percentual_vegetacao_urbana_total = 0.0
                percentual_vegetacao_urbana = 0.0

        else:

            percentual_vegetacao_urbana_total = 0.0
            percentual_vegetacao_urbana = 0.0

        resultados.append({

            "ano": ano_atual,

            "percentual_urbanizacao":
                percentual_urbanizacao,

            "percentual_cobertura_vegetal_mapbiomas":
                percentual_cobertura_vegetal,

            "percentual_hidrografia":
                percentual_hidrografia,

            "percentual_vegetacao_urbana":
                percentual_vegetacao_urbana,

            "percentual_vegetacao_urbana_total":
                percentual_vegetacao_urbana_total
        })

    if len(resultados) == 0:

        return {

            "percentual_urbanizacao": 0,

            "percentual_cobertura_vegetal_mapbiomas": 0,

            "percentual_hidrografia": 0,

            "percentual_vegetacao_urbana": 0,

            "percentual_vegetacao_urbana_total": 0,

            "anos": [],

            "serie_temporal": []
        }

    media = {}

    for chave in [

        "percentual_urbanizacao",

        "percentual_cobertura_vegetal_mapbiomas",

        "percentual_hidrografia",

        "percentual_vegetacao_urbana",

        "percentual_vegetacao_urbana_total"

    ]:

        media[chave] = round(

            float(

                np.mean(
                    [r[chave] for r in resultados]
                )

            ),

            6

        )

    media["anos"] = [

    r["ano"]

    for r in resultados

    ]

    media["ano_mapbiomas"] = "2022-2024"

    # Desvio padrão da série temporal
    media["desvio_padrao"] = {

        chave: round(

            float(

                np.std(

                    [r[chave] for r in resultados]

                )

            ),

            6

        )

        for chave in [

            "percentual_urbanizacao",

            "percentual_cobertura_vegetal_mapbiomas",

            "percentual_hidrografia",

            "percentual_vegetacao_urbana",

            "percentual_vegetacao_urbana_total"

        ]

    }

    # Tendência entre 2022 e 2024
    media["variacao"] = {

        chave: round(

            resultados[-1][chave] -

            resultados[0][chave],

            6

        )

        for chave in [

            "percentual_urbanizacao",

            "percentual_cobertura_vegetal_mapbiomas",

            "percentual_hidrografia",

            "percentual_vegetacao_urbana",

            "percentual_vegetacao_urbana_total"

        ]

    }

    media["serie_temporal"] = resultados

    return media