from datetime import datetime, timedelta
import agrobr
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import shape
from sklearn.neighbors import KernelDensity
from src.settings.settings import *

# CONFIGURAÇÕES OSM / HIDROLOGIA

RAIO_BUSCA_OSM_METROS = 300
# CHUVA - INMET (AGROBR + FALLBACK RESILIENTE)

def chuva_ultimas_24h(codigo_estacao="A701"):
  """Obtém o volume de chuva acumulada nas últimas 24h via biblioteca agrobr (INMET).

  Parâmetros corrigidos: 'inicio' e 'fim'. Inclui fallback de contingência caso
  a API do INMET esteja offline.
  """
  try:
    hoje = datetime.utcnow().date()
    ontem = hoje - timedelta(days=1)

    print(f"Consultando agrobr/INMET para a estação {codigo_estacao}...")

    # Chamada corrigida com parâmetros posicionais/nomeados aceitos pelo agrobr
    df = agrobr.inmet.estacao(codigo=codigo_estacao, inicio=ontem, fim=hoje)

    if df is not None and not df.empty:
      col_chuva = None
      for col in [
          "chuva",
          "precipitacao",
          "CHUVA",
          "precipitacao_total",
          "PRE_TOT",
          "pr",
      ]:
        if col in df.columns:
          col_chuva = col
          break

      if col_chuva is not None:
        valores = df[col_chuva].replace([-9999, "-9999", -9999.0], 0).fillna(0)
        valores_numericos = pd.to_numeric(
            valores.astype(str).str.replace(",", "."), errors="coerce"
        ).fillna(0)
        chuva_total = float(valores_numericos.sum())

        print(
            f"Chuva acumulada (24h) via agrobr ({codigo_estacao}):"
            f" {chuva_total:.2f} mm"
        )
        return round(chuva_total, 2)

  except Exception as e:
    print(f"Tentativa agrobr/INMET ({codigo_estacao}) falhou:", e)

  # Fallback de contingência: Open-Meteo para a cidade de São Paulo (-23.55, -46.63)
  try:
    url_fallback = (
        "https://api.open-meteo.com/v1/forecast?latitude=-23.55&longitude=-46.63&hourly=precipitation&past_days=1&forecast_days=1"
    )
    r = requests.get(url_fallback, timeout=5)
    if r.status_code == 200:
      dados = r.json()
      chuvas = dados.get("hourly", {}).get("precipitation", [])
      if chuvas:
        chuva_24h = sum(
            float(x) for x in chuvas[-24:] if x not in [None, "", "null"]
        )
        print(f"Chuva (24h) obtida via fallback Open-Meteo: {chuva_24h:.2f} mm")
        return round(chuva_24h, 2)
  except Exception as e:
    print("Fallback meteorológico falhou:", e)

  return 0.0


def normalizar_chuva(valor):
  """Aplica a função linear por partes com saturação em 80 mm (Eq. 3.2)."""
  if valor <= 10:
    return 0.0

  if valor >= 80:
    return 1.0

  return float(valor / 80)


# PESO POR DISTÂNCIA
def calcular_peso_distancia(distancia_m, raio_max=RAIO_BUSCA_OSM_METROS):
    """
    Calcula o peso espacial do elemento hidrológico conforme a distância
    até o centroide da unidade analisada.

    0 m      => peso 1.0
    raio_max => peso 0.0
    """

    try:
        distancia_m = float(distancia_m)

        if distancia_m >= raio_max:
            return 0.0

        if distancia_m <= 0:
            return 1.0

        return float(1 - (distancia_m / raio_max))

    except Exception:
        return 0.0


def buscar_pontos_alagamento(geom_metrico):
    """
    Busca indicadores hidrológicos no OpenStreetMap via Overpass.

    Observação metodológica:
    Estes pontos não representam necessariamente ocorrências oficiais
    de alagamento. Eles representam elementos hidrológicos, drenagem,
    corpos d'água e possíveis marcações de suscetibilidade a inundação
    disponíveis no OSM.

    Ajuste metodológico:
    A influência dos pontos é ponderada pela distância até o centroide
    da geometria analisada, evitando que elementos distantes tenham o
    mesmo peso que elementos próximos.
    """

    try:
        centroide = geom_metrico.centroid

        geom_busca = geom_metrico.buffer(RAIO_BUSCA_OSM_METROS)

        gdf = gpd.GeoDataFrame(
            geometry=[geom_busca],
            crs=CRS_METRICO
        ).to_crs("EPSG:4326")

        minx, miny, maxx, maxy = gdf.total_bounds

        overpass_url = "https://overpass-api.de/api/interpreter"

        query = f"""
        [out:json][timeout:15];
        (
        node["waterway"]({miny},{minx},{maxy},{maxx});
        way["waterway"]({miny},{minx},{maxy},{maxx});

        node["natural"="water"]({miny},{minx},{maxy},{maxx});
        way["natural"="water"]({miny},{minx},{maxy},{maxx});

        node["flood_prone"="yes"]({miny},{minx},{maxy},{maxx});
        way["flood_prone"="yes"]({miny},{minx},{maxy},{maxx});

        node["hazard"="flood"]({miny},{minx},{maxy},{maxx});
        way["hazard"="flood"]({miny},{minx},{maxy},{maxx});
        );
        out center tags;
        """

        print("BBOX Overpass:", miny, minx, maxy, maxx)

        response = requests.post(
            overpass_url,
            data={"data": query},
            headers={
                "User-Agent": "CityGraph-LIME/1.0",
                "Accept": "application/json"
            },
            timeout=30
        )

        print("Status Overpass:", response.status_code)

        if response.status_code != 200:
            print("Resposta Overpass:", response.text[:500])
            return gpd.GeoDataFrame(), 0.0, []

        data = response.json()
        elementos = data.get("elements", [])

        print("Elementos encontrados:", len(elementos))

        if not elementos:
            return gpd.GeoDataFrame(), 0.0, []

        pontos_temp = []
        vistos = set()

        for el in elementos:
            tags = el.get("tags", {})

            lat = None
            lng = None

            if el.get("type") == "node":
                lat = el.get("lat")
                lng = el.get("lon")

            elif el.get("type") == "way" and "center" in el:
                lat = el["center"].get("lat")
                lng = el["center"].get("lon")

            if lat is None or lng is None:
                continue

            chave = (round(float(lat), 6), round(float(lng), 6))

            if chave in vistos:
                continue

            vistos.add(chave)

            pontos_temp.append({
                "lat": float(lat),
                "lng": float(lng),
                "tipo": inferir_tipo_hidrologico(tags)
            })

        if not pontos_temp:
            return gpd.GeoDataFrame(), 0.0, []

        geoms_wgs84 = [
            shape({
                "type": "Point",
                "coordinates": (p["lng"], p["lat"])
            })
            for p in pontos_temp
        ]

        gdf_eventos = gpd.GeoDataFrame(
            pontos_temp,
            geometry=geoms_wgs84,
            crs="EPSG:4326"
        ).to_crs(CRS_METRICO)

        pontos_filtrados = []

        for idx, row in gdf_eventos.iterrows():
            distancia_m = float(row.geometry.distance(centroide))
            peso_distancia = calcular_peso_distancia(
                distancia_m,
                RAIO_BUSCA_OSM_METROS
            )

            if peso_distancia <= 0:
                continue

            pontos_filtrados.append({
                "lat": float(pontos_temp[idx]["lat"]),
                "lng": float(pontos_temp[idx]["lng"]),
                "tipo": pontos_temp[idx]["tipo"],
                "distancia_m": round(distancia_m, 2),
                "peso_distancia": round(float(peso_distancia), 4)
            })

        if not pontos_filtrados:
            return gpd.GeoDataFrame(), 0.0, []

        gdf_eventos_filtrado = gdf_eventos.iloc[
            [i for i, row in gdf_eventos.iterrows()
             if calcular_peso_distancia(
                 float(row.geometry.distance(centroide)),
                 RAIO_BUSCA_OSM_METROS
             ) > 0]
        ].copy()

        soma_pesos = sum(p["peso_distancia"] for p in pontos_filtrados)

        densidade_ponderada = soma_pesos / geom_metrico.area * 100000
        densidade_ponderada = min(float(densidade_ponderada), 1.0)

        print("Pontos OSM filtrados:", len(pontos_filtrados))
        print("Soma pesos OSM:", round(float(soma_pesos), 4))
        print("Densidade ponderada OSM:", round(float(densidade_ponderada), 6))

        return gdf_eventos_filtrado, densidade_ponderada, pontos_filtrados

    except Exception as e:
        print("Erro Overpass:", e)
        return gpd.GeoDataFrame(), 0.0, []


def inferir_tipo_hidrologico(tags):
    if not tags:
        return "indicador hidrológico"

    if tags.get("flood_prone") == "yes":
        return "área suscetível a alagamento"

    if tags.get("hazard") == "flood":
        return "risco de inundação"

    if "waterway" in tags:
        return f"curso d'água: {tags.get('waterway')}"

    if tags.get("natural") == "water":
        return "corpo d'água"

    if "water" in tags:
        return f"água: {tags.get('water')}"

    return "indicador hidrológico"


# KDE

def calcular_densidade_alagamento_kde(geom_metrico, gdf_eventos=None):
    """
    Calcula a densidade KDE dos indicadores hidrológicos.

    Se gdf_eventos for informado, evita nova chamada ao Overpass.

    Ajuste metodológico:
    O retorno é conservador para evitar que elementos hidrológicos
    distantes dominem a classificação.
    """

    try:
        if gdf_eventos is None:
            gdf_eventos, _, _ = buscar_pontos_alagamento(geom_metrico)

        if gdf_eventos.empty:
            return 0.0

        coords = np.vstack([
            gdf_eventos.geometry.x,
            gdf_eventos.geometry.y
        ]).T

        if len(coords) < 3:
            densidade_simples = len(coords) / geom_metrico.area * 100000
            return float(min(densidade_simples, 0.30))

        kde = KernelDensity(
            bandwidth=180,
            kernel="gaussian"
        )

        kde.fit(coords)

        centroide = geom_metrico.centroid
        ponto = np.array([[centroide.x, centroide.y]])

        log_densidade = kde.score_samples(ponto)[0]
        densidade = np.exp(log_densidade)

        densidade_norm = densidade * 100000
        densidade_norm = min(float(densidade_norm), 0.50)

        return densidade_norm

    except Exception as e:
        print("Erro KDE:", e)
        return 0.0