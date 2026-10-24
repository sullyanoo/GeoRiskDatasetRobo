import geopandas as gpd
from src.settings.settings import *
from pystac_client import Client
import planetary_computer
import rasterio
from rasterio.mask import mask
from rasterio.errors import WindowError
from shapely.geometry import box
import numpy as np
from src.settings.settings import NDVI


# NDVI
def calcular_percentual_verde_ndvi(geom_metrico):
    try:
        if geom_metrico.geom_type == "Point":
            geom_metrico = geom_metrico.buffer(150)

        if geom_metrico.area < 10:
            geom_metrico = geom_metrico.buffer(150)

        gdf_metrico = gpd.GeoDataFrame(
            geometry=[geom_metrico],
            crs=CRS_METRICO
        )

        gdf_wgs84 = gdf_metrico.to_crs("EPSG:4326")
        bbox = gdf_wgs84.total_bounds

        catalog = Client.open(
            NDVI
        )

        search = catalog.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            query={"eo:cloud_cover": {"lt": 20}},
            max_items=5
        )

        items = list(search.get_items())

        if not items:
            return 0.0

        melhores_resultados = []

        for item in items:

            try:

                signed_item = planetary_computer.sign(item)

                red_href = signed_item.assets["B04"].href
                nir_href = signed_item.assets["B08"].href

                with rasterio.open(red_href) as red_src:

                    gdf_raster_crs = gdf_wgs84.to_crs(red_src.crs)
                    geometry_raster = gdf_raster_crs.geometry.iloc[0].__geo_interface__

                    if not gdf_raster_crs.geometry.iloc[0].intersects(box(*red_src.bounds)):
                        continue

                    red_img, _ = mask(red_src, [geometry_raster], crop=True, nodata=0)

                with rasterio.open(nir_href) as nir_src:

                    gdf_raster_crs = gdf_wgs84.to_crs(nir_src.crs)
                    geometry_raster = gdf_raster_crs.geometry.iloc[0].__geo_interface__

                    nir_img, _ = mask(nir_src, [geometry_raster], crop=True, nodata=0)

                red = red_img[0].astype("float32")
                nir = nir_img[0].astype("float32")

                valid_pixels = (red > 0) & (nir > 0)

                if np.sum(valid_pixels) == 0:
                    continue

                ndvi = np.where(
                    (nir + red) == 0,
                    0,
                    (nir - red) / (nir + red)
                )

                # Threshold mais adequado para vegetação urbana
                mask_veg = (ndvi > 0.25) & valid_pixels

                percentual_verde = np.sum(mask_veg) / np.sum(valid_pixels)

                melhores_resultados.append(float(percentual_verde))

            except (ValueError, WindowError):
                continue
            except Exception as e:
                print("Erro item Sentinel:", e)
                continue

        if not melhores_resultados:
            return 0.0

        return float(max(melhores_resultados))

    except Exception as e:
        print("Erro NDVI:", e)
        return 0.0