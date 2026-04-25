"""
============================================================================
EVACUATION ABM - Agent-Based Model untuk Simulasi Evakuasi Tsunami
============================================================================
Author: Kelompok 3 - Mini Project Komputasi Geospasial S2 Geomatika UGM
Version: 2.0.0 (Refactored, Bugs Fixed)

Bug Fixes:
- BUG A: Import path corrected (from spatial_utils)
- BUG B: Function naming consistent (build_evacuation_graph)
- BUG C: Missing imports added (defaultdict, heapq)
- BUG D: arrived_by_desa double-counting fixed (using 'counted' flag)
- BUG E: Division by zero handled via safe_divide/calculate_slope_percent
============================================================================
"""

import os
import json
import math
import random
import logging
from collections import defaultdict  # ✅ BUG C FIX
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field

# ✅ BUG A FIX - Import from shared core module
from ..core import (
    haversine_m, haversine_km,
    bearing_degrees, destination_point,
    point_in_polygon, polygon_area_m2, bbox_from_points,
    dijkstra, astar, reconstruct_path,
    calculate_slope_percent, calculate_slope_degrees,
    elevation_penalty, slope_penalty,
    safe_divide, validate_coordinates, clamp,
    coords_to_geojson_point, coords_to_geojson_linestring,
    features_to_feature_collection,
    shp_to_geojson
)

try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

try:
    import osmnx as ox
    OSMNX_AVAILABLE = True
except ImportError:
    OSMNX_AVAILABLE = False

try:
    from shapely.geometry import Point, Polygon, LineString
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

try:
    from .abm_accelerated import (
        parse_wave_frames_gpu, GPUNodeIndex, batch_flood_check_gpu,
        batch_update_agents_gpu, mark_flooded_edges_gpu,
        get_abm_gpu_status, CUPY_AVAILABLE as ABM_GPU_AVAILABLE
    )
except ImportError:
    ABM_GPU_AVAILABLE = False
    parse_wave_frames_gpu = None
    GPUNodeIndex = None
    batch_flood_check_gpu = None
    batch_update_agents_gpu = None

import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# KONSTANTA
# ============================================================================

SPEED_MAP = {
    'motorway': 80, 'trunk': 70, 'primary': 60, 'secondary': 50,
    'tertiary': 40, 'unclassified': 30, 'residential': 30,
    'service': 20, 'track': 15, 'path': 5, 'footway': 5, 'pedestrian': 5
}

WEIGHT_DISTANCE = 0.30
WEIGHT_TIME = 0.30
WEIGHT_ELEVATION = 0.25
WEIGHT_SLOPE = 0.15

FLOOD_PENALTY = 10.0
DEFAULT_SHELTER_CAPACITY = 250
RESPONSE_DELAY_RANGE = (0, 5)
SAFE_ELEVATION_M = 20.0

# ── Transport Mode Speeds (m/s) — Referensi ABM Revisi ──
TRANSPORT_SPEEDS = {
    'foot': 1.38,   # Pejalan kaki
    'motor': 5.66,  # Sepeda motor
    'car': 4.17     # Mobil
}

# ── Modal Split — Referensi ABM Revisi ──
MODAL_SPLIT = {
    'foot': 0.10,   # 10% pejalan kaki
    'motor': 0.70,  # 70% sepeda motor
    'car': 0.20     # 20% mobil
}

# ── Transport Mode Area (m²) — untuk capacity calculation ──
TRANSPORT_AREA = {
    'foot': 0.5,
    'motor': 3.0,
    'car': 9.0
}

# ── Slope Factor Table — Referensi ABM Revisi ──
def get_slope_factor(slope_deg: float) -> float:
    """Konversi slope derajat ke faktor kecepatan."""
    if slope_deg <= 5:
        return 1.0
    elif slope_deg <= 10:
        return 0.9
    elif slope_deg <= 15:
        return 0.7
    elif slope_deg <= 20:
        return 0.5
    else:
        return 0.3


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Agent:
    id: int
    home_lat: float
    home_lon: float
    home_node: int
    desa_name: str
    population: int = 1
    status: str = "waiting"
    counted: bool = False  # ✅ BUG D FIX
    path: List[int] = field(default_factory=list)
    current_path_idx: int = 0
    dist_covered_m: float = 0.0
    shelter_id: Optional[int] = None
    response_delay: float = 0.0
    speed_mps: float = 1.38
    start_time: float = 0.0
    arrival_time: Optional[float] = None
    
    # ── Referensi ABM Revisi: Transport Mode ──
    transport_mode: str = 'foot'        # 'foot', 'motor', 'car'
    weight: int = 1                     # Populasi per agent (= population)
    distance_to_coast_km: float = 0.0   # Jarak ke garis pantai
    in_hazard_zone: bool = False         # Apakah di zona bahaya tsunami
    flood_depth_m: float = 0.0           # Kedalaman genangan di posisi awal
    hazard_risk_level: str = 'AMAN'      # AMAN/RENDAH/SEDANG/TINGGI/EKSTREM
    slope_deg: float = 0.0               # Slope di posisi saat ini
    
    @property
    def base_speed_ms(self) -> float:
        """Kecepatan base per transport mode (m/s)"""
        return TRANSPORT_SPEEDS.get(self.transport_mode, 1.38)
    
    @property
    def friction_factor(self) -> float:
        """Friction factor dari populasi (weight^-0.3)"""
        return max(0.3, self.weight ** (-0.3))
    
    @property
    def slope_factor(self) -> float:
        """Slope factor berdasarkan slope_deg"""
        return get_slope_factor(self.slope_deg)
    
    @property
    def effective_speed_ms(self) -> float:
        """Kecepatan efektif = base × friction × slope"""
        return self.base_speed_ms * self.friction_factor * self.slope_factor
    
    @property
    def area_m2(self) -> float:
        """Area yang ditempati agent (m²)"""
        return self.weight * TRANSPORT_AREA.get(self.transport_mode, 0.5)


@dataclass
class Shelter:
    id: int
    name: str
    lat: float
    lon: float
    capacity: int = DEFAULT_SHELTER_CAPACITY
    current_occupancy: int = 0
    node_id: Optional[int] = None
    elevation: float = 0.0
    distance_to_coast_km: float = 0.0  # Referensi ABM: TES terjauh dari pantai


@dataclass
class ABMResults:
    total_agents: int
    total_population: int
    arrived: int
    stranded: int
    evacuation_timeline: List[Dict]
    per_desa_stats: Dict[str, Dict]
    per_shelter_stats: Dict[int, Dict]
    routes_geojson: Dict
    simulation_duration_min: float
    statistics: Dict[str, Any]


# ============================================================================
# GEOMETRY HELPERS
# ============================================================================

def get_valid_land_point(polygon_coords: List[Tuple[float, float]], 
                           dem_mgr=None) -> Tuple[float, float]:
    """
    Pastikan titik (misal centroid desa) berada di DARAT (elev > 0).
    
    Returns:
        (lat, lon) titik valid di darat
    """
    if not polygon_coords:
        return (0.0, 0.0)
    
    lons = [p[0] for p in polygon_coords]
    lats = [p[1] for p in polygon_coords]
    cx = sum(lons) / len(lons)
    cy = sum(lats) / len(lats)
    
    if dem_mgr is None:
        return (cy, cx)
    
    def query_elev(lat, lon):
        try:
            if hasattr(dem_mgr, 'query_elevation'):
                return dem_mgr.query_elevation(lat, lon)
            return dem_mgr(lat, lon)
        except Exception:
            return None
    
    # Priority 1: Centroid
    elev = query_elev(cy, cx)
    if elev is not None and elev > 0:
        return (cy, cx)
    
    # Priority 2: Grid sampling
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    
    for n in [5, 10]:
        for i in range(1, n):
            for j in range(1, n):
                test_lon = min_lon + (max_lon - min_lon) * i / n
                test_lat = min_lat + (max_lat - min_lat) * j / n
                if point_in_polygon((test_lon, test_lat), polygon_coords):
                    e = query_elev(test_lat, test_lon)
                    if e is not None and e > 0:
                        return (test_lat, test_lon)
    
    # Priority 3: Exterior vertex dengan elevasi tertinggi
    best_elev = -9999
    best_point = (cy, cx)
    for lon, lat in polygon_coords:
        e = query_elev(lat, lon)
        if e is not None and e > best_elev:
            best_elev = e
            best_point = (lat, lon)
    
    return best_point


# ============================================================================
# CACHE BUILDERS
# ============================================================================

class DataCache:
    """Cache untuk road network, desa, dan shelter."""
    
    def __init__(self, vektor_dir: str, dem_mgr=None):
        self.vektor_dir = vektor_dir
        self.dem_mgr = dem_mgr
        self.roads: List[Dict] = []
        self.desa: List[Dict] = []
        self.shelters: List[Shelter] = []
    
    def build_all(self):
        self._build_road_cache()
        self._build_desa_cache()
        self._build_tes_cache()
        logger.info(f"Cache built: {len(self.roads)} roads, "
                    f"{len(self.desa)} desa, {len(self.shelters)} shelters")
    
    def _build_road_cache(self):
        """Scan direktori untuk road network files."""
        if not GEOPANDAS_AVAILABLE or not os.path.isdir(self.vektor_dir):
            return
        
        keywords = ['jalan', 'road', 'transport']
        for fname in os.listdir(self.vektor_dir):
            if not fname.lower().endswith('.shp'):
                continue
            if not any(k in fname.lower() for k in keywords):
                continue
            
            fpath = os.path.join(self.vektor_dir, fname)
            try:
                gdf = gpd.read_file(fpath)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                else:
                    gdf = gdf.to_crs(epsg=4326)
                
                for idx, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None or geom.geom_type != 'LineString':
                        continue
                    
                    highway_type = (row.get('highway') or 
                                     row.get('HIGHWAY') or 
                                     row.get('fclass') or 
                                     'residential')
                    speed = SPEED_MAP.get(str(highway_type).lower(), 30)
                    lanes = row.get('lanes', 1) or 1
                    try:
                        lanes = int(lanes)
                    except (ValueError, TypeError):
                        lanes = 1
                    
                    coords = list(geom.coords)
                    self.roads.append({
                        'id': len(self.roads),
                        'coords': coords,
                        'highway': str(highway_type),
                        'name': str(row.get('name', '')),
                        'oneway': bool(row.get('oneway', False)),
                        'speed_kmh': speed,
                        'lanes': lanes,
                        'capacity': lanes * 1000
                    })
            except Exception as e:
                logger.warning(f"Failed to load road file {fname}: {e}")
    
    def _build_desa_cache(self):
        """Scan direktori untuk administrative boundaries."""
        if not GEOPANDAS_AVAILABLE or not os.path.isdir(self.vektor_dir):
            return
        
        keywords = ['desa', 'kelurahan', 'administrasi']
        for fname in os.listdir(self.vektor_dir):
            if not fname.lower().endswith('.shp'):
                continue
            if not any(k in fname.lower() for k in keywords):
                continue
            
            fpath = os.path.join(self.vektor_dir, fname)
            try:
                gdf = gpd.read_file(fpath)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                else:
                    gdf = gdf.to_crs(epsg=4326)
                
                for idx, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    
                    name = (row.get('NAMOBJ') or row.get('DESA') or 
                             row.get('NAMA') or row.get('name') or 
                             f"Desa_{idx}")
                    pop = (row.get('JIWA') or row.get('POPULATION') or 
                            row.get('JUMLAH_PEN') or 0)
                    try:
                        pop = int(pop)
                    except (ValueError, TypeError):
                        pop = 0
                    
                    if geom.geom_type == 'MultiPolygon':
                        geom = max(geom.geoms, key=lambda g: g.area)
                    if geom.geom_type != 'Polygon':
                        continue
                    
                    poly_coords = [(p[0], p[1]) for p in geom.exterior.coords]
                    centroid = get_valid_land_point(poly_coords, self.dem_mgr)
                    
                    self.desa.append({
                        'id': len(self.desa),
                        'name': str(name),
                        'population': pop,
                        'centroid_lat': centroid[0],
                        'centroid_lon': centroid[1],
                        'polygon': poly_coords
                    })
            except Exception as e:
                logger.warning(f"Failed to load desa file {fname}: {e}")
    
    def _build_tes_cache(self):
        """Scan direktori untuk TES / shelter."""
        if not GEOPANDAS_AVAILABLE or not os.path.isdir(self.vektor_dir):
            return
        
        keywords = ['tes', 'shelter', 'evakuasi']
        for fname in os.listdir(self.vektor_dir):
            if not fname.lower().endswith('.shp'):
                continue
            if not any(k in fname.lower() for k in keywords):
                continue
            
            fpath = os.path.join(self.vektor_dir, fname)
            try:
                gdf = gpd.read_file(fpath)
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                else:
                    gdf = gdf.to_crs(epsg=4326)
                
                for idx, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    
                    if hasattr(geom, 'centroid'):
                        cx, cy = geom.centroid.x, geom.centroid.y
                    else:
                        cx, cy = geom.x, geom.y
                    
                    name = (row.get('Nama') or row.get('NAMA') or row.get('name') or 
                             f"Shelter_{idx}")
                    cap = (row.get('KAPASITAS') or row.get('capacity') or 
                            DEFAULT_SHELTER_CAPACITY)
                    try:
                        cap = int(cap)
                    except (ValueError, TypeError):
                        cap = DEFAULT_SHELTER_CAPACITY
                    
                    # Query elevasi
                    elev = 0.0
                    if self.dem_mgr:
                        try:
                            e = self.dem_mgr.query_elevation(cy, cx) if \
                                hasattr(self.dem_mgr, 'query_elevation') else None
                            if e is not None:
                                elev = float(e)
                        except Exception:
                            pass
                    
                    self.shelters.append(Shelter(
                        id=len(self.shelters),
                        name=str(name),
                        lat=cy,
                        lon=cx,
                        capacity=cap,
                        elevation=elev
                    ))
            except Exception as e:
                logger.warning(f"Failed to load TES file {fname}: {e}")


# ============================================================================
# GRAPH BUILDER
# ============================================================================

class EvacuationGraph:
    """
    Graph untuk routing evakuasi dengan composite cost.
    Cost = w_dist * dist + w_time * time + w_elev * elev_pen + w_slope * slope_pen
    """
    
    def __init__(self, cache: DataCache, dem_mgr=None):
        self.cache = cache
        self.dem_mgr = dem_mgr
        
        self.nodes: Dict[int, Tuple[float, float]] = {}  # node_id -> (lat, lon)
        self.node_elev: Dict[int, float] = {}
        self.adj: Dict[int, List[Tuple[int, float, float]]] = defaultdict(list)
        # adj[u] = [(v, cost, distance_m), ...]
        
        self.edge_meta: Dict[Tuple[int, int], Dict] = {}
        # edge_meta[(u,v)] = {road_id, highway, speed, ...}
    
    def build_evacuation_graph(self):
        """
        ✅ BUG B FIX: Nama fungsi konsisten (build_evacuation_graph).
        
        Build graph dari roads cache dengan composite weighting.
        """
        if not self.cache.roads:
            logger.warning("No roads in cache, graph will be empty")
            return
        
        node_id_counter = 0
        coord_to_node: Dict[Tuple[float, float], int] = {}
        
        def get_or_create_node(lon: float, lat: float) -> int:
            nonlocal node_id_counter
            # Round untuk menggabungkan node yang sangat dekat
            key = (round(lon, 6), round(lat, 6))
            if key in coord_to_node:
                return coord_to_node[key]
            
            nid = node_id_counter
            coord_to_node[key] = nid
            self.nodes[nid] = (lat, lon)
            
            # Skip per-node DEM query — too slow for 100k+ nodes
            # Elevasi di-set 0, slope penalty tetap minimal
            self.node_elev[nid] = 0.0
            
            node_id_counter += 1
            return nid
        
        # Build edges
        for road in self.cache.roads:
            coords = road['coords']
            speed_kmh = road['speed_kmh']
            speed_mps = speed_kmh / 3.6
            oneway = road['oneway']
            
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i][0], coords[i][1]
                lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
                
                u = get_or_create_node(lon1, lat1)
                v = get_or_create_node(lon2, lat2)
                
                if u == v:
                    continue
                
                # Distance
                dist_m = haversine_m(lat1, lon1, lat2, lon2)
                if dist_m < 1e-3:
                    continue
                
                # Time
                time_s = safe_divide(dist_m, speed_mps, default=dist_m / 1.0)
                
                # Elevation penalty
                e1 = self.node_elev.get(u, 0.0)
                e2 = self.node_elev.get(v, 0.0)
                avg_elev = 0.5 * (e1 + e2)
                elev_pen = elevation_penalty(avg_elev, SAFE_ELEVATION_M)
                
                # ✅ BUG E FIX: Safe slope calculation
                slope_pct = calculate_slope_percent(e1, e2, dist_m)
                slope_pen = slope_penalty(slope_pct)
                
                # Normalize factors
                norm_dist = dist_m / 1000.0  # km
                norm_time = time_s / 60.0    # min
                
                # Composite cost
                cost = (WEIGHT_DISTANCE * norm_dist +
                        WEIGHT_TIME * norm_time +
                        WEIGHT_ELEVATION * (elev_pen - 1.0) +
                        WEIGHT_SLOPE * (slope_pen - 1.0))
                
                cost = max(cost, 1e-6)
                
                # Add edge
                self.adj[u].append((v, cost, dist_m))
                self.edge_meta[(u, v)] = {
                    'road_id': road['id'],
                    'highway': road['highway'],
                    'speed_kmh': speed_kmh,
                    'distance_m': dist_m,
                    'time_s': time_s,
                    'slope_pct': slope_pct
                }
                
                if not oneway:
                    self.adj[v].append((u, cost, dist_m))
                    self.edge_meta[(v, u)] = self.edge_meta[(u, v)].copy()
        
        logger.info(f"Graph built: {len(self.nodes)} nodes, "
                    f"{sum(len(v) for v in self.adj.values())} edges")
        
        # Batch DEM elevation query — buka file SEKALI, query semua node
        self._batch_elevation_query()
        
        # Build spatial index for fast nearest-node lookups
        self._build_spatial_index()
    
    def _batch_elevation_query(self):
        """Batch query elevasi DEM untuk semua node sekaligus (vectorized)."""
        if not self.dem_mgr or not self.nodes:
            return
        
        try:
            import rasterio
            from rasterio.transform import rowcol
        except ImportError:
            logger.warning("rasterio not available, skipping batch elevation")
            return
        
        # Kumpulkan semua koordinat node
        node_ids = list(self.nodes.keys())
        lats = np.array([self.nodes[nid][0] for nid in node_ids], dtype=np.float64)
        lons = np.array([self.nodes[nid][1] for nid in node_ids], dtype=np.float64)
        
        n_filled = 0
        for tile in self.dem_mgr.tiles:
            try:
                with rasterio.open(tile['path']) as src:
                    b = src.bounds
                    # Filter node yang ada di dalam tile ini
                    mask = (lons >= b.left) & (lons <= b.right) & \
                           (lats >= b.bottom) & (lats <= b.top)
                    
                    if not np.any(mask):
                        continue
                    
                    # Baca seluruh raster SEKALI
                    data = src.read(1)
                    
                    # Vectorized row/col conversion
                    rows_arr, cols_arr = rowcol(
                        src.transform, 
                        lons[mask].tolist(), 
                        lats[mask].tolist()
                    )
                    rows_arr = np.array(rows_arr, dtype=np.int32)
                    cols_arr = np.array(cols_arr, dtype=np.int32)
                    
                    # Bounds check
                    valid = (rows_arr >= 0) & (rows_arr < src.shape[0]) & \
                            (cols_arr >= 0) & (cols_arr < src.shape[1])
                    
                    # Extract elevasi
                    masked_ids = np.array(node_ids)[mask]
                    for idx in np.where(valid)[0]:
                        val = float(data[rows_arr[idx], cols_arr[idx]])
                        if -100 < val < 10000:
                            self.node_elev[masked_ids[idx]] = val
                            n_filled += 1
                    
            except Exception as e:
                logger.warning(f"Batch DEM query error for tile: {e}")
                continue
        
        logger.info(f"Batch DEM elevation: {n_filled}/{len(node_ids)} nodes filled")
    
    def _build_spatial_index(self):
        """Build KDTree spatial index for O(log N) nearest-node queries."""
        if GPUNodeIndex is not None and len(self.nodes) > 0:
            self._node_index = GPUNodeIndex(self.nodes)
            logger.info(f"GPUNodeIndex built: {len(self.nodes)} nodes (KDTree)")
        else:
            self._node_index = None
    
    def nearest_node(self, lat: float, lon: float, 
                      max_dist_m: float = 5000) -> Optional[int]:
        """Cari node terdekat — KDTree O(log N) jika tersedia."""
        # Use GPUNodeIndex if available
        if hasattr(self, '_node_index') and self._node_index is not None:
            max_dist_deg = max_dist_m / 111_000.0  # approx m → deg
            return self._node_index.nearest(lat, lon, max_dist_deg)
        
        # Fallback: brute force
        best_node = None
        best_dist = float('inf')
        
        for nid, (nlat, nlon) in self.nodes.items():
            d = haversine_m(lat, lon, nlat, nlon)
            if d < best_dist:
                best_dist = d
                best_node = nid
        
        if best_dist > max_dist_m:
            return None
        return best_node
    
    def to_graph_dict(self) -> Dict[int, List[Tuple[int, float]]]:
        """Convert ke format {node: [(neighbor, weight), ...]} untuk dijkstra."""
        result = {}
        for u, edges in self.adj.items():
            result[u] = [(v, cost) for v, cost, _ in edges]
        return result


# ============================================================================
# ROUTING
# ============================================================================

class EvacuationRouter:
    """Router untuk mencari rute evakuasi optimal."""
    
    def __init__(self, graph: EvacuationGraph):
        self.graph = graph
        self.flood_blocked_edges: set = set()
    
    def set_flood_data(self, flood_polygons: List[List[Tuple[float, float]]]):
        """Mark edges yang terkena banjir untuk diberi penalty."""
        self.flood_blocked_edges.clear()
        
        for (u, v), meta in self.graph.edge_meta.items():
            lat1, lon1 = self.graph.nodes[u]
            lat2, lon2 = self.graph.nodes[v]
            midlat = 0.5 * (lat1 + lat2)
            midlon = 0.5 * (lon1 + lon2)
            
            for poly in flood_polygons:
                if point_in_polygon((midlon, midlat), poly):
                    self.flood_blocked_edges.add((u, v))
                    break
        
        logger.info(f"Flood: {len(self.flood_blocked_edges)} edges blocked")
    
    def find_nearest_shelter(self, agent_node: int, 
                                shelters: List[Shelter],
                                use_astar: bool = True
                                ) -> Tuple[Optional[Shelter], List[int], float]:
        """
        Cari shelter terdekat dari agent (berdasarkan composite cost).
        
        Returns:
            (shelter, path, total_cost)
        """
        graph_dict = self.graph.to_graph_dict()
        
        def edge_penalty(u: int, v: int) -> float:
            if (u, v) in self.flood_blocked_edges:
                return FLOOD_PENALTY
            return 1.0
        
        best_shelter = None
        best_path = []
        best_cost = float('inf')
        
        # Filter shelter yang masih punya kapasitas
        available = [s for s in shelters if s.current_occupancy < s.capacity]
        if not available:
            return None, [], float('inf')
        
        if use_astar:
            # A* per shelter
            for shelter in available:
                if shelter.node_id is None:
                    shelter.node_id = self.graph.nearest_node(shelter.lat, shelter.lon)
                    if shelter.node_id is None:
                        continue
                
                path, cost = astar(
                    graph_dict, agent_node, shelter.node_id,
                    self.graph.nodes,
                    edge_filter=lambda u, v: (u, v) not in self.flood_blocked_edges
                )
                
                if path and cost < best_cost:
                    best_cost = cost
                    best_path = path
                    best_shelter = shelter
        else:
            # Dijkstra dari agent ke semua node
            distances, predecessors = dijkstra(
                graph_dict, agent_node,
                edge_penalty=edge_penalty
            )
            
            for shelter in available:
                if shelter.node_id is None:
                    shelter.node_id = self.graph.nearest_node(shelter.lat, shelter.lon)
                    if shelter.node_id is None:
                        continue
                
                cost = distances.get(shelter.node_id, float('inf'))
                if cost < best_cost:
                    best_cost = cost
                    best_path = reconstruct_path(predecessors, agent_node, shelter.node_id)
                    best_shelter = shelter
        
        return best_shelter, best_path, best_cost
    
    def find_safest_shelter(self, agent_node: int,
                              shelters: List[Shelter],
                              tsunami_deadline_s: float = float('inf'),
                              agent_speed_mps: float = 1.38
                              ) -> Tuple[Optional[Shelter], List[int], float]:
        """
        Referensi ABM Revisi: Pilih TES TERJAUH dari pantai 
        yang bisa dicapai sebelum tsunami tiba.
        
        Strategi:
        1. Hitung path ke semua TES yang available
        2. Filter TES yang bisa dicapai sebelum tsunami deadline
        3. Pilih TES dengan distance_to_coast TERBESAR
        4. Fallback: pilih TES terjauh dari pantai tanpa time filter
        
        Returns:
            (shelter, path, total_cost)
        """
        graph_dict = self.graph.to_graph_dict()
        
        # Dijkstra dari agent ke semua node
        def edge_penalty(u: int, v: int) -> float:
            if (u, v) in self.flood_blocked_edges:
                return FLOOD_PENALTY
            return 1.0
        
        distances, predecessors = dijkstra(
            graph_dict, agent_node,
            edge_penalty=edge_penalty
        )
        
        # Kumpulkan semua TES yang reachable
        available = [s for s in shelters if s.current_occupancy < s.capacity]
        if not available:
            return None, [], float('inf')
        
        reachable_tes = []
        for shelter in available:
            if shelter.node_id is None:
                shelter.node_id = self.graph.nearest_node(shelter.lat, shelter.lon)
                if shelter.node_id is None:
                    continue
            
            cost = distances.get(shelter.node_id, float('inf'))
            if cost == float('inf'):
                continue
            
            path = reconstruct_path(predecessors, agent_node, shelter.node_id)
            if not path:
                continue
            
            # Hitung travel time berdasarkan jarak dan kecepatan agent
            travel_dist_m = self.path_distance_m(path)
            travel_time_s = travel_dist_m / max(agent_speed_mps, 0.5)
            
            reachable_tes.append({
                'shelter': shelter,
                'path': path,
                'cost': cost,
                'travel_time_s': travel_time_s,
                'distance_to_coast_km': shelter.distance_to_coast_km,
            })
        
        if not reachable_tes:
            return None, [], float('inf')
        
        # Filter: hanya TES yang bisa dicapai sebelum tsunami
        safe_tes = [t for t in reachable_tes if t['travel_time_s'] <= tsunami_deadline_s]
        
        # Jika ada yang safe, pilih terjauh dari pantai
        if safe_tes:
            best = max(safe_tes, key=lambda t: t['distance_to_coast_km'])
        else:
            # Fallback: pilih terjauh dari pantai tanpa time filter
            best = max(reachable_tes, key=lambda t: t['distance_to_coast_km'])
        
        return best['shelter'], best['path'], best['cost']
    
    def path_distance_m(self, path: List[int]) -> float:
        """Total jarak (meter) dari path."""
        if len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            meta = self.graph.edge_meta.get((u, v))
            if meta:
                total += meta['distance_m']
            else:
                lat1, lon1 = self.graph.nodes[u]
                lat2, lon2 = self.graph.nodes[v]
                total += haversine_m(lat1, lon1, lat2, lon2)
        return total
    
    def path_to_coords(self, path: List[int]) -> List[Tuple[float, float]]:
        """Convert node path ke list (lat, lon)."""
        return [self.graph.nodes[n] for n in path if n in self.graph.nodes]


# ============================================================================
# ADAPTIVE SPEED CALCULATOR
# ============================================================================

class AdaptiveSpeedCalculator:
    """Hitung kecepatan agent berdasarkan tsunami dynamics & panic level."""
    
    def __init__(self, flood_checker=None, wave_arrival_func=None):
        self.flood_checker = flood_checker
        self.wave_arrival_func = wave_arrival_func
    
    def calculate_speed(self, agent_lat: float, agent_lon: float,
                        current_time_min: float,
                        base_speed_mps: float = 1.4) -> Dict:
        """
        Hitung kecepatan agent adaptif berdasarkan kondisi tsunami.
        
        Returns:
            {'speed_mps': float, 'speed_state': str, 'panic_level': float,
             'flood_depth_m': float}
        """
        flood_depth = 0.0
        is_flooded = False
        
        # Cek flood di posisi agent
        if self.flood_checker:
            is_flooded = self.flood_checker(agent_lat, agent_lon, current_time_min)
            if is_flooded:
                flood_depth = 0.5  # Default assumption
        
        # Estimasi waktu sampai tsunami
        time_to_arrival = 999.0
        if self.wave_arrival_func:
            wave_t = self.wave_arrival_func(agent_lat, agent_lon)
            if wave_t is not None:
                time_to_arrival = max(0, wave_t - current_time_min)
        
        # Adaptive speed formula
        base_speed_kmh = base_speed_mps * 3.6
        
        if is_flooded and flood_depth > 0.3:
            # Wading through water — slowed down significantly
            speed_factor = max(0.2, 1.0 - flood_depth / 3.0)
            speed_kmh = base_speed_kmh * speed_factor
            speed_state = 'wading'
            panic_level = 1.0
        elif time_to_arrival <= 5:
            # Critical — sprinting
            panic_factor = min(2.0, 1.5 + (5 - time_to_arrival) / 10.0)
            speed_kmh = min(10.0, base_speed_kmh * panic_factor)
            speed_state = 'sprinting'
            panic_level = 1.0
        elif time_to_arrival <= 15:
            # Urgent — hurrying
            panic_factor = 1.2 + (15 - time_to_arrival) / 30.0
            speed_kmh = min(8.0, base_speed_kmh * panic_factor)
            speed_state = 'hurrying'
            panic_level = min(1.0, (15 - time_to_arrival) / 15.0)
        else:
            # Normal evacuation
            speed_kmh = base_speed_kmh
            speed_state = 'normal'
            panic_level = 0.0
        
        speed_mps = max(0.3, speed_kmh / 3.6)
        
        return {
            'speed_mps': speed_mps,
            'speed_kmh': speed_kmh,
            'speed_state': speed_state,
            'panic_level': panic_level,
            'flood_depth_m': flood_depth,
            'time_to_arrival_min': time_to_arrival,
        }


# ============================================================================
# ABM SIMULATOR
# ============================================================================

class _ABMSimulator:
    """Internal time-step simulator."""
    
    def __init__(self, graph: EvacuationGraph, router: EvacuationRouter,
                   agents: List[Agent], shelters: List[Shelter],
                   warning_time_min: float = 5.0,
                   duration_min: float = 120.0,
                   dt_min: float = 1.0,
                   flood_checker: Optional[Callable] = None,
                   wave_arrival_func: Optional[Callable] = None):
        self.graph = graph
        self.router = router
        self.agents = agents
        self.shelters = shelters
        self.warning_time_s = warning_time_min * 60.0
        self.duration_s = duration_min * 60.0
        self.dt_s = dt_min * 60.0
        self.flood_checker = flood_checker
        self.wave_arrival_func = wave_arrival_func
        
        # Adaptive speed calculator
        self.speed_calc = AdaptiveSpeedCalculator(
            flood_checker=flood_checker,
            wave_arrival_func=wave_arrival_func
        )
        
        # Timeline tracking
        self.timeline: List[Dict] = []
        
        # ✅ BUG D FIX: per-desa dengan flag counted
        self.arrived_by_desa: Dict[str, int] = defaultdict(int)
        self.moving_by_desa: Dict[str, int] = defaultdict(int)
        self.waiting_by_desa: Dict[str, int] = defaultdict(int)
    
    def run(self) -> ABMResults:
        """Jalankan simulasi — GPU-accelerated if available."""
        current_time = 0.0
        n_steps = int(self.duration_s / self.dt_s)
        n_agents = len(self.agents)
        
        use_gpu_batch = (batch_update_agents_gpu is not None and n_agents > 50)
        
        logger.info(f"Running ABM: {n_agents} agents, "
                    f"{n_steps} steps ({self.duration_s/60:.0f} min), "
                    f"GPU batch: {'YES' if use_gpu_batch else 'NO'}")
        
        # Pre-compute routes untuk semua agent
        self._precompute_routes()
        
        if use_gpu_batch:
            # ── GPU BATCH MODE ──
            # Pre-build numpy arrays for vectorized operations
            agent_dists = np.zeros(n_agents, dtype=np.float32)
            agent_speeds = np.array([ag.speed_mps for ag in self.agents], dtype=np.float32)
            agent_path_lengths = np.array(
                [self.router.path_distance_m(ag.path) if ag.path else 0 for ag in self.agents],
                dtype=np.float32
            )
            # Status: 0=waiting, 1=moving, 2=arrived, 3=stranded
            status_map = {"waiting": 0, "moving": 1, "arrived": 2, "stranded": 3}
            rev_status = {0: "waiting", 1: "moving", 2: "arrived", 3: "stranded"}
            agent_statuses = np.array([status_map.get(ag.status, 0) for ag in self.agents], dtype=np.int32)
            agent_delays = np.array([ag.response_delay for ag in self.agents], dtype=np.float32)
            agent_wave_arr = np.array(
                [getattr(ag, 'wave_arrival_min', float('inf')) or float('inf') for ag in self.agents],
                dtype=np.float32
            )
            
            for step in range(n_steps):
                current_time = step * self.dt_s
                
                # ✅ GPU VECTORIZED UPDATE
                agent_statuses, agent_dists, progress = batch_update_agents_gpu(
                    agent_dists, agent_speeds, agent_path_lengths,
                    agent_statuses, agent_delays, agent_wave_arr,
                    current_time, self.warning_time_s, self.dt_s
                )
                
                # Sync back to agent objects (for timeline/results)
                if step % 5 == 0 or step == n_steps - 1:
                    for idx, ag in enumerate(self.agents):
                        new_status = rev_status.get(int(agent_statuses[idx]), ag.status)
                        if new_status == "arrived" and ag.status != "arrived":
                            ag.arrival_time = current_time
                            if not ag.counted:
                                self.arrived_by_desa[ag.desa_name] += ag.population
                                ag.counted = True
                        ag.status = new_status
                        ag.dist_covered_m = float(agent_dists[idx])
                    
                    self._record_timeline(current_time, n_steps, step)
        else:
            # ── CPU FALLBACK MODE ──
            for step in range(n_steps):
                current_time = step * self.dt_s
                
                moving_now = defaultdict(int)
                waiting_now = defaultdict(int)
                
                for agent in self.agents:
                    self._update_agent(agent, current_time)
                    
                    if agent.status == "moving":
                        moving_now[agent.desa_name] += agent.population
                    elif agent.status == "waiting":
                        waiting_now[agent.desa_name] += agent.population
                
                if step % 5 == 0 or step == n_steps - 1:
                    self._record_timeline(current_time, n_steps, step)
        
        return self._build_results()
    
    def _record_timeline(self, current_time: float, n_steps: int, step: int):
        """Record timeline snapshot for animation."""
        total_arrived = sum(ag.population for ag in self.agents if ag.status == "arrived")
        total_moving = sum(ag.population for ag in self.agents if ag.status == "moving")
        total_waiting = sum(ag.population for ag in self.agents if ag.status == "waiting")
        total_stranded = sum(ag.population for ag in self.agents if ag.status == "stranded")
        total_pop = sum(ag.population for ag in self.agents)
        
        # Collect agent positions for animation
        positions = []
        for ag in self.agents:
            if ag.status in ("arrived", "stranded", "moving"):
                lat, lon = ag.home_lat, ag.home_lon
                if ag.path and ag.current_path_idx < len(ag.path):
                    nid = ag.path[ag.current_path_idx]
                    if nid in self.graph.nodes:
                        lat, lon = self.graph.nodes[nid]
                if ag.status == "arrived" and ag.shelter_id is not None:
                    for sh in self.shelters:
                        if sh.id == ag.shelter_id:
                            lat, lon = sh.lat, sh.lon
                            break
                positions.append({
                    "id": ag.id, "lat": lat, "lon": lon,
                    "status": ag.status, "pop": ag.population,
                    "transport_mode": ag.transport_mode
                })
        
        self.timeline.append({
            'time_min': current_time / 60.0,
            'arrived': total_arrived,
            'moving': total_moving,
            'waiting': total_waiting,
            'stranded': total_stranded,
            'arrival_pct': 100.0 * total_arrived / max(total_pop, 1),
            'positions': positions[:300]
        })
    
    def _precompute_routes(self):
        """Cari route ke shelter TERJAUH dari pantai untuk semua agent."""
        logger.info("Pre-computing evacuation routes (strategy: farthest from coast)...")
        
        for agent in self.agents:
            # Hitung tsunami deadline berdasarkan wave arrival
            tsunami_deadline_s = float('inf')
            wave_t = getattr(agent, 'wave_arrival_min', None)
            if wave_t is not None and wave_t < float('inf'):
                tsunami_deadline_s = (wave_t * 60.0) - 60.0  # Safety margin 60s
            
            # Gunakan find_safest_shelter (terjauh dari pantai)
            shelter, path, cost = self.router.find_safest_shelter(
                agent.home_node, self.shelters,
                tsunami_deadline_s=tsunami_deadline_s,
                agent_speed_mps=agent.effective_speed_ms
            )
            
            if shelter is None or not path:
                agent.status = "stranded"
                continue
            
            agent.path = path
            agent.shelter_id = shelter.id
            agent.target_tes_name = shelter.name
            # Reserve shelter capacity
            shelter.current_occupancy += agent.population
    
    def _update_agent(self, agent: Agent, current_time: float):
        """Update state satu agent — transport mode + slope + friction."""
        if agent.status in ("arrived", "stranded"):
            return
        
        current_time_min = current_time / 60.0
        
        # Check wave arrival — agent caught by tsunami
        wave_t = getattr(agent, 'wave_arrival_min', None)
        if wave_t is not None and agent.status != "arrived" and current_time_min >= wave_t:
            agent.status = "stranded"
            return
        
        # Phase 1: Waiting
        if agent.status == "waiting":
            if current_time >= self.warning_time_s + agent.response_delay:
                agent.status = "moving"
                agent.start_time = current_time
            else:
                return
        
        # Phase 2: Moving
        if agent.status == "moving":
            # Update slope dari graph elevation data
            current_lat, current_lon = agent.home_lat, agent.home_lon
            if agent.path and agent.current_path_idx < len(agent.path):
                nid = agent.path[agent.current_path_idx]
                if nid in self.graph.nodes:
                    current_lat, current_lon = self.graph.nodes[nid]
                
                # Hitung slope dari elevasi node saat ini dan berikutnya
                if agent.current_path_idx + 1 < len(agent.path):
                    next_nid = agent.path[agent.current_path_idx + 1]
                    e1 = self.graph.node_elev.get(nid, 0.0)
                    e2 = self.graph.node_elev.get(next_nid, 0.0)
                    n1 = self.graph.nodes.get(nid, (0, 0))
                    n2 = self.graph.nodes.get(next_nid, (0, 0))
                    dist = haversine_m(n1[0], n1[1], n2[0], n2[1])
                    if dist > 1.0:
                        slope_pct = abs(e2 - e1) / dist * 100.0
                        agent.slope_deg = math.degrees(math.atan(slope_pct / 100.0))
            
            # Effective speed = base_speed × friction × slope_factor
            # Lalu modulasi dengan tsunami panic level
            base_effective = agent.effective_speed_ms
            
            # Tambahan: panic modifier dari tsunami proximity
            speed_info = self.speed_calc.calculate_speed(
                current_lat, current_lon, current_time_min, base_effective
            )
            effective_speed = speed_info['speed_mps']
            
            step_distance = effective_speed * self.dt_s
            agent.dist_covered_m += step_distance
            
            total_path_dist = self.router.path_distance_m(agent.path)
            
            if agent.dist_covered_m >= total_path_dist:
                agent.status = "arrived"
                agent.arrival_time = current_time
                
                # ✅ BUG D FIX: Hanya hitung SEKALI
                if not agent.counted:
                    self.arrived_by_desa[agent.desa_name] += agent.population
                    agent.counted = True
            else:
                # Update current position (untuk tracking)
                agent.current_path_idx = self._get_current_node_idx(
                    agent.path, agent.dist_covered_m
                )
                
                # Dynamic flood check at current position
                if self.flood_checker and agent.current_path_idx < len(agent.path):
                    node_id = agent.path[agent.current_path_idx]
                    if node_id in self.graph.nodes:
                        nlat, nlon = self.graph.nodes[node_id]
                        if self.flood_checker(nlat, nlon, current_time_min):
                            agent.status = "stranded"
    
    def _get_current_node_idx(self, path: List[int], 
                                 dist_covered: float) -> int:
        """Tentukan node index saat ini berdasarkan jarak yang ditempuh."""
        if len(path) < 2:
            return 0
        
        accumulated = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            meta = self.graph.edge_meta.get((u, v))
            seg_dist = meta['distance_m'] if meta else 0
            
            if accumulated + seg_dist >= dist_covered:
                return i
            accumulated += seg_dist
        
        return len(path) - 1
    
    def _build_results(self) -> ABMResults:
        """Kompilasi hasil akhir."""
        total_agents = len(self.agents)
        total_pop = sum(ag.population for ag in self.agents)
        arrived = sum(ag.population for ag in self.agents if ag.status == "arrived")
        stranded = sum(ag.population for ag in self.agents if ag.status == "stranded")
        
        # Per-desa stats
        per_desa = defaultdict(lambda: {
            'total': 0, 'arrived': 0, 'stranded': 0, 'moving': 0,
            'avg_evacuation_time_min': 0.0
        })
        
        arrival_times_by_desa = defaultdict(list)
        
        for ag in self.agents:
            d = per_desa[ag.desa_name]
            d['total'] += ag.population
            if ag.status == "arrived":
                d['arrived'] += ag.population
                if ag.arrival_time is not None and ag.start_time >= 0:
                    evac_time = (ag.arrival_time - ag.start_time) / 60.0
                    arrival_times_by_desa[ag.desa_name].append(evac_time)
            elif ag.status == "stranded":
                d['stranded'] += ag.population
            elif ag.status == "moving":
                d['moving'] += ag.population
        
        for desa_name, times in arrival_times_by_desa.items():
            if times:
                per_desa[desa_name]['avg_evacuation_time_min'] = sum(times) / len(times)
        
        # Per-shelter stats
        per_shelter = {}
        for sh in self.shelters:
            per_shelter[sh.id] = {
                'name': sh.name,
                'lat': sh.lat,
                'lon': sh.lon,
                'capacity': sh.capacity,
                'occupancy': sh.current_occupancy,
                'usage_pct': 100.0 * sh.current_occupancy / max(sh.capacity, 1),
                'elevation_m': sh.elevation
            }
        
        # Routes GeoJSON
        routes_features = []
        for ag in self.agents:
            if not ag.path or ag.status == "stranded":
                continue
            coords = self.router.path_to_coords(ag.path)
            if len(coords) < 2:
                continue
            routes_features.append(coords_to_geojson_linestring(
                coords,
                properties={
                    'agent_id': ag.id,
                    'desa': ag.desa_name,
                    'shelter_id': ag.shelter_id,
                    'status': ag.status,
                    'population': ag.population
                }
            ))
        
        routes_geojson = features_to_feature_collection(routes_features)
        
        # Heatmap density grid
        heatmap = self._generate_heatmap()
        
        stats = {
            'total_agents': total_agents,
            'total_population': total_pop,
            'arrival_rate_pct': 100.0 * arrived / max(total_pop, 1),
            'stranded_rate_pct': 100.0 * stranded / max(total_pop, 1),
            'avg_evacuation_time_min': self._avg_evac_time(),
            'avg_arrival_time_min': self._avg_evac_time(),
            'warning_time_min': self.warning_time_s / 60.0,
            'simulation_duration_min': self.duration_s / 60.0,
            'heatmap': heatmap
        }
        
        return ABMResults(
            total_agents=total_agents,
            total_population=total_pop,
            arrived=arrived,
            stranded=stranded,
            evacuation_timeline=self.timeline,
            per_desa_stats=dict(per_desa),
            per_shelter_stats=per_shelter,
            routes_geojson=routes_geojson,
            simulation_duration_min=self.duration_s / 60.0,
            statistics=stats
        )
    
    def _avg_evac_time(self) -> float:
        times = [(ag.arrival_time - ag.start_time) / 60.0 
                 for ag in self.agents 
                 if ag.status == "arrived" and ag.arrival_time is not None]
        return sum(times) / len(times) if times else 0.0
    
    def _generate_heatmap(self) -> List[Dict]:
        """Generate heatmap density grid dari posisi agent."""
        heatmap_grid: Dict[tuple, int] = {}
        for ag in self.agents:
            if ag.path:
                for nid in ag.path:
                    if nid in self.graph.nodes:
                        lat, lon = self.graph.nodes[nid]
                        cell_key = (round(lat, 3), round(lon, 3))
                        heatmap_grid[cell_key] = heatmap_grid.get(cell_key, 0) + ag.population
        
        return [
            {'lat': k[0], 'lon': k[1], 'density': v}
            for k, v in sorted(heatmap_grid.items(), key=lambda x: -x[1])[:500]
        ]


# ============================================================================
# MAIN SOLVER
# ============================================================================

class EvacuationABMSolver:
    """
    Main entry point untuk evacuation ABM simulation.
    
    Usage:
        solver = EvacuationABMSolver(vektor_dir='./Vektor', dem_mgr=dem)
        solver.build_caches()
        solver.set_swe_results(swe_output)  # optional
        result = solver.run_abm({'warning_time_min': 5, 'duration_min': 120})
    """
    
    def __init__(self, vektor_dir: str, dem_mgr=None):
        self.vektor_dir = vektor_dir
        self.dem_mgr = dem_mgr
        
        self.cache = DataCache(vektor_dir, dem_mgr)
        self.graph = EvacuationGraph(self.cache, dem_mgr)
        self.router: Optional[EvacuationRouter] = None
        self.swe_results: Optional[Dict] = None
        
        # Coastline geometry — untuk distance-to-coast calculation
        self._coastline_geom = None
        self._load_coastline()
    
    def _load_coastline(self):
        """Load coastline shapefile untuk distance-to-coast calculation."""
        if not GEOPANDAS_AVAILABLE or not SHAPELY_AVAILABLE:
            return
        
        keywords = ['pantai', 'coastline', 'coast']
        for fname in os.listdir(self.vektor_dir):
            if not fname.lower().endswith('.shp'):
                continue
            if not any(k in fname.lower() for k in keywords):
                continue
            
            try:
                gdf = gpd.read_file(os.path.join(self.vektor_dir, fname))
                if gdf.crs is None:
                    gdf.set_crs(epsg=4326, inplace=True)
                else:
                    gdf = gdf.to_crs(epsg=4326)
                
                self._coastline_geom = gdf.geometry.unary_union
                logger.info(f"Coastline loaded from {fname}")
                return
            except Exception as e:
                logger.warning(f"Failed to load coastline {fname}: {e}")
        
        logger.warning("No coastline shapefile found, distance-to-coast disabled")
    
    def _distance_to_coast_km(self, lat: float, lon: float) -> float:
        """Hitung jarak dari titik ke garis pantai (km)."""
        if self._coastline_geom is None or not SHAPELY_AVAILABLE:
            return 0.0
        try:
            point = Point(lon, lat)
            dist_deg = point.distance(self._coastline_geom)
            # Approx: 1 degree ≈ 111.32 km
            return dist_deg * 111.32
        except Exception:
            return 0.0
    
    def build_caches(self):
        """Build data cache dan graph."""
        self.cache.build_all()
        self.graph.build_evacuation_graph()  # ✅ BUG B FIX
        self.router = EvacuationRouter(self.graph)
        
        # Map shelter ke nearest node + hitung distance_to_coast
        for shelter in self.cache.shelters:
            shelter.node_id = self.graph.nearest_node(shelter.lat, shelter.lon)
            shelter.distance_to_coast_km = self._distance_to_coast_km(shelter.lat, shelter.lon)
    
    def set_swe_results(self, swe_output: Dict):
        """
        Integrate SWE tsunami flood data with grid-based lookup.
        Supports: wave_frames + grid_info (from swe_solver) AND flood_polygons.
        """
        if not swe_output or not isinstance(swe_output, dict):
            return
        self.swe_results = swe_output
        self._flood_grids = {}       # t_min -> set((j, i))
        self._wave_arrival = {}      # (j, i) -> t_arrival_min
        self._inundation_kdtree = None

        # ── Normalize grid_info from SWE format ──
        raw_gi = swe_output.get('grid_info', {})
        lons = raw_gi.get('lons', [])
        lats = raw_gi.get('lats', [])
        shape = raw_gi.get('shape', [])
        self._grid_meta = {
            'lat_min': min(lats) if lats else raw_gi.get('lat_min', 0),
            'lat_max': max(lats) if lats else raw_gi.get('lat_max', 0),
            'lon_min': min(lons) if lons else raw_gi.get('lon_min', 0),
            'lon_max': max(lons) if lons else raw_gi.get('lon_max', 0),
            'ny': shape[0] if len(shape) >= 2 else raw_gi.get('ny', 1),
            'nx': shape[1] if len(shape) >= 2 else raw_gi.get('nx', 1),
        }
        logger.info(f"Grid meta normalized: {self._grid_meta}")

        FLOOD_THRESHOLD_M = 0.1

        # ── Parse wave_frames — GPU accelerated if available ──
        wave_frames = swe_output.get('wave_frames', [])
        grid_meta = self._grid_meta
        if wave_frames and grid_meta:
            ny = grid_meta.get('ny', 1)
            nx = grid_meta.get('nx', 1)
            if ny >= 2 and nx >= 2:
                if parse_wave_frames_gpu is not None:
                    # ✅ GPU-ACCELERATED: CuPy vectorized parsing
                    self._flood_grids, self._wave_arrival = parse_wave_frames_gpu(
                        wave_frames, ny, nx, FLOOD_THRESHOLD_M
                    )
                    logger.info(f"SWE flood parsing: GPU-accelerated ({ny}x{nx} grid)")
                else:
                    # Fallback: CPU parsing
                    for frame in wave_frames:
                        t_min = frame.get('t_min', 0) if isinstance(frame, dict) else 0
                        eta_flat = frame.get('eta_flat', []) if isinstance(frame, dict) else frame
                        if not eta_flat:
                            continue
                        flooded = set()
                        for idx, h in enumerate(eta_flat):
                            if abs(h) < FLOOD_THRESHOLD_M:
                                continue
                            j, i = idx // nx, idx % nx
                            flooded.add((j, i))
                            if (j, i) not in self._wave_arrival:
                                self._wave_arrival[(j, i)] = t_min
                        self._flood_grids[t_min] = flooded
                    logger.info(f"SWE grid integration (CPU): {len(self._flood_grids)} frames, "
                                f"{len(self._wave_arrival)} wave arrival cells")

        # ── Build KDTree from inundation points ──
        inundation_gj = swe_output.get('inundation_geojson', {})
        features = inundation_gj.get('features', [])
        if not features and self._flood_grids and self._grid_meta:
            gm = self._grid_meta
            lat_min, lat_max = gm.get('lat_min', 0), gm.get('lat_max', 0)
            lon_min, lon_max = gm.get('lon_min', 0), gm.get('lon_max', 0)
            ny, nx = gm.get('ny', 1), gm.get('nx', 1)
            all_flooded = set()
            for cells in self._flood_grids.values():
                all_flooded.update(cells)
            features = []
            for (j, i) in all_flooded:
                glat = lat_min + j / max(ny - 1, 1) * (lat_max - lat_min)
                glon = lon_min + i / max(nx - 1, 1) * (lon_max - lon_min)
                features.append({"geometry": {"coordinates": [glon, glat], "type": "Point"}})

        if features:
            try:
                from scipy.spatial import cKDTree
                pts = [[f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0]] for f in features]
                if pts:
                    self._inundation_kdtree = cKDTree(pts)
                    logger.info(f"Inundation KDTree: {len(pts)} points")
            except Exception as e:
                logger.warning(f"KDTree build failed: {e}")

        # ── Also pass flood_polygons to router ──
        flood_polygons = swe_output.get('flood_polygons', [])
        if flood_polygons and self.router:
            self.router.set_flood_data(flood_polygons)

    def _is_flooded(self, lat: float, lon: float, t_min: float = 0) -> bool:
        """O(1) grid-based flood check at position (lat, lon) at time t_min."""
        gm = getattr(self, '_grid_meta', {})
        flood_grids = getattr(self, '_flood_grids', {})
        if not gm or not flood_grids:
            return False
        lat_min, lat_max = gm.get('lat_min', 0), gm.get('lat_max', 0)
        lon_min, lon_max = gm.get('lon_min', 0), gm.get('lon_max', 0)
        ny, nx = gm.get('ny', 1), gm.get('nx', 1)
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            return False
        j = int((lat - lat_min) / max(lat_max - lat_min, 1e-9) * (ny - 1))
        i = int((lon - lon_min) / max(lon_max - lon_min, 1e-9) * (nx - 1))
        j, i = max(0, min(ny - 1, j)), max(0, min(nx - 1, i))
        avail = sorted([t for t in flood_grids if t <= t_min], reverse=True)
        if not avail:
            return False
        return (j, i) in flood_grids[avail[0]]

    def _wave_arrival_at(self, lat: float, lon: float) -> Optional[float]:
        """Wave arrival time (minutes) at position using grid lookup."""
        gm = getattr(self, '_grid_meta', {})
        wave_arr = getattr(self, '_wave_arrival', {})
        if not gm or not wave_arr:
            return None
        lat_min, lat_max = gm.get('lat_min', 0), gm.get('lat_max', 0)
        lon_min, lon_max = gm.get('lon_min', 0), gm.get('lon_max', 0)
        ny, nx = gm.get('ny', 1), gm.get('nx', 1)
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            return None
        j = int((lat - lat_min) / max(lat_max - lat_min, 1e-9) * (ny - 1))
        i = int((lon - lon_min) / max(lon_max - lon_min, 1e-9) * (nx - 1))
        j, i = max(0, min(ny - 1, j)), max(0, min(nx - 1, i))
        return wave_arr.get((j, i))
    
    def run_abm(self, body: Dict) -> Dict:
        """
        Jalankan ABM simulation.
        
        Args:
            body: {
                'warning_time_min': 5.0,
                'duration_min': 120.0,
                'dt_min': 1.0,
                'agents_per_desa': 50,
                'panic_factor': 0.5
            }
        
        Returns:
            Dict hasil simulasi (JSON-serializable)
        """
        if self.router is None:
            raise RuntimeError("Call build_caches() first")
        
        warning_time = float(body.get('warning_time_min', 5.0))
        duration = float(body.get('duration_min', 120.0))
        # ── Referensi ABM Revisi: Time step 5 detik = 0.0833 menit ──
        dt = float(body.get('dt_min', 5.0 / 60.0))  # Default 5 detik
        agents_per_desa = int(body.get('agents_per_desa', 50))
        panic_factor = float(body.get('panic_factor', 0.5))
        
        # Generate agents dengan modal split
        agents = self._generate_agents(agents_per_desa, panic_factor)
        
        if not agents:
            return {
                'error': 'No agents generated. Check desa data and graph coverage.',
                'total_agents': 0
            }
        
        # Run simulator with flood awareness
        has_flood = bool(getattr(self, '_flood_grids', {}))
        simulator = _ABMSimulator(
            graph=self.graph,
            router=self.router,
            agents=agents,
            shelters=self.cache.shelters,
            warning_time_min=warning_time,
            duration_min=duration,
            dt_min=dt,
            flood_checker=self._is_flooded if has_flood else None,
            wave_arrival_func=self._wave_arrival_at if has_flood else None
        )
        
        results = simulator.run()
        
        # Build frames for frontend animation (ABMFrame format)
        frames = []
        for snap in results.evacuation_timeline:
            agents_data = []
            for p in snap.get('positions', []):
                agents_data.append({
                    'id': str(p['id']),
                    'lat': p['lat'],
                    'lon': p['lon'],
                    'status': 'safe' if p['status'] == 'arrived' else p['status'],
                    'transport_mode': p.get('transport_mode', 'foot'),
                })
            frames.append({
                'time_min': snap['time_min'],
                'agents': agents_data,
            })
        
        total_cap = sum(s.capacity for s in self.cache.shelters)
        total_occ = sum(s.current_occupancy for s in self.cache.shelters)
        tes_details = {}
        for s in self.cache.shelters:
            tes_details[str(s.id)] = {
                'name': s.name,
                'current': s.current_occupancy,
                'max': s.capacity,
                'ratio': s.current_occupancy / max(s.capacity, 1),
                'distance_to_coast_km': getattr(s, 'distance_to_coast_km', 0.0),
            }
        
        tes_capacity = {
            'total_capacity': total_cap,
            'total_occupied': total_occ,
            'utilization_rate': (total_occ / max(1, total_cap)) * 100 if total_cap else 0,
            'tes_details': tes_details
        }
        
        # ── Referensi ABM Revisi: Per-Transport Mode Statistics ──
        transport_stats = {}
        for mode in ['foot', 'motor', 'car']:
            mode_agents = [a for a in agents if a.transport_mode == mode]
            mode_arrived = [a for a in mode_agents if a.status == 'arrived']
            mode_times = [(a.arrival_time - a.start_time) / 60.0 
                         for a in mode_arrived if a.arrival_time is not None and a.start_time >= 0]
            
            mode_name = {'foot': 'Pejalan Kaki', 'motor': 'Sepeda Motor', 'car': 'Mobil'}[mode]
            transport_stats[mode] = {
                'name': mode_name,
                'total': len(mode_agents),
                'arrived': len(mode_arrived),
                'population': sum(a.population for a in mode_agents),
                'arrived_population': sum(a.population for a in mode_arrived),
                'avg_time_min': sum(mode_times) / len(mode_times) if mode_times else 0,
                'min_time_min': min(mode_times) if mode_times else 0,
                'max_time_min': max(mode_times) if mode_times else 0,
                'base_speed_ms': TRANSPORT_SPEEDS[mode],
            }
        
        # ── Referensi ABM Revisi: Hazard Zone Analysis ──
        hazard_agents = [a for a in agents if a.in_hazard_zone]
        hazard_arrived = [a for a in hazard_agents if a.status == 'arrived']
        hazard_pop = sum(a.population for a in hazard_agents)
        hazard_safe_pop = sum(a.population for a in hazard_arrived)
        
        # ── Referensi ABM Revisi: Safety Analysis (sebelum tsunami) ──
        tsunami_arrival_s = float('inf')
        if has_flood and self.swe_results:
            stats_swe = self.swe_results.get('statistics', {})
            tsunami_arrival_s = float(stats_swe.get('arrival_time_min', float('inf'))) * 60.0
        
        safe_before_tsunami = sum(
            a.population for a in agents 
            if a.status == 'arrived' and a.arrival_time is not None 
            and a.arrival_time < (tsunami_arrival_s - 60)  # Safety margin 60s
        )
        
        rerouting_count = 0
        for ag in agents:
            if ag.shelter_id is not None:
                nearest = min(self.cache.shelters, key=lambda s: haversine_m(ag.home_lat, ag.home_lon, s.lat, s.lon) if getattr(ag, 'home_lat', None) else 0)
                if nearest.id != ag.shelter_id:
                    rerouting_count += 1
        
        return {
            'total_agents': results.total_agents,
            'total_population': results.total_population,
            'safe_count': results.arrived,
            'trapped_count': results.stranded,
            'avg_evacuation_time_min': results.statistics.get('avg_arrival_time_min', 0),
            'arrived': results.arrived,
            'stranded': results.stranded,
            'frames': frames,
            'timeline': results.evacuation_timeline,
            'per_desa': results.per_desa_stats,
            'per_shelter': results.per_shelter_stats,
            'routes_geojson': results.routes_geojson,
            'statistics': {
                **results.statistics, 
                'swe_integrated': has_flood,
                'tes_capacity': tes_capacity,
                'tes_selection_strategy': 'farthest_from_coast',
                'rerouting': rerouting_count,
                'safe': results.arrived,
                'stranded': results.stranded,
                'affected': results.stranded,
                'time_step_seconds': dt * 60.0,
                # ── Transport Mode Breakdown ──
                'transport_mode_stats': transport_stats,
                'modal_split': {k: f"{v*100:.0f}%" for k, v in MODAL_SPLIT.items()},
                # ── Hazard Zone Analysis ──
                'hazard_zone': {
                    'agents_in_hazard': len(hazard_agents),
                    'population_in_hazard': hazard_pop,
                    'agents_safe': len(hazard_arrived),
                    'population_safe': hazard_safe_pop,
                    'hazard_evacuation_rate': (hazard_safe_pop / max(hazard_pop, 1)) * 100,
                },
                # ── Safety Before Tsunami ──
                'safety_analysis': {
                    'tsunami_arrival_s': tsunami_arrival_s,
                    'safe_before_tsunami_pop': safe_before_tsunami,
                    'safe_before_tsunami_pct': (safe_before_tsunami / max(results.total_population, 1)) * 100,
                    'safety_margin_s': 60,
                },
            }
        }
    
    def _generate_agents(self, agents_per_desa: int, 
                           panic_factor: float) -> List[Agent]:
        """Generate agents — modal split + hazard zone awareness + distance to coast."""
        import random
        agents = []
        agent_id = 0
        
        has_kdtree = getattr(self, '_inundation_kdtree', None) is not None
        has_swe = bool(self.swe_results)
        
        # Modal split modes dan probabilities
        transport_modes = list(MODAL_SPLIT.keys())
        transport_probs = list(MODAL_SPLIT.values())
        
        # SWE statistics untuk hazard assessment
        tsunami_arrival_s = float('inf')
        max_runup_m = 5.0
        if has_swe:
            stats = self.swe_results.get('statistics', {})
            tsunami_arrival_s = float(stats.get('arrival_time_min', float('inf'))) * 60.0
            max_runup_m = float(self.swe_results.get('runup_m', 5.0))
        
        for desa in self.cache.desa:
            if desa['population'] <= 0:
                continue
            
            dlat = desa['centroid_lat']
            dlon = desa['centroid_lon']
            
            # ── Filter: only generate agents for desa in/near inundation zone ──
            is_affected = False
            flood_depth_at_desa = 0.0
            
            if has_kdtree:
                dist, idx = self._inundation_kdtree.query([dlat, dlon], distance_upper_bound=0.008)
                is_affected = (dist != float('inf'))
                if is_affected and hasattr(self, '_inundation_depths') and idx < len(self._inundation_depths):
                    flood_depth_at_desa = self._inundation_depths[idx]
            if not is_affected and self.dem_mgr:
                try:
                    elev, _ = self.dem_mgr.query(dlon, dlat)
                    if elev is not None:
                        runup = max_runup_m
                        is_affected = float(elev) <= runup + 3.0
                except Exception:
                    pass
            if not is_affected and not has_kdtree and not has_swe:
                is_affected = True  # No inundation data → include all
            
            if not is_affected:
                continue
            
            # Hitung distance to coast untuk desa ini
            desa_coast_dist = self._distance_to_coast_km(dlat, dlon)
            
            # Klasifikasi hazard risk level
            def classify_risk(coast_dist_km: float, flood_d: float) -> str:
                if flood_d >= 3.0 or coast_dist_km < 0.5:
                    return 'EKSTREM'
                elif flood_d >= 1.5 or coast_dist_km < 1.0:
                    return 'TINGGI'
                elif flood_d >= 0.5 or coast_dist_km < 2.0:
                    return 'SEDANG'
                elif flood_d > 0 or coast_dist_km < 3.0:
                    return 'RENDAH'
                else:
                    return 'AMAN'
            
            risk_level = classify_risk(desa_coast_dist, flood_depth_at_desa)
            
            # Populasi per agent
            n_agents = min(agents_per_desa, desa['population'])
            if n_agents == 0:
                continue
            pop_per_agent = max(1, desa['population'] // n_agents)
            
            # Nearest node dari centroid desa
            home_node = self.graph.nearest_node(dlat, dlon)
            if home_node is None:
                logger.warning(f"No graph node near desa {desa['name']}")
                continue
            
            # Wave arrival time for this desa
            wave_t = self._wave_arrival_at(dlat, dlon)
            
            for i in range(n_agents):
                home_lat = dlat + random.gauss(0, 0.0005)
                home_lon = dlon + random.gauss(0, 0.0005)
                
                delay = random.uniform(*RESPONSE_DELAY_RANGE) * 60.0
                
                # ── Modal Split: random pilih transport mode ──
                transport_mode = random.choices(transport_modes, weights=transport_probs, k=1)[0]
                base_speed = TRANSPORT_SPEEDS[transport_mode]
                
                # Slight speed variation per individual
                speed_variation = random.uniform(0.85, 1.15)
                
                ag = Agent(
                    id=agent_id,
                    home_lat=home_lat,
                    home_lon=home_lon,
                    home_node=home_node,
                    desa_name=desa['name'],
                    population=pop_per_agent,
                    status="waiting",
                    counted=False,
                    response_delay=delay,
                    speed_mps=base_speed * speed_variation,
                    # ── Referensi ABM Revisi fields ──
                    transport_mode=transport_mode,
                    weight=pop_per_agent,
                    distance_to_coast_km=desa_coast_dist,
                    in_hazard_zone=flood_depth_at_desa > 0 or desa_coast_dist < 2.0,
                    flood_depth_m=flood_depth_at_desa,
                    hazard_risk_level=risk_level,
                )
                # Store wave arrival for stranding check
                ag.wave_arrival_min = wave_t
                agents.append(ag)
                agent_id += 1
        
        # Log modal split distribution
        foot_count = sum(1 for a in agents if a.transport_mode == 'foot')
        motor_count = sum(1 for a in agents if a.transport_mode == 'motor')
        car_count = sum(1 for a in agents if a.transport_mode == 'car')
        hazard_count = sum(1 for a in agents if a.in_hazard_zone)
        
        logger.info(f"Generated {len(agents)} agents from {len(self.cache.desa)} desa "
                     f"(inundation filter: KDTree={'yes' if has_kdtree else 'no'}, SWE={'yes' if has_swe else 'no'})")
        logger.info(f"  Modal split: foot={foot_count} ({foot_count/max(len(agents),1)*100:.0f}%), "
                     f"motor={motor_count} ({motor_count/max(len(agents),1)*100:.0f}%), "
                     f"car={car_count} ({car_count/max(len(agents),1)*100:.0f}%)")
        logger.info(f"  Hazard zone: {hazard_count} agents ({hazard_count/max(len(agents),1)*100:.0f}%)")
        return agents


# ============================================================================
# MODULE INFO
# ============================================================================

__version__ = "2.0.0"
__all__ = [
    'EvacuationABMSolver',
    'EvacuationGraph',
    'EvacuationRouter',
    'DataCache',
    'Agent',
    'Shelter',
    'ABMResults',
    'SPEED_MAP',
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                         format='%(asctime)s [%(levelname)s] %(message)s')
    
    print("=" * 70)
    print("Evacuation ABM Solver v2.0.0 - Refactored")
    print("=" * 70)
    print("✅ BUG A FIXED: Import path (from spatial_utils)")
    print("✅ BUG B FIXED: Consistent naming (build_evacuation_graph)")
    print("✅ BUG C FIXED: defaultdict & heapq imports")
    print("✅ BUG D FIXED: arrived_by_desa no double-counting (counted flag)")
    print("✅ BUG E FIXED: Division by zero (safe_divide, calculate_slope_percent)")
    print("=" * 70)
    print(f"Geopandas: {'✅' if GEOPANDAS_AVAILABLE else '❌'}")
    print(f"OSMnx: {'✅' if OSMNX_AVAILABLE else '❌'}")
    print(f"Shapely: {'✅' if SHAPELY_AVAILABLE else '❌'}")