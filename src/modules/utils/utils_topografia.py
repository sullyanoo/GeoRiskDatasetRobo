import numpy as np
import requests


def obter_altimetria_e_declividade(geom_metrico):
  """Calcula a cota média e estima a declividade aproximada do polígono.

  Utiliza a API aberta de elevação do Open-Meteo (base Copernicus DEM 30m)
  para o centroide e os 4 vértices cardeais do buffer.
  """
  try:
    # 1. Obter centroide e limites em WGS84
    centroide = geom_metrico.centroid
    bounds = geom_metrico.bounds  # (minx, miny, maxx, maxy)

    # Converter pontos estratégicos para Lat/Lng (WGS84)
    # Ponto Central, Norte, Sul, Leste, Oeste
    import geopandas as gpd

    pontos_gdf = gpd.GeoDataFrame(
        geometry=[
            centroide,
            geom_metrico.boundary.interpolate(0, normalized=True),
            geom_metrico.boundary.interpolate(0.25, normalized=True),
            geom_metrico.boundary.interpolate(0.50, normalized=True),
            geom_metrico.boundary.interpolate(0.75, normalized=True),
        ],
        crs="EPSG:31983",
    ).to_crs("EPSG:4326")

    lats = [p.y for p in pontos_gdf.geometry]
    lngs = [p.x for p in pontos_gdf.geometry]

    lats_str = ",".join(f"{lat:.6f}" for lat in lats)
    lngs_str = ",".join(f"{lng:.6f}" for lng in lngs)

    # 2. Consulta à API de Elevação (Open-Meteo / Copernicus 30m)
    url = f"https://api.open-meteo.com/v1/elevation?latitude={lats_str}&longitude={lngs_str}"
    r = requests.get(url, timeout=5)

    if r.status_code == 200:
      altitudes = r.json().get("elevation", [])
      if altitudes and len(altitudes) == 5:
        cota_central = float(altitudes[0])
        cotas_bordas = altitudes[1:]

        # Declividade média estimada: desnível máximo / raio (150m) * 100
        desnivel_max = max(cotas_bordas) - min(cotas_bordas)
        declividade_pct = min(100.0, (desnivel_max / 300.0) * 100.0)

        # Normalização da vulnerabilidade topográfica (0 a 1)
        # Terrenos planos (< 3%) têm maior risco de alagamento (1.0)
        # Terrenos íngremes (> 20%) têm menor risco de alagamento (0.0)
        vulnerabilidade_relevo = float(
            np.clip(1.0 - (declividade_pct / 20.0), 0.0, 1.0)
        )

        return {
            "cota_media_m": round(cota_central, 2),
            "desnivel_local_m": round(desnivel_max, 2),
            "declividade_pct": round(declividade_pct, 2),
            "vulnerabilidade_relevo_norm": round(vulnerabilidade_relevo, 4),
        }

  except Exception as e:
    print("Aviso: Falha ao obter altimetria externa, usando neutro:", e)

  # Fallback padrão (relevo médio típico de SP: 760m, plano)
  return {
    "cota_media_m": 760.0,
    "desnivel_local_m": 2.0,
    "declividade_pct": 1.5,
    "vulnerabilidade_relevo_norm": 0.5,
  }
