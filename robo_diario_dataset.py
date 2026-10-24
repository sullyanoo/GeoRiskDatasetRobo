import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from pathlib import Path
import os
import json
import random
import time
from datetime import datetime

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, box

from src.settings.settings import CRS_METRICO, CRS_GEOGRAFICO
from src.modules.utils.utils_mapbiomas import calcular_indicadores_mapbiomas
from src.modules.utils.utils_area_verde import calcular_percentual_verde_ndvi
from src.modules.utils.utils_alagamento import buscar_pontos_alagamento, calcular_densidade_alagamento_kde, chuva_ultimas_24h, normalizar_chuva
from src.modules.services.utils_services.utils_centralidade_grau import calcular_centralidade_grau_local


AMOSTRAS_TREINO_POR_DIA = 80
AMOSTRAS_TESTE_POR_DIA = 20
TOTAL_GERAL = AMOSTRAS_TREINO_POR_DIA + AMOSTRAS_TESTE_POR_DIA
RAIOS_BUFFER = [150, 300, 500]

CSV_TREINO = "dataset_treino_santo_amaro.csv"
CSV_TESTE = "dataset_teste_santo_amaro.csv"
ARQUIVO_GEOSAMPA = "shapefile geosampa.txt"

BBOX_MACRO_REGIAO = box(-46.7250, -23.6850, -46.6750, -23.6250)
_gdf_dominio = gpd.GeoDataFrame(geometry=[BBOX_MACRO_REGIAO], crs=CRS_GEOGRAFICO).to_crs(CRS_METRICO)
X_MIN, Y_MIN, X_MAX, Y_MAX = _gdf_dominio.total_bounds
Y_CENTRO = (Y_MIN + Y_MAX) / 2.0
MARGEM_GUARDA_METROS = 500.0

ZONA_TREINO_METRICA = box(X_MIN, Y_CENTRO + MARGEM_GUARDA_METROS, X_MAX, Y_MAX)
ZONA_TESTE_METRICA  = box(X_MIN, Y_MIN, X_MAX, Y_CENTRO - MARGEM_GUARDA_METROS)

print("=" * 65)
print("DOMÍNIO ESPACIAL CONFIGURADO (PARTICIONAMENTO EM BLOCO)")
print(f"Extensão Total da Área (km): X={(X_MAX - X_MIN)/1000:.2f}, Y={(Y_MAX - Y_MIN)/1000:.2f}")
print(f"Zona de Guarda (Dead Zone) Total: {MARGEM_GUARDA_METROS * 2:.0f} metros")
print("=" * 65)

def carregar_complemento_geosampa(filepath):
    if not os.path.isfile(filepath):
        return gpd.GeoDataFrame(geometry=[], crs=CRS_METRICO)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            conteudo = json.load(f)
        gdf = gpd.GeoDataFrame.from_features(conteudo["features"], crs=CRS_GEOGRAFICO)
        gdf["geometry"] = gdf["geometry"].centroid
        return gdf.to_crs(CRS_METRICO)
    except Exception as e:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_METRICO)

GDF_GEOSAMPA_COMPLEMENTAR = carregar_complemento_geosampa(ARQUIVO_GEOSAMPA)


def sortear_ponto_no_bloco(poligono_bloco):
    minx, miny, maxx, maxy = poligono_bloco.bounds
    ponto_candidato = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
    ponto_wgs = gpd.GeoSeries([ponto_candidato], crs=CRS_METRICO).to_crs(CRS_GEOGRAFICO)
    return ponto_wgs.geometry.iloc[0].x, ponto_wgs.geometry.iloc[0].y

def criar_buffers_multiescala(longitude, latitude):
    ponto = Point(longitude, latitude)
    gdf = gpd.GeoDataFrame(geometry=[ponto], crs=CRS_GEOGRAFICO).to_crs(CRS_METRICO)
    return {raio: gdf.geometry.iloc[0].buffer(raio) for raio in RAIOS_BUFFER}

def obter_pontos_alagamento_seguro(buffer_maximo):
    try:
        gdf_osm, _, pontos_osm = buscar_pontos_alagamento(buffer_maximo)
    except Exception:
        gdf_osm, pontos_osm = gpd.GeoDataFrame(geometry=[], crs=CRS_METRICO), []

    pontos_unificados = pontos_osm if isinstance(pontos_osm, list) else []
    gdf_unificado = gdf_osm if gdf_osm is not None and not gdf_osm.empty else gpd.GeoDataFrame(geometry=[], crs=CRS_METRICO)

    if not GDF_GEOSAMPA_COMPLEMENTAR.empty:
        geosampa_local = GDF_GEOSAMPA_COMPLEMENTAR[GDF_GEOSAMPA_COMPLEMENTAR.intersects(buffer_maximo)]
        if not geosampa_local.empty:
            for _, row in geosampa_local.iterrows():
                geom = row.geometry
                geom_wgs = gpd.GeoSeries([geom], crs=CRS_METRICO).to_crs(CRS_GEOGRAFICO).iloc[0]
                pontos_unificados.append({
                    "lat": geom_wgs.y,
                    "lng": geom_wgs.x,
                    "tipo": "Risco_GeoSampa",
                    "distancia_m": float(buffer_maximo.centroid.distance(geom)),
                    "peso_distancia": 1.0
                })
            gdf_unificado = pd.concat([gdf_unificado, geosampa_local], ignore_index=True)

    return gdf_unificado, pontos_unificados

def gerar_amostra(poligono_bloco, setor_label, chuva_norm):
    longitude, latitude = sortear_ponto_no_bloco(poligono_bloco)
    buffers = criar_buffers_multiescala(longitude, latitude)

    registro = {
        "data_coleta": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bloco_espacial": setor_label,
        "longitude": longitude,
        "latitude": latitude,
    }

    buffer_500m = buffers[500]
    gdf_eventos_500m, pontos_500m = obter_pontos_alagamento_seguro(buffer_500m)

    indicadores_finais = {}

    for raio, buffer in buffers.items():
        indicadores = calcular_indicadores_mapbiomas(buffer)
        percentual_verde_ndvi = calcular_percentual_verde_ndvi(buffer)

        if not gdf_eventos_500m.empty:
            gdf_raio = gdf_eventos_500m[gdf_eventos_500m.intersects(buffer)]
        else:
            gdf_raio = gpd.GeoDataFrame(geometry=[], crs=CRS_METRICO)

        pontos_raio = [p for p in pontos_500m if buffer.contains(Point(p["lng"], p["lat"]))] if pontos_500m else []

        pct_hidro = indicadores.get("percentual_hidrografia", 0.0)
        if len(pontos_raio) == 0 and pct_hidro > 0:
            centro = buffer.centroid
            geom_wgs = gpd.GeoSeries([centro], crs=CRS_METRICO).to_crs(CRS_GEOGRAFICO).iloc[0]
            pt_drenagem = {
                "lat": geom_wgs.y,
                "lng": geom_wgs.x,
                "tipo": "Corpo_Dagua_MapBiomas",
                "distancia_m": 0.0,
                "peso_distancia": min(1.0, pct_hidro * 10)
            }
            pontos_raio.append(pt_drenagem)
            gdf_raio = gpd.GeoDataFrame([{"geometry": centro}], crs=CRS_METRICO)

        if len(pontos_raio) > 0 and not gdf_raio.empty:
            densidade = calcular_densidade_alagamento_kde(buffer, gdf_raio)
        else:
            densidade = 0.0

        centralidade = calcular_centralidade_grau_local(pontos_raio, densidade)

        registro.update({
            f"area_total_m2_{raio}m": float(buffer.area),
            f"percentual_verde_ndvi_{raio}m": percentual_verde_ndvi,
            f"percentual_urbanizacao_{raio}m": indicadores.get("percentual_urbanizacao", 0.0),
            f"percentual_vegetacao_urbana_{raio}m": indicadores.get("percentual_vegetacao_urbana", 0.0),
            f"percentual_hidrografia_{raio}m": pct_hidro,
            f"densidade_alagamento_kde_{raio}m": densidade,
            f"centralidade_grau_local_{raio}m": centralidade
        })

        indicadores_finais = indicadores

    registro["chuva_24h_norm"] = chuva_norm
    registro["ano_mapbiomas"] = indicadores_finais.get("ano_mapbiomas", "N/A")
    return registro


def executar_coleta_lote(etapa_num, nome_csv, total_amostras, poligono_bloco, setor_label, chuva_norm):
    print(f"\n[{etapa_num}] Iniciando lote: {setor_label}")
    print(f"      Destino: {nome_csv} | Meta: {total_amostras} amostras")
    print("-" * 65)

    sucessos = 0
    tempo_inicio = time.time()

    for i in range(1, total_amostras + 1):
        tempo_item = time.time()
        try:
            registro = gerar_amostra(poligono_bloco, setor_label, chuva_norm)
            arquivo_existe = os.path.isfile(nome_csv)
            pd.DataFrame([registro]).to_csv(nome_csv, mode="a", header=not arquivo_existe, index=False)
            sucessos += 1
            duracao = time.time() - tempo_item
            pct = (i / total_amostras) * 100
            print(f"  -> [{setor_label}] Amostra {i:02d}/{total_amostras:02d} ({pct:5.1f}%) ok em {duracao:.2f}s | Coord: ({registro['longitude']:.4f}, {registro['latitude']:.4f})")
        except Exception as e:
            print(f"  ⚠️  [{setor_label}] Falha na amostra {i:02d}: {e}")

    tempo_total = time.time() - tempo_inicio
    print("-" * 65)
    print(f"[{etapa_num}] Lote {setor_label} finalizado: {sucessos}/{total_amostras} salvas em {tempo_total:.1f}s.")

def rodar_robo_diario():
    inicio_geral = time.time()
    print("=" * 65)
    print(f"ROBÔ DE COLETA DIÁRIA - AMOSTRAGEM ESPACIAL ESTRATIFICADA")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 65)

    print("\n[Etapa 1/3] Consultando condições meteorológicas...")
    try:
        chuva_valor = chuva_ultimas_24h()
        chuva_norm = normalizar_chuva(chuva_valor)
        print(f"  -> ✓ Sucesso! Chuva: {chuva_valor} mm | Normalizada: {chuva_norm:.4f}")
    except Exception as e:
        print(f"  -> ⚠️ Erro na API de chuva ({e}). Usando valor neutro 0.0.")
        chuva_norm = 0.0

    executar_coleta_lote(
        etapa_num="Etapa 2/3",
        nome_csv=CSV_TREINO,
        total_amostras=AMOSTRAS_TREINO_POR_DIA,
        poligono_bloco=ZONA_TREINO_METRICA,
        setor_label="SantoAmaro_Norte_Treino",
        chuva_norm=chuva_norm
    )

    executar_coleta_lote(
        etapa_num="Etapa 3/3",
        nome_csv=CSV_TESTE,
        total_amostras=AMOSTRAS_TESTE_POR_DIA,
        poligono_bloco=ZONA_TESTE_METRICA,
        setor_label="SantoAmaro_Sul_Teste",
        chuva_norm=chuva_norm
    )

    duracao_total = time.time() - inicio_geral
    print("\n" + "=" * 65)
    print(f"✓ ROTINA DIÁRIA CONCLUÍDA EM {duracao_total / 60:.1f} MINUTOS!")
    print(f"• Dataset Treino: '{CSV_TREINO}' atualizado com novos dados.")
    print(f"• Dataset Teste:  '{CSV_TESTE}' atualizado com novos dados.")
    print("=" * 65)

if __name__ == "__main__":
    rodar_robo_diario()
