"""
Global Data Loader untuk ABM
Load dan cache data dari folder /data
"""
import os
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Global data cache
_GLOBAL_CACHE = {
    'pemukiman': [],
    'tes': [],
    'roads': [],
    'coastline': None,
    'loaded': False
}

DATA_DIR = os.path.join(os.path.dirname(__file__), '../../data')
VEKTOR_DIR = os.path.join(DATA_DIR, 'Vektor')


def load_global_data():
    """Load semua data global (cache sekali, used everywhere)."""
    global _GLOBAL_CACHE

    if _GLOBAL_CACHE['loaded']:
        logger.info("[DataLoader] Global data already loaded, skipping...")
        return _GLOBAL_CACHE

    logger.info(f"[DataLoader] Loading global data from {VEKTOR_DIR}")

    # Load Pemukiman
    try:
        import geopandas as gpd
        pemukiman_path = os.path.join(VEKTOR_DIR, 'Pemukiman.geojson')

        if os.path.exists(pemukiman_path):
            logger.info(f"[DataLoader] Loading Pemukiman.geojson...")
            gdf = gpd.read_file(pemukiman_path)

            if gdf.crs is not None:
                gdf = gdf.to_crs(epsg=4326)

            # Convert ke list of dict
            pemukiman_list = []
            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom is None:
                    continue

                # Get centroid
                if hasattr(geom, 'centroid'):
                    centroid = geom.centroid
                    lat, lon = centroid.y, centroid.x
                elif hasattr(geom, 'representative_point'):
                    rep_point = geom.representative_point()
                    lat, lon = rep_point.y, rep_point.x
                else:
                    continue

                name = str(row.get('NAMOBJ', f"Pemukiman_{idx}"))
                population = int(row.get('Penduduk', 1000))

                pemukiman_list.append({
                    'id': f"pemukiman_{idx}",
                    'name': name,
                    'population': population,
                    'centroid_lat': lat,
                    'centroid_lon': lon,
                    'geometry': geom
                })

            _GLOBAL_CACHE['pemukiman'] = pemukiman_list
            logger.info(f"[DataLoader] ✅ Loaded {len(pemukiman_list)} pemukiman")
        else:
            logger.warning(f"[DataLoader] Pemukiman.geojson not found at {pemukiman_path}")

    except Exception as e:
        logger.error(f"[DataLoader] Failed to load pemukiman: {e}")

    # Load TES
    try:
        import geopandas as gpd
        tes_path = os.path.join(VEKTOR_DIR, 'TES_Bantul.shp')

        if os.path.exists(tes_path):
            logger.info(f"[DataLoader] Loading TES_Bantul.shp...")
            gdf = gpd.read_file(tes_path)

            if gdf.crs is not None:
                gdf = gdf.to_crs(epsg=4326)

            tes_list = []
            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom is None:
                    continue

                if hasattr(geom, 'centroid'):
                    cx, cy = geom.centroid.x, geom.centroid.y
                else:
                    cx, cy = geom.x, geom.y

                name = str(row.get('Nama', f"TES_{idx}"))
                capacity = int(row.get('kapasitas', 500))

                tes_list.append({
                    'id': idx,
                    'name': name,
                    'lat': cy,
                    'lon': cx,
                    'capacity': capacity,
                    'geometry': geom
                })

            _GLOBAL_CACHE['tes'] = tes_list
            logger.info(f"[DataLoader] ✅ Loaded {len(tes_list)} TES")
        else:
            logger.warning(f"[DataLoader] TES_Bantul.shp not found at {tes_path}")

    except Exception as e:
        logger.error(f"[DataLoader] Failed to load TES: {e}")

    _GLOBAL_CACHE['loaded'] = True
    logger.info(f"[DataLoader] ✅ Global data loaded: {len(_GLOBAL_CACHE['pemukiman'])} pemukiman, {len(_GLOBAL_CACHE['tes'])} TES")

    return _GLOBAL_CACHE


def get_pemukiman_data() -> List[Dict]:
    """Get pemukiman data from global cache."""
    if not _GLOBAL_CACHE['loaded']:
        load_global_data()
    return _GLOBAL_CACHE['pemukiman']


def get_tes_data() -> List[Dict]:
    """Get TES data from global cache."""
    if not _GLOBAL_CACHE['loaded']:
        load_global_data()
    return _GLOBAL_CACHE['tes']


def get_nearest_tes(lat: float, lon: float) -> Dict:
    """Cari TES terdekat dari titik (lat, lon)."""
    from .spatial_utils import haversine_m

    tes_list = get_tes_data()

    if not tes_list:
        return None

    nearest = None
    min_dist = float('inf')

    for tes in tes_list:
        dist = haversine_m(lat, lon, tes['lat'], tes['lon'])
        if dist < min_dist:
            min_dist = dist
            nearest = tes

    return nearest
