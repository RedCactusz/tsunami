"""
============================================================================
SPATIAL UTILITIES MODULE
============================================================================
Konsolidasi semua fungsi spasial yang digunakan oleh:
- server.py
- swe_solver.py
- evacuation_abm.py

Author: Kelompok 3 - Mini Project Komputasi Geospasial S2 Geomatika UGM
Version: 2.0.0 (Refactored)
============================================================================
"""

import math
import heapq
import json
import logging
from typing import List, Tuple, Dict, Optional, Callable, Any
from collections import defaultdict
import numpy as np

# Try importing geopandas (optional for shapefile support)
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# KONSTANTA GLOBAL
# ============================================================================
EARTH_RADIUS_M = 6_371_000.0      # Radius Bumi dalam meter
EARTH_RADIUS_KM = 6371.0           # Radius Bumi dalam kilometer
GRAVITY = 9.81                     # Percepatan gravitasi (m/s²)
DEG_TO_RAD = math.pi / 180.0
RAD_TO_DEG = 180.0 / math.pi

# WGS84 ellipsoid parameters
WGS84_A = 6378137.0                # Semi-major axis
WGS84_F = 1 / 298.257223563        # Flattening
WGS84_B = WGS84_A * (1 - WGS84_F)  # Semi-minor axis


# ============================================================================
# 1. DISTANCE & GEOMETRY CALCULATIONS
# ============================================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Menghitung jarak great-circle antara dua titik dalam METER.
    Menggunakan formula Haversine.
    
    Args:
        lat1, lon1: Koordinat titik pertama (derajat)
        lat2, lon2: Koordinat titik kedua (derajat)
    
    Returns:
        Jarak dalam meter
    """
    phi1 = lat1 * DEG_TO_RAD
    phi2 = lat2 * DEG_TO_RAD
    dphi = (lat2 - lat1) * DEG_TO_RAD
    dlambda = (lon2 - lon1) * DEG_TO_RAD
    
    a = (math.sin(dphi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_M * c


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Menghitung jarak great-circle dalam KILOMETER."""
    return haversine_m(lat1, lon1, lat2, lon2) / 1000.0


def haversine_vectorized(lat1: np.ndarray, lon1: np.ndarray, 
                          lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """
    Versi vectorized untuk array NumPy. Jauh lebih cepat untuk batch processing.
    
    Returns:
        Array jarak dalam meter
    """
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = (np.sin(dphi / 2) ** 2 + 
         np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return EARTH_RADIUS_M * c


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Menghitung bearing (arah) dari titik 1 ke titik 2 dalam derajat.
    0° = Utara, 90° = Timur, 180° = Selatan, 270° = Barat.
    """
    phi1 = lat1 * DEG_TO_RAD
    phi2 = lat2 * DEG_TO_RAD
    dlambda = (lon2 - lon1) * DEG_TO_RAD
    
    x = math.sin(dlambda) * math.cos(phi2)
    y = (math.cos(phi1) * math.sin(phi2) - 
         math.sin(phi1) * math.cos(phi2) * math.cos(dlambda))
    
    bearing = math.atan2(x, y) * RAD_TO_DEG
    return (bearing + 360) % 360


def destination_point(lat: float, lon: float, bearing: float, 
                       distance_m: float) -> Tuple[float, float]:
    """
    Menghitung titik tujuan dari titik awal dengan bearing dan jarak tertentu.
    
    Args:
        lat, lon: Titik awal (derajat)
        bearing: Arah (derajat, 0=Utara)
        distance_m: Jarak (meter)
    
    Returns:
        (lat_tujuan, lon_tujuan)
    """
    phi1 = lat * DEG_TO_RAD
    lambda1 = lon * DEG_TO_RAD
    theta = bearing * DEG_TO_RAD
    delta = distance_m / EARTH_RADIUS_M
    
    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + 
                     math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2)
    )
    
    return (phi2 * RAD_TO_DEG, lambda2 * RAD_TO_DEG)


def point_in_polygon(point: Tuple[float, float], 
                      polygon: List[Tuple[float, float]]) -> bool:
    """
    Algoritma Ray-Casting untuk menentukan apakah titik ada di dalam polygon.
    
    Args:
        point: (lon, lat) titik yang dicek
        polygon: List [(lon, lat), ...] vertex polygon
    
    Returns:
        True jika titik di dalam polygon
    """
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def polygon_area_m2(polygon: List[Tuple[float, float]]) -> float:
    """
    Menghitung luas polygon dalam meter persegi menggunakan formula Shoelace.
    Koordinat input dalam (lon, lat) derajat.
    """
    if len(polygon) < 3:
        return 0.0
    
    # Konversi ke meter menggunakan proyeksi lokal sederhana
    lat_avg = sum(p[1] for p in polygon) / len(polygon)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(lat_avg * DEG_TO_RAD)
    
    coords_m = [(p[0] * m_per_deg_lon, p[1] * m_per_deg_lat) for p in polygon]
    
    area = 0.0
    n = len(coords_m)
    for i in range(n):
        j = (i + 1) % n
        area += coords_m[i][0] * coords_m[j][1]
        area -= coords_m[j][0] * coords_m[i][1]
    
    return abs(area) / 2.0


def bbox_from_points(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """
    Menghitung bounding box dari list titik.
    
    Returns:
        (min_lon, min_lat, max_lon, max_lat)
    """
    if not points:
        return (0, 0, 0, 0)
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return (min(lons), min(lats), max(lons), max(lats))


def bbox_intersects(bbox1: Tuple[float, float, float, float],
                     bbox2: Tuple[float, float, float, float]) -> bool:
    """Cek apakah dua bounding box bersinggungan."""
    return not (bbox1[2] < bbox2[0] or bbox1[0] > bbox2[2] or
                bbox1[3] < bbox2[1] or bbox1[1] > bbox2[3])


# ============================================================================
# 2. GRID & INTERPOLATION
# ============================================================================

def create_grid(lon_min: float, lon_max: float, 
                 lat_min: float, lat_max: float, 
                 dx_deg: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Membuat grid regular untuk komputasi numerik.
    
    Returns:
        lons_1d, lats_1d, LON_2d, LAT_2d
    """
    lons = np.arange(lon_min, lon_max + dx_deg, dx_deg)
    lats = np.arange(lat_min, lat_max + dx_deg, dx_deg)
    LON, LAT = np.meshgrid(lons, lats)
    return lons, lats, LON, LAT


def bilinear_interpolation(x: float, y: float, 
                             x_grid: np.ndarray, y_grid: np.ndarray, 
                             z_grid: np.ndarray) -> float:
    """
    Interpolasi bilinear pada grid 2D.
    
    Args:
        x, y: Koordinat titik query
        x_grid: Array 1D koordinat x
        y_grid: Array 1D koordinat y
        z_grid: Array 2D nilai (shape: [len(y_grid), len(x_grid)])
    
    Returns:
        Nilai terinterpolasi, atau NaN jika di luar grid
    """
    if x < x_grid[0] or x > x_grid[-1] or y < y_grid[0] or y > y_grid[-1]:
        return float('nan')
    
    ix = np.searchsorted(x_grid, x) - 1
    iy = np.searchsorted(y_grid, y) - 1
    ix = max(0, min(ix, len(x_grid) - 2))
    iy = max(0, min(iy, len(y_grid) - 2))
    
    x1, x2 = x_grid[ix], x_grid[ix + 1]
    y1, y2 = y_grid[iy], y_grid[iy + 1]
    
    fx = (x - x1) / (x2 - x1) if x2 > x1 else 0
    fy = (y - y1) / (y2 - y1) if y2 > y1 else 0
    
    z11 = z_grid[iy, ix]
    z12 = z_grid[iy, ix + 1]
    z21 = z_grid[iy + 1, ix]
    z22 = z_grid[iy + 1, ix + 1]
    
    return (z11 * (1 - fx) * (1 - fy) + 
            z12 * fx * (1 - fy) + 
            z21 * (1 - fx) * fy + 
            z22 * fx * fy)


def nearest_neighbor_fill(grid: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Mengisi nilai NaN pada grid menggunakan nearest-neighbor.
    
    Args:
        grid: Array 2D dengan beberapa nilai NaN
        mask: Array 2D boolean (True = valid, False = NaN)
    
    Returns:
        Grid yang sudah diisi
    """
    try:
        from scipy.ndimage import distance_transform_edt
        _, (yi, xi) = distance_transform_edt(~mask, return_indices=True)
        return grid[yi, xi]
    except ImportError:
        # Fallback manual
        filled = grid.copy()
        ny, nx = grid.shape
        for i in range(ny):
            for j in range(nx):
                if not mask[i, j]:
                    for r in range(1, max(ny, nx)):
                        found = False
                        for di in range(-r, r + 1):
                            for dj in range(-r, r + 1):
                                ii, jj = i + di, j + dj
                                if 0 <= ii < ny and 0 <= jj < nx and mask[ii, jj]:
                                    filled[i, j] = grid[ii, jj]
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
        return filled


# ============================================================================
# 3. GRAPH & PATHFINDING ALGORITHMS
# ============================================================================

def dijkstra(graph: Dict[int, List[Tuple[int, float]]], 
              start: int, 
              end: Optional[int] = None,
              edge_filter: Optional[Callable[[int, int], bool]] = None,
              edge_penalty: Optional[Callable[[int, int], float]] = None
              ) -> Tuple[Dict[int, float], Dict[int, int]]:
    """
    Algoritma Dijkstra untuk shortest path.
    
    Args:
        graph: {node_id: [(neighbor_id, weight), ...]}
        start: Node awal
        end: Node tujuan (opsional, jika None akan cari ke semua node)
        edge_filter: Function(u, v) -> bool. Jika False, edge di-skip
        edge_penalty: Function(u, v) -> float. Multiplier untuk edge weight
    
    Returns:
        (distances_dict, predecessors_dict)
    """
    distances = {start: 0.0}
    predecessors = {}
    pq = [(0.0, start)]
    visited = set()
    
    while pq:
        current_dist, current = heapq.heappop(pq)
        
        if current in visited:
            continue
        visited.add(current)
        
        if end is not None and current == end:
            break
        
        for neighbor, weight in graph.get(current, []):
            if neighbor in visited:
                continue
            
            # Filter edge
            if edge_filter and not edge_filter(current, neighbor):
                continue
            
            # Apply penalty
            effective_weight = weight
            if edge_penalty:
                effective_weight *= edge_penalty(current, neighbor)
            
            new_dist = current_dist + effective_weight
            
            if neighbor not in distances or new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                predecessors[neighbor] = current
                heapq.heappush(pq, (new_dist, neighbor))
    
    return distances, predecessors


def astar(graph: Dict[int, List[Tuple[int, float]]], 
           start: int, 
           end: int,
           node_coords: Dict[int, Tuple[float, float]],
           edge_filter: Optional[Callable[[int, int], bool]] = None
           ) -> Tuple[List[int], float]:
    """
    Algoritma A* dengan Haversine heuristic.
    
    Args:
        graph: {node_id: [(neighbor_id, weight), ...]}
        start: Node awal
        end: Node tujuan
        node_coords: {node_id: (lat, lon)}
        edge_filter: Function(u, v) -> bool
    
    Returns:
        (path_list, total_cost). Path kosong jika tidak ada jalur.
    """
    def heuristic(n1: int, n2: int) -> float:
        c1 = node_coords.get(n1)
        c2 = node_coords.get(n2)
        if c1 is None or c2 is None:
            return 0.0
        return haversine_m(c1[0], c1[1], c2[0], c2[1])
    
    open_set = [(0.0, start)]
    came_from = {}
    g_score = {start: 0.0}
    f_score = {start: heuristic(start, end)}
    visited = set()
    
    while open_set:
        _, current = heapq.heappop(open_set)
        
        if current == end:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[end]
        
        if current in visited:
            continue
        visited.add(current)
        
        for neighbor, weight in graph.get(current, []):
            if neighbor in visited:
                continue
            if edge_filter and not edge_filter(current, neighbor):
                continue
            
            tentative_g = g_score[current] + weight
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, end)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    
    return [], float('inf')


def reconstruct_path(predecessors: Dict[int, int], 
                      start: int, end: int) -> List[int]:
    """Rekonstruksi path dari hasil Dijkstra."""
    if end not in predecessors and end != start:
        return []
    
    path = [end]
    current = end
    while current != start:
        if current not in predecessors:
            return []
        current = predecessors[current]
        path.append(current)
    
    path.reverse()
    return path


# ============================================================================
# 4. ELEVATION, SLOPE & TERRAIN ANALYSIS
# ============================================================================

def calculate_slope_percent(elev1: float, elev2: float, 
                              dist_m: float) -> float:
    """
    Menghitung kemiringan (slope) dalam persen.
    SAFE: Menangani division by zero (BUG E fix).
    
    Args:
        elev1, elev2: Elevasi dua titik (meter)
        dist_m: Jarak horizontal (meter)
    
    Returns:
        Slope dalam persen (absolute value)
    """
    if dist_m <= 0 or math.isnan(dist_m):
        return 0.0
    
    elev_diff = elev2 - elev1
    if math.isnan(elev_diff):
        return 0.0
    
    return abs(elev_diff / dist_m) * 100.0


def calculate_slope_degrees(elev1: float, elev2: float, 
                              dist_m: float) -> float:
    """Menghitung slope dalam derajat."""
    if dist_m <= 0:
        return 0.0
    elev_diff = elev2 - elev1
    return math.degrees(math.atan2(abs(elev_diff), dist_m))


def elevation_penalty(elevation: float, 
                       safe_threshold: float = 20.0,
                       max_penalty: float = 10.0) -> float:
    """
    Penalty untuk elevasi rendah (zona bahaya tsunami).
    Semakin rendah elevasi, semakin besar penalty.
    
    Args:
        elevation: Elevasi titik (meter)
        safe_threshold: Elevasi aman (meter), default 20m
        max_penalty: Penalty maksimum
    
    Returns:
        Penalty multiplier [1.0, max_penalty]
    """
    if elevation >= safe_threshold:
        return 1.0
    if elevation <= 0:
        return max_penalty
    
    ratio = 1.0 - (elevation / safe_threshold)
    return 1.0 + ratio * (max_penalty - 1.0)


def slope_penalty(slope_pct: float, max_slope: float = 40.0) -> float:
    """
    Penalty untuk slope curam.
    
    Args:
        slope_pct: Slope dalam persen
        max_slope: Slope maksimum (%) untuk penalty maksimal
    
    Returns:
        Penalty multiplier [1.0, 3.0]
    """
    if slope_pct <= 5.0:
        return 1.0
    if slope_pct >= max_slope:
        return 3.0
    
    ratio = (slope_pct - 5.0) / (max_slope - 5.0)
    return 1.0 + ratio * 2.0


# ============================================================================
# 5. TSUNAMI PHYSICS UTILITIES
# ============================================================================

def wave_speed(depth_m: float) -> float:
    """
    Kecepatan gelombang tsunami: c = sqrt(g * d).
    
    Args:
        depth_m: Kedalaman air (meter, positif)
    
    Returns:
        Kecepatan (m/s). 0 jika depth <= 0.
    """
    if depth_m <= 0 or math.isnan(depth_m):
        return 0.0
    return math.sqrt(GRAVITY * depth_m)


def abe_initial_height(magnitude: float) -> float:
    """
    Formula Abe (1979): H0 = 10^(0.5*Mw - 3.2).
    
    Returns:
        Tinggi gelombang awal (meter)
    """
    return 10.0 ** (0.5 * magnitude - 3.2)


def synolakis_runup(h_nearshore: float, 
                     beach_slope: float = 0.04, 
                     d_ref: float = 10.0) -> float:
    """
    Formula Synolakis (1987) untuk runup tsunami.
    R = 2.831 * sqrt(cot(beta)) * H^1.25 * d_ref^(-0.25)
    
    Args:
        h_nearshore: Tinggi gelombang di nearshore (meter)
        beach_slope: Slope pantai (default 0.04)
        d_ref: Reference depth (meter, default 10)
    
    Returns:
        Runup height (meter)
    """
    if beach_slope <= 0 or h_nearshore <= 0 or d_ref <= 0:
        return 0.0
    
    cot_beta = 1.0 / beach_slope
    return 2.831 * math.sqrt(cot_beta) * (h_nearshore ** 1.25) * (d_ref ** -0.25)


def geometric_spreading_decay(h0: float, r_km: float, 
                                r0_km: float = 1.0) -> float:
    """
    Decay geometris untuk propagasi tsunami.
    H(r) = H0 * sqrt(r0/r)
    """
    if r_km <= r0_km:
        return h0
    return h0 * math.sqrt(r0_km / r_km)


def fault_efficiency(fault_type: str) -> float:
    """
    Efisiensi tsunami berdasarkan tipe fault.
    Vertical (thrust/normal) = 100%, Strike-slip = 4% (Okada 1985).
    """
    ft = fault_type.lower().strip()
    if 'strike' in ft or 'slip' in ft:
        return 0.04
    elif 'thrust' in ft or 'normal' in ft or 'reverse' in ft or 'mega' in ft:
        return 1.0
    return 0.5  # Oblique / unknown


# ============================================================================
# 6. STATISTICS & AGGREGATION
# ============================================================================

def describe_array(arr: np.ndarray) -> Dict[str, float]:
    """
    Statistik deskriptif (ignore NaN).
    
    Returns:
        {min, max, mean, median, std, count}
    """
    clean = arr[~np.isnan(arr)] if arr.size > 0 else np.array([])
    if clean.size == 0:
        return {'min': 0, 'max': 0, 'mean': 0, 'median': 0, 'std': 0, 'count': 0}
    
    return {
        'min': float(np.min(clean)),
        'max': float(np.max(clean)),
        'mean': float(np.mean(clean)),
        'median': float(np.median(clean)),
        'std': float(np.std(clean)),
        'count': int(clean.size)
    }


def normalize(arr: np.ndarray, new_min: float = 0.0, 
               new_max: float = 1.0) -> np.ndarray:
    """Min-max normalization ke range baru."""
    arr_min = np.nanmin(arr)
    arr_max = np.nanmax(arr)
    
    if arr_max - arr_min < 1e-10:
        return np.full_like(arr, (new_min + new_max) / 2)
    
    normalized = (arr - arr_min) / (arr_max - arr_min)
    return normalized * (new_max - new_min) + new_min


# ============================================================================
# 7. VALIDATION & SAFETY
# ============================================================================

def safe_divide(numerator: float, denominator: float, 
                 default: float = 0.0) -> float:
    """
    Pembagian aman. Handle division by zero dan NaN (BUG E fix).
    """
    if denominator == 0 or math.isnan(denominator) or math.isnan(numerator):
        return default
    result = numerator / denominator
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def validate_coordinates(lat: float, lon: float) -> bool:
    """Validasi koordinat WGS84."""
    if math.isnan(lat) or math.isnan(lon):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Membatasi nilai dalam range [min_val, max_val]."""
    return max(min_val, min(value, max_val))


def sanitize_depth(depth: float, min_depth: float = -7500.0, 
                    max_depth: float = -0.5) -> Optional[float]:
    """
    3-Layer masking untuk nilai depth (sesuai dokumentasi server.py).
    
    Returns:
        Nilai depth yang valid, atau None jika tidak valid (land)
    """
    if math.isnan(depth):
        return None
    # Layer 1: Value threshold
    if depth >= max_depth:
        return None
    # Layer 2: Sanity range
    if depth < min_depth:
        return None
    return depth


# ============================================================================
# 8. GEOJSON & EXPORT UTILITIES
# ============================================================================

def coords_to_geojson_point(lat: float, lon: float, 
                              properties: Optional[Dict] = None) -> Dict:
    """Konversi koordinat ke GeoJSON Point Feature."""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties or {}
    }


def coords_to_geojson_linestring(coords: List[Tuple[float, float]],
                                    properties: Optional[Dict] = None) -> Dict:
    """
    Konversi list koordinat ke GeoJSON LineString.
    Input: [(lat, lon), ...]
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon, lat] for lat, lon in coords]
        },
        "properties": properties or {}
    }


def features_to_feature_collection(features: List[Dict]) -> Dict:
    """Wrap list of features ke GeoJSON FeatureCollection."""
    return {"type": "FeatureCollection", "features": features}


def shp_to_geojson(shp_path: str, simplify: float = 0.0, 
                     max_pts: int = 10000) -> Dict:
    """
    Konversi Shapefile ke GeoJSON dengan transformasi CRS ke WGS84.
    
    Parameters:
    - shp_path: Path ke shapefile (.shp)
    - simplify: Simplification tolerance (0 = no simplification)
    - max_pts: Maximum number of features to include
    
    Returns:
    - GeoJSON FeatureCollection dict
    """
    if not GEOPANDAS_AVAILABLE:
        logger.warning("geopandas not available, returning empty FeatureCollection")
        return {"type": "FeatureCollection", "features": []}
    
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        else:
            gdf = gdf.to_crs(epsg=4326)
        
        if simplify > 0:
            gdf['geometry'] = gdf['geometry'].simplify(simplify)
        
        if len(gdf) > max_pts:
            gdf = gdf.head(max_pts)
        
        return json.loads(gdf.to_json())
    except Exception as e:
        logger.error(f"Failed to load {shp_path}: {e}")
        return {"type": "FeatureCollection", "features": []}


# ============================================================================
# UNIT TESTS (dijalankan jika file di-run langsung)
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("UNIT TESTS - spatial_utils.py")
    print("=" * 70)
    
    # Test Haversine: Jakarta -> Yogyakarta (~440 km)
    jkt = (-6.2088, 106.8456)
    yog = (-7.7956, 110.3695)
    dist_km = haversine_km(jkt[0], jkt[1], yog[0], yog[1])
    assert 430 < dist_km < 450, f"Haversine FAIL: {dist_km}"
    print(f"✅ Haversine Jakarta→Jogja: {dist_km:.2f} km")
    
    # Test Safe Divide
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(float('nan'), 2) == 0.0
    print("✅ Safe Divide: OK")
    
    # Test Slope (BUG E)
    assert calculate_slope_percent(10, 20, 0) == 0.0  # No division by zero
    assert calculate_slope_percent(10, 20, 100) == 10.0
    print("✅ Slope Calculation: OK (no division by zero)")
    
    # Test Point in Polygon
    poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), poly) == True
    assert point_in_polygon((15, 5), poly) == False
    print("✅ Point in Polygon: OK")
    
    # Test Wave Speed
    c = wave_speed(4000)  # Deep ocean
    assert 190 < c < 210, f"Wave speed FAIL: {c}"
    print(f"✅ Wave Speed (4000m): {c:.2f} m/s")
    
    # Test Abe Formula
    h0 = abe_initial_height(9.0)
    assert 2 < h0 < 5, f"Abe FAIL: {h0}"
    print(f"✅ Abe Formula (Mw 9.0): H0 = {h0:.2f} m")
    
    # Test Synolakis Runup
    r = synolakis_runup(2.0)
    assert r > 5.0, f"Runup FAIL: {r}"
    print(f"✅ Synolakis Runup (H=2m): R = {r:.2f} m")
    
    # Test Dijkstra
    graph = {0: [(1, 1.0), (2, 4.0)], 1: [(2, 2.0)], 2: []}
    dist, pred = dijkstra(graph, 0, 2)
    assert dist[2] == 3.0
    print(f"✅ Dijkstra: shortest 0→2 = {dist[2]}")
    
    # Test Sanitize Depth
    assert sanitize_depth(-100) == -100
    assert sanitize_depth(10) is None  # Land
    assert sanitize_depth(-8000) is None  # Too deep
    print("✅ Sanitize Depth (3-layer mask): OK")
    
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)