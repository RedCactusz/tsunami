import logging
import numpy as np
import random
from typing import Dict, List, Optional
import time

try:
    import geopandas as gpd
    from shapely.geometry import Point, MultiPolygon, Polygon
except ImportError:
    pass

try:
    import osmnx as ox
except ImportError:
    ox = None

logger = logging.getLogger(__name__)

def load_desa_data(shapefile_path: str):
    gdf = gpd.read_file(shapefile_path)
    if gdf.crs is not None:
        gdf = gdf.to_crs(epsg=4326)
    return gdf

def load_settlement_data(geojson_path: str):
    """Load pemukiman data dari GeoJSON file (Pemukiman.geojson)."""
    gdf = gpd.read_file(geojson_path)
    if gdf.crs is not None:
        gdf = gdf.to_crs(epsg=4326)
    return gdf

class SettlementAnalyzer:
    def __init__(self, desa_gdf, settlement_gdf=None, use_gpu=True):
        self.desa_gdf = desa_gdf
        self.settlement_gdf = settlement_gdf
        self.use_gpu = use_gpu
        self.desa_stats = {}
        self.affected_settlements_count = 0
        self.affected_pop = 0
        self.osm_gdf = None

    def fetch_osm_residential(self, bbox: Optional[tuple] = None):
        """
        [OBSOLETE] Previously used to fetch OSM landuse=residential.
        However, OSM is missing landuse=residential tags on the Bantul coast,
        causing agents to spawn far inland (fallback).
        We now use Bangunan_Bantul.shp directly.
        """
        pass

    def analyze_pemukiman_geojson(self):
        """
        Analisis langsung dari Pemukiman.geojson tanpa intersect dengan desa.
        Setiap feature di Pemukiman.geojson adalah area permukiman dengan data penduduk.
        """
        if self.settlement_gdf is None:
            logger.warning("[SettlementAnalyzer] No settlement data available!")
            return

        for idx, row in self.settlement_gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue

            # Get nama desa dan penduduk dari Pemukiman.geojson
            desa_name = row.get('NAMOBJ', f"Pemukiman_{idx}")
            population = int(row.get('Penduduk', row.get('PENDUDUK', 1000)))
            kepadatan = row.get('Kepadatan', 0)

            # Hitung area polygon
            if hasattr(geom, 'area'):
                area = geom.area
            else:
                area = 0

            self.desa_stats[desa_name] = {
                'population': population,
                'total_settlement_area': area,
                'density': kepadatan,
                'settlements': self.settlement_gdf.iloc[[idx]],  # Single row as GeoDataFrame
                'geometry': geom,
                'original_idx': idx
            }

        logger.info(f"[SettlementAnalyzer] Analyzed {len(self.desa_stats)} pemukiman areas")

    def analyze_settlements_per_desa(self):
        """
        Analisis distribusi penduduk berdasarkan area permukiman (OSM atau Shapefile).
        """
        if self.settlement_gdf is None:
            logger.warning("[SettlementAnalyzer] No settlement data available!")
            return

        for idx, desa in self.desa_gdf.iterrows():
            desa_geom = desa.geometry
            if desa_geom is None:
                continue
            
            desa_name = desa.get('NAMOBJ', desa.get('DESA', f"Desa_{idx}"))
            population = int(desa.get('PENDUDUK', desa.get('JIWA', 1000)))
            
            # Cari permukiman yang beririsan dengan desa ini
            desa_settlements = self.settlement_gdf[self.settlement_gdf.geometry.intersects(desa_geom)].copy()
            
            # Penting: Jika menggunakan poligon (OSM), area dihitung dalam derajat^2 
            # lalu dikonversi ke proporsi total area permukiman desa tersebut.
            total_settlement_area = desa_settlements.geometry.area.sum()
            
            if total_settlement_area > 0:
                density = population / total_settlement_area
            else:
                # Fallback: jika tidak ada data permukiman di desa ini, 
                # buat satu "titik representasi" di tengah desa agar penduduk tidak hilang
                density = 0
                logger.debug(f"[SettlementAnalyzer] Desa {desa_name} has no settlement polygons, using centroid fallback")

            self.desa_stats[desa_name] = {
                'population': population,
                'total_settlement_area': total_settlement_area,
                'density': density,
                'settlements': desa_settlements,
                'geometry': desa_geom
            }

    def filter_settlements_in_inundation_zone(self, inundation_polygon, depth_grid, grid_bounds, hazard_threshold_m=0.3, inundation_geojson=None):
        """
        Filter area permukiman yang tergenang.
        """
        import numpy as np
        affected_settlements = []
        n_checked = 0
        n_in_zone = 0
        
        # KDTree untuk lookup kedalaman cepat dari inundation_geojson
        flood_points = []
        if inundation_geojson and 'features' in inundation_geojson:
            for feat in inundation_geojson['features']:
                geom = feat.get('geometry', {})
                if geom.get('type') == 'Point':
                    coords = geom.get('coordinates', [])
                    if len(coords) >= 2:
                        depth = feat.get('properties', {}).get('flood_depth', feat.get('properties', {}).get('depth_m', 1.0))
                        flood_points.append((coords[0], coords[1], depth))
        
        from scipy.spatial import KDTree
        kdtree = KDTree([(p[0], p[1]) for p in flood_points]) if flood_points else None

        for desa_name, stats in self.desa_stats.items():
            settlements = stats['settlements']
            
            # Jika desa ini sama sekali tidak punya poligon permukiman, buat satu titik di pusat desa
            if settlements.empty:
                centroid = stats['geometry'].centroid
                settlements = gpd.GeoDataFrame([{'geometry': centroid}], crs="EPSG:4326")

            for idx, settlement in settlements.iterrows():
                # Jika poligon, ambil centroid untuk check inundasi
                centroid = settlement.geometry.centroid
                lon, lat = centroid.x, centroid.y
                n_checked += 1
                
                is_inundated = False
                depth = 1.0 # default
                
                # Check 1: KDTree (paling akurat dengan visualisasi)
                if kdtree is not None:
                    dist, i = kdtree.query((lon, lat), distance_upper_bound=0.005) # ~500m
                    if dist != float('inf'):
                        is_inundated = True
                        depth = flood_points[i][2]
                
                # Check 2: Polygon Inundasi
                if not is_inundated and inundation_polygon is not None:
                    try:
                        if inundation_polygon.intersects(settlement.geometry):
                            is_inundated = True
                    except: pass
                
                if is_inundated and depth >= hazard_threshold_m:
                    n_in_zone += 1
                    # Hitung populasi representatif
                    # Jika poligon: area * density. Jika titik (fallback): total pop desa.
                    if hasattr(settlement.geometry, 'area') and settlement.geometry.area > 0:
                        pop_rep = int(settlement.geometry.area * stats['density'])
                    else:
                        pop_rep = stats['population']
                    
                    pop_rep = max(pop_rep, 1)
                    self.affected_pop += pop_rep
                    
                    affected_settlements.append({
                        'settlement_id': f"{desa_name}_{idx}",
                        'desa': desa_name,
                        'lat': lat,
                        'lon': lon,
                        'area': getattr(settlement.geometry, 'area', 0),
                        'population_represented': pop_rep,
                        'initial_depth': depth,
                        'hazard_level': 'TINGGI' if depth > 1.0 else 'SEDANG'
                    })
        
        self.affected_settlements_count = len(affected_settlements)
        logger.info(f"[SettlementAnalyzer] Analysis complete: {n_in_zone} zones affected, "
                    f"Total Affected Population: {self.affected_pop:,}")
        return affected_settlements

    def generate_agent_positions(self, affected_settlements, agents_per_person=0.01):
        """
        Generate agen dari area permukiman yang terdampak.
        Agar tidak timeout, jumlah agen dibatasi rasio yang ketat.
        """
        agents = []
        total_requested_agents = int(self.affected_pop * agents_per_person)
        logger.info(f"[SettlementAnalyzer] Generating ~{total_requested_agents} agents for {self.affected_pop:,} people")
        
        for s in affected_settlements:
            # Proporsional terhadap populasi area ini
            num_agents = int(s['population_represented'] * agents_per_person)
            
            # Probabilistic fallback: jika < 1 tapi ada populasi, berikan kesempatan kecil untuk muncul agen
            if num_agents < 1 and s['population_represented'] > 0:
                if random.random() < (s['population_represented'] * agents_per_person):
                    num_agents = 1
            
            if num_agents < 1:
                continue
                
            pop_per_agent = int(s['population_represented'] / num_agents)
            
            for i in range(num_agents):
                # Jitter lat/lon agar tidak bertumpuk di satu titik (centroid)
                lat_jitter = s['lat'] + random.uniform(-0.0005, 0.0005)
                lon_jitter = s['lon'] + random.uniform(-0.0005, 0.0005)
                
                agents.append({
                    'agent_id': f"{s['settlement_id']}_{i}",
                    'lat': lat_jitter,
                    'lon': lon_jitter,
                    'settlement_id': s['settlement_id'],
                    'desa': s['desa'],
                    'population_represented': pop_per_agent,
                    'initial_depth': s['initial_depth'],
                    'hazard_level': s['hazard_level']
                })
        
        logger.info(f"[SettlementAnalyzer] Final agents generated: {len(agents)}")
        return agents

    def get_summary_statistics(self):
        total_pop = sum(s['population'] for s in self.desa_stats.values())
        return {
            'total_desa': len(self.desa_stats),
            'total_settlements': sum(len(s['settlements']) for s in self.desa_stats.values()),
            'affected_settlements': self.affected_settlements_count,
            'total_population': total_pop,
            'affected_population': self.affected_pop,
            'affected_percentage': (self.affected_pop / total_pop * 100) if total_pop > 0 else 0.0
        }
