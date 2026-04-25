"""
============================================================================
OSM ROUTER — Road Network dari Data Jalan Lokal + Fallback OSMnx
============================================================================
Membangun graph jalan dari Jalan_Bantul.shp (data OSM lokal) atau
download via OSMnx jika shapefile tidak tersedia.

Fitur:
- Build NetworkX graph dari shapefile jalan lokal (Jalan_Bantul.shp)
- Fallback download via OSMnx jika shapefile tidak tersedia
- Cache sebagai pickle untuk startup cepat
- Shortest-path routing dengan NetworkX (Dijkstra)
- Filter shelter/fasilitas yang berada di luar zona inundasi
- Konversi path → koordinat lat/lon untuk visualisasi
============================================================================
"""

import os
import time
import logging
import pickle
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

# ── Imports ────────────────────────────────────────────────────────
try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False
    nx = None

try:
    import geopandas as gpd
    GPD_AVAILABLE = True
except ImportError:
    GPD_AVAILABLE = False

try:
    from shapely.geometry import Point, LineString
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

try:
    from scipy.spatial import cKDTree
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import osmnx as ox
    OSMNX_AVAILABLE = True
except ImportError:
    OSMNX_AVAILABLE = False
    ox = None


# ── Speed map (km/h) berdasarkan tipe jalan OSM ──────────────────
SPEED_MAP = {
    'motorway': 80, 'motorway_link': 60,
    'trunk': 70, 'trunk_link': 50,
    'primary': 60, 'primary_link': 45,
    'secondary': 50, 'secondary_link': 40,
    'tertiary': 40, 'tertiary_link': 35,
    'unclassified': 30, 'residential': 30,
    'service': 20, 'living_street': 15,
    'track': 15, 'path': 5, 'footway': 5,
    'pedestrian': 5, 'cycleway': 10,
    'steps': 3,
}

# Daftar tipe fasilitas yang DILARANG jadi shelter
EXCLUDED_FACILITY_NAMES = [
    'kuburan', 'makam', 'pemakaman', 'cemetery', 'grave',
    'krematorium', 'crematorium', 'tpu ',
]


def _haversine_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters."""
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


class OSMRoadNetwork:
    """
    Build NetworkX road graph dari shapefile jalan lokal
    atau download dari OSM via OSMnx.
    """
    
    def __init__(self, vektor_dir: str, cache_dir: str = None):
        self.vektor_dir = vektor_dir
        self.cache_dir = cache_dir or os.path.join(vektor_dir, '..', '..', 'cache', 'osm')
        self.G: Optional[Any] = None  # NetworkX DiGraph
        self._kdtree = None
        self._node_ids = None
        self._node_coords = None
    
    @property
    def pickle_path(self) -> str:
        return os.path.join(self.cache_dir, 'road_network.pkl')
    
    def build(self) -> bool:
        """Build road network: try pickle cache → shapefile → OSMnx download."""
        if not NX_AVAILABLE:
            logger.error("NetworkX not installed")
            return False
        
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # 1. Try loading from pickle cache (fastest)
        if os.path.exists(self.pickle_path):
            try:
                t0 = time.time()
                with open(self.pickle_path, 'rb') as f:
                    self.G = pickle.load(f)
                elapsed = time.time() - t0
                logger.info(f"Road network loaded from cache: "
                           f"{self.G.number_of_nodes()} nodes, "
                           f"{self.G.number_of_edges()} edges ({elapsed:.1f}s)")
                self._build_kdtree()
                return True
            except Exception as e:
                logger.warning(f"Cache corrupt, rebuilding: {e}")
        
        # 2. Build from local shapefile (Jalan_Bantul.shp)
        if self._build_from_shapefile():
            self._save_pickle()
            return True
        
        # 3. Fallback: download from OSMnx
        if self._build_from_osmnx():
            self._save_pickle()
            return True
        
        return False
    
    def _build_from_shapefile(self) -> bool:
        """Build NetworkX graph dari Jalan_Bantul.shp (data OSM lokal)."""
        if not GPD_AVAILABLE:
            return False
        
        # Cari file jalan
        road_file = None
        for fname in os.listdir(self.vektor_dir):
            if fname.lower().endswith('.shp') and 'jalan' in fname.lower():
                road_file = os.path.join(self.vektor_dir, fname)
                break
        
        if road_file is None:
            logger.warning("No road shapefile found in Vektor directory")
            return False
        
        t0 = time.time()
        logger.info(f"Building road graph from {os.path.basename(road_file)}...")
        
        try:
            gdf = gpd.read_file(road_file)
            if gdf.crs is not None:
                gdf = gdf.to_crs(epsg=4326)
            else:
                gdf.set_crs(epsg=4326, inplace=True)
        except Exception as e:
            logger.error(f"Failed to read {road_file}: {e}")
            return False
        
        # Build directed graph
        G = nx.DiGraph()
        node_id_counter = 0
        coord_to_node = {}
        
        def get_or_create_node(lon, lat):
            nonlocal node_id_counter
            key = (round(lon, 6), round(lat, 6))
            if key in coord_to_node:
                return coord_to_node[key]
            nid = node_id_counter
            coord_to_node[key] = nid
            G.add_node(nid, y=lat, x=lon)
            node_id_counter += 1
            return nid
        
        edges_added = 0
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.geom_type != 'LineString':
                continue
            
            highway = str(row.get('highway', '') or row.get('fclass', '') or 'residential').lower()
            speed_kmh = SPEED_MAP.get(highway, 30)
            name = str(row.get('name', '') or '')
            oneway = bool(row.get('oneway', False))
            
            coords = list(geom.coords)
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i][0], coords[i][1]
                lon2, lat2 = coords[i+1][0], coords[i+1][1]
                
                u = get_or_create_node(lon1, lat1)
                v = get_or_create_node(lon2, lat2)
                
                if u == v:
                    continue
                
                dist_m = _haversine_m(lat1, lon1, lat2, lon2)
                if dist_m < 0.5:
                    continue
                
                travel_time = dist_m / (speed_kmh / 3.6)  # seconds
                
                edge_data = {
                    'length': dist_m,
                    'travel_time': travel_time,
                    'speed_kph': speed_kmh,
                    'highway': highway,
                    'name': name,
                }
                
                G.add_edge(u, v, **edge_data)
                edges_added += 1
                
                if not oneway:
                    G.add_edge(v, u, **edge_data)
                    edges_added += 1
        
        self.G = G
        elapsed = time.time() - t0
        logger.info(f"Road graph from shapefile: "
                    f"{G.number_of_nodes()} nodes, "
                    f"{G.number_of_edges()} edges ({elapsed:.1f}s)")
        
        self._build_kdtree()
        return True
    
    def _build_from_osmnx(self) -> bool:
        """Fallback: download dari OSM via OSMnx."""
        if not OSMNX_AVAILABLE:
            return False
        
        logger.info("Attempting OSMnx download for Bantul roads...")
        try:
            ox.settings.timeout = 120
            ox.settings.overpass_rate_limit = False
            
            self.G = ox.graph_from_bbox(
                bbox=(-7.77, -8.03, 110.52, 110.21),
                network_type='all',
                simplify=True,
            )
            self.G = ox.routing.add_edge_speeds(self.G)
            self.G = ox.routing.add_edge_travel_times(self.G)
            
            logger.info(f"OSMnx download: {self.G.number_of_nodes()} nodes, "
                       f"{self.G.number_of_edges()} edges")
            self._build_kdtree()
            return True
        except Exception as e:
            logger.warning(f"OSMnx download failed: {e}")
            return False
    
    def _save_pickle(self):
        """Cache graph as pickle for fast subsequent loads."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.pickle_path, 'wb') as f:
                pickle.dump(self.G, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Road network cached to {self.pickle_path}")
        except Exception as e:
            logger.warning(f"Failed to cache: {e}")
    
    def _build_kdtree(self):
        """Build KDTree for O(log n) nearest-node lookups."""
        if self.G is None:
            return
        
        nodes = list(self.G.nodes(data=True))
        self._node_ids = [n[0] for n in nodes]
        self._node_coords = np.array([
            [n[1].get('y', 0), n[1].get('x', 0)] for n in nodes
        ])
        
        if SCIPY_AVAILABLE and len(self._node_coords) > 0:
            self._kdtree = cKDTree(self._node_coords)
            logger.info(f"Road KDTree: {len(self._node_ids)} nodes")
    
    def nearest_node(self, lat: float, lon: float, max_dist_m: float = 2000) -> Optional[int]:
        """Find nearest graph node to coordinates."""
        if self._kdtree is not None:
            dist, idx = self._kdtree.query([lat, lon])
            # ~1 degree ≈ 111km
            if dist * 111000 > max_dist_m:
                return None
            return self._node_ids[idx]
        return None
    
    def shortest_path(self, start_node: int, end_node: int,
                      weight: str = 'length') -> Optional[List[int]]:
        """Dijkstra shortest path."""
        if self.G is None:
            return None
            
        # Use a weight function if we have blocked nodes to penalize inundated roads
        if hasattr(self, 'blocked_nodes') and self.blocked_nodes:
            def weight_func(u, v, d):
                cost = d.get(weight, 1.0)
                if u in self.blocked_nodes or v in self.blocked_nodes:
                    return cost + 1000000.0  # 1000km penalty for flooded roads
                return cost
            w = weight_func
        else:
            w = weight
            
        try:
            return nx.shortest_path(self.G, start_node, end_node, weight=w)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            # Fallback to undirected graph to avoid one-way street dead ends
            if self.G.is_directed():
                try:
                    if not hasattr(self, 'G_undirected') or self.G_undirected is None:
                        logger.info("shortest_path failed on directed graph, building undirected fallback cache...")
                        self.G_undirected = self.G.to_undirected()
                    return nx.shortest_path(self.G_undirected, start_node, end_node, weight=w)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
            return None

    def find_safe_route(self, origin_lat: float, origin_lon: float,
                        dest_lat: float, dest_lon: float,
                        transport_mode: str = 'foot',
                        safety_weight: float = 50.0,
                        inundation_geojson: Optional[Dict] = None) -> Dict:
        """
        Cari rute evakuasi yang seimbang antara kecepatan dan keselamatan.
        """
        if self.G is None:
            raise ValueError("Road network belum diinisialisasi")
        
        # 1. Parse inundation zones
        flood_cells = set()
        if inundation_geojson:
            try:
                features = inundation_geojson.get('features', [])
                for feat in features:
                    geom = feat.get('geometry', {})
                    if geom.get('type') == 'Polygon':
                        coords = geom.get('coordinates', [[]])[0]
                        for lon, lat in coords:
                            flood_cells.add((round(lat, 4), round(lon, 4)))
            except Exception as e:
                logger.warning(f"Failed to parse inundation: {e}")
        
        # 2. Find nearest nodes di graph
        origin_node = self.nearest_node(origin_lat, origin_lon)
        dest_node = self.nearest_node(dest_lat, dest_lon)
        
        if not origin_node or not dest_node:
            raise ValueError("Tidak bisa menemukan node terdekat di graph")
        
        # 3. Hitung cost edge dengan safety weight
        def edge_cost(u, v, d):
            dist_km = d.get('length', 0) / 1000.0
            
            u_lat, u_lon = self.G.nodes[u].get('y'), self.G.nodes[u].get('x')
            v_lat, v_lon = self.G.nodes[v].get('y'), self.G.nodes[v].get('x')
            
            flood_risk = 0.0
            if u_lat and u_lon and (round(u_lat, 4), round(u_lon, 4)) in flood_cells:
                flood_risk += 0.5
            if v_lat and v_lon and (round(v_lat, 4), round(v_lon, 4)) in flood_cells:
                flood_risk += 0.5
            
            speed_factor = (100.0 - safety_weight) / 100.0
            safety_factor = safety_weight / 100.0
            
            return speed_factor * dist_km + safety_factor * flood_risk * 10.0
        
        # 4. Shortest path dengan custom cost
        try:
            path_nodes = nx.shortest_path(self.G, origin_node, dest_node, weight=edge_cost)
        except nx.NetworkXNoPath:
            if self.G.is_directed():
                try:
                    if not hasattr(self, 'G_undirected') or self.G_undirected is None:
                        self.G_undirected = self.G.to_undirected()
                    path_nodes = nx.shortest_path(self.G_undirected, origin_node, dest_node, weight=edge_cost)
                except nx.NetworkXNoPath:
                    raise ValueError("Tidak ada rute yang tersedia")
            else:
                raise ValueError("Tidak ada rute yang tersedia")
        
        # 5. Build results
        path_coords = self.path_to_coords(path_nodes)
        total_dist_m = self.path_distance_m(path_nodes)
        
        flood_count = sum(1 for lat, lon in path_coords if (round(lat, 4), round(lon, 4)) in flood_cells)
        safety_score = max(0.0, min(100.0, 100.0 - (flood_count / max(len(path_coords), 1) * 100)))
        
        speed_kmh = 5 if transport_mode == 'foot' else (20 if transport_mode == 'motor' else 40)
        time_min = (total_dist_m / 1000.0) / speed_kmh * 60.0
        
        return {
            'path': [[lat, lon] for lat, lon in path_coords],
            'distance_km': total_dist_m / 1000.0,
            'time_min': time_min,
            'safety_score': safety_score,
            'avoids_flood': flood_count == 0,
            'n_nodes': len(path_nodes)
        }
    
    def path_to_coords(self, path: List[int]) -> List[Tuple[float, float]]:
        """Convert node path → [(lat, lon), ...]."""
        if self.G is None or not path:
            return []
        
        coords = []
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            
            # Tambahkan node awal
            coords.append((self.G.nodes[u].get('y', 0), self.G.nodes[u].get('x', 0)))
            
            edge_data = self.G.get_edge_data(u, v)
            if edge_data:
                # Handle MultiDiGraph (osmnx) vs DiGraph
                if isinstance(edge_data, dict) and 0 in edge_data:
                    data = edge_data[0]
                else:
                    data = edge_data
                    
                if 'geometry' in data:
                    geom = data['geometry']
                    if hasattr(geom, 'coords'):
                        # geometry.coords is list of (lon, lat)
                        geom_coords = [(lat, lon) for lon, lat in list(geom.coords)]
                        # Skip titik awal (u) dan akhir (v) karena akan ditambahkan dari node
                        if len(geom_coords) > 2:
                            coords.extend(geom_coords[1:-1])
                            
        # Tambahkan node paling akhir
        last_u = path[-1]
        coords.append((self.G.nodes[last_u].get('y', 0), self.G.nodes[last_u].get('x', 0)))
        
        return coords
    
    def path_distance_m(self, path: List[int]) -> float:
        """Total path distance in meters."""
        if self.G is None or not path or len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            data = self.G.get_edge_data(u, v)
            if data:
                # DiGraph: single edge
                total += data.get('length', 0)
            else:
                # Calculate from coords
                c1 = self.get_node_coords(u)
                c2 = self.get_node_coords(v)
                if c1 and c2:
                    total += _haversine_m(c1[0], c1[1], c2[0], c2[1])
        return total
    
    def get_node_coords(self, node_id: int) -> Optional[Tuple[float, float]]:
        """Get (lat, lon) for a node."""
        if self.G is None or node_id not in self.G.nodes:
            return None
        data = self.G.nodes[node_id]
        return (data.get('y', 0), data.get('x', 0))


class SafeShelterFilter:
    """
    Filter shelter/fasilitas umum yang AMAN:
    - TIDAK berada di zona inundasi
    - BUKAN kuburan/krematorium
    """
    
    def __init__(self):
        self._inundation_kdtree = None
    
    def set_inundation_zone(self, inundation_geojson: Dict = None,
                            flood_polygons: List = None):
        """Set zona inundasi dari SWE result."""
        points = []
        
        if inundation_geojson and 'features' in inundation_geojson:
            for feat in inundation_geojson.get('features', []):
                geom = feat.get('geometry', {})
                coords = geom.get('coordinates', [])
                if len(coords) >= 2:
                    points.append([coords[1], coords[0]])
        
        if flood_polygons:
            for poly_data in flood_polygons:
                coords = poly_data if isinstance(poly_data, list) else poly_data.get('coordinates', [])
                if coords:
                    for ring in coords:
                        if isinstance(ring, (list, tuple)):
                            for pt in ring:
                                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                                    points.append([pt[1], pt[0]])
        
        if points and SCIPY_AVAILABLE:
            self._inundation_kdtree = cKDTree(np.array(points))
            logger.info(f"Inundation zone: {len(points)} reference points")
    
    def is_in_inundation_zone(self, lat: float, lon: float,
                               threshold_m: float = 200) -> bool:
        """Check if a point is within the inundation zone."""
        if self._inundation_kdtree is None:
            return False
        dist, _ = self._inundation_kdtree.query([lat, lon])
        return dist * 111000 < threshold_m
    
    def filter_safe_shelters(self, shelters: List) -> List:
        """
        Filter shelters:
        1. BUKAN kuburan/makam
        2. TIDAK di zona inundasi
        """
        safe = []
        for shelter in shelters:
            name = getattr(shelter, 'name', '') or ''
            name_lower = name.lower()
            
            # Skip excluded types
            if any(excl in name_lower for excl in EXCLUDED_FACILITY_NAMES):
                logger.info(f"Shelter excluded (type): {name}")
                continue
            
            # Check inundation zone
            lat = getattr(shelter, 'lat', 0)
            lon = getattr(shelter, 'lon', 0)
            if self.is_in_inundation_zone(lat, lon):
                logger.info(f"Shelter excluded (inundasi): {name} ({lat:.4f}, {lon:.4f})")
                continue
            
            safe.append(shelter)
        
        logger.info(f"Safe shelters: {len(safe)}/{len(shelters)}")
        return safe


class OSMEvacuationRouter:
    """
    Router evakuasi berbasis road network.
    Menggabungkan OSMRoadNetwork + SafeShelterFilter.
    """
    
    def __init__(self, road_network: OSMRoadNetwork):
        self.network = road_network
        self.shelter_filter = SafeShelterFilter()
        self._safe_shelters = None
        
    def path_to_coords(self, path: List[int]) -> List[Tuple[float, float]]:
        """Proxy ke network path_to_coords"""
        return self.network.path_to_coords(path)
        
    def path_distance_m(self, path: List[int]) -> float:
        """Proxy ke network path_distance_m"""
        return self.network.path_distance_m(path)
    
    def set_flood_data(self, inundation_geojson: Dict = None,
                       flood_polygons: List = None):
        """Update flood zone data."""
        self.shelter_filter.set_inundation_zone(inundation_geojson, flood_polygons)
        
        # Block flooded nodes in the network
        blocked_nodes = set()
        if self.network.G:
            for node, data in self.network.G.nodes(data=True):
                lat, lon = data.get('y', 0), data.get('x', 0)
                if self.shelter_filter.is_in_inundation_zone(lat, lon):
                    blocked_nodes.add(node)
            self.network.blocked_nodes = blocked_nodes
            logger.info(f"Blocked {len(blocked_nodes)} nodes in OSMRoadNetwork due to inundation")
    def update_safe_shelters(self, all_shelters: List):
        """Filter and cache safe shelters."""
        self._safe_shelters = self.shelter_filter.filter_safe_shelters(all_shelters)
        
        # Map shelters to nearest graph nodes
        for shelter in self._safe_shelters:
            if getattr(shelter, 'node_id', None) is None:
                shelter.node_id = self.network.nearest_node(shelter.lat, shelter.lon)
        
        return self._safe_shelters
    
    def get_safe_shelters(self) -> List:
        return self._safe_shelters or []
    
    def find_route(self, start_lat: float, start_lon: float,
                   end_lat: float, end_lon: float,
                   weight: str = 'length') -> Optional[Dict]:
        """
        Find evacuation route between two points on the road network.
        Returns dict with route info or None.
        """
        start_node = self.network.nearest_node(start_lat, start_lon)
        end_node = self.network.nearest_node(end_lat, end_lon)
        
        if start_node is None or end_node is None:
            logger.warning(f"No graph nodes near ({start_lat}, {start_lon}) → ({end_lat}, {end_lon}). start_node={start_node}, end_node={end_node}")
            return None
            
        logger.info(f"Routing from node {start_node} to {end_node}")
        
        path = self.network.shortest_path(start_node, end_node, weight=weight)
        if path is None:
            logger.warning(f"No path found between node {start_node} and {end_node}")
            return None
        
        coords = self.network.path_to_coords(path)
        total_dist_m = self.network.path_distance_m(path)
        
        return {
            'path_nodes': path,
            'coordinates': coords,
            'total_distance_m': total_dist_m,
            'total_distance_km': total_dist_m / 1000.0,
            'n_nodes': len(path),
        }
    
    def find_nearest_shelter_route(self, start_lat: float, start_lon: float,
                                    shelters: List = None) -> Optional[Dict]:
        """
        Find route to the nearest safe shelter (by road distance).
        """
        shelters = shelters or self._safe_shelters or []
        if not shelters:
            return None
        
        start_node = self.network.nearest_node(start_lat, start_lon)
        if start_node is None:
            return None
        
        best_shelter = None
        best_path = None
        best_dist = float('inf')
        
        for shelter in shelters:
            # Pengecekan kapasitas
            occupancy = getattr(shelter, 'current_occupancy', 0)
            capacity = getattr(shelter, 'capacity', 1000)
            if occupancy >= capacity:
                continue

            node_id = getattr(shelter, 'node_id', None)
            if node_id is None:
                continue
            
            path = self.network.shortest_path(start_node, node_id)
            if path is None:
                continue
            
            dist = self.network.path_distance_m(path)
            if dist < best_dist:
                best_dist = dist
                best_shelter = shelter
                best_path = path
        
        if best_shelter is None:
            return None
        
        coords = self.network.path_to_coords(best_path)
        return {
            'shelter': best_shelter,
            'path_nodes': best_path,
            'coordinates': coords,
            'total_distance_m': best_dist,
            'total_distance_km': best_dist / 1000.0,
            'n_nodes': len(best_path),
        }
