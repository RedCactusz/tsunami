"""
Road Network Router
====================
Load shapefile jalan, build graph, dan run Dijkstra untuk routing evakuasi.
"""

import os
import logging
import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import geopandas as gpd
    import networkx as nx
    from shapely.geometry import Point, LineString
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    logger.warning("geopandas/networkx not available - routing will use fallback")


@dataclass
class RoadGraph:
    """Road network graph untuk routing."""
    graph: nx.Graph  # NetworkX graph
    gdf: gpd.GeoDataFrame  # Original GeoDataFrame
    nodes_gdf: gpd.GeoDataFrame  # Nodes as points
    crs: str = "EPSG:4326"

    def get_nearest_node(self, lat: float, lon: float) -> Tuple[int, float]:
        """Cari node terdekat dari titik koordinat."""
        point = Point(lon, lat)

        # Query nearest node menggunakan spatial index
        distances = self.nodes_gdf.geometry.distance(point)
        nearest_idx = distances.idxmin()
        nearest_dist = distances.min()

        return nearest_idx, nearest_dist * 111000  # Convert to meters (approx)


def load_road_network(shapefile_path: str) -> Optional[RoadGraph]:
    """
    Load road network dari shapefile dan build graph.

    Args:
        shapefile_path: Path ke Jalan_Bantul.shp

    Returns:
        RoadGraph object atau None jika gagal
    """
    if not GEOPANDAS_AVAILABLE:
        logger.error("geopandas/networkx tidak tersedia")
        return None

    if not os.path.exists(shapefile_path):
        logger.error(f"Shapefile tidak ditemukan: {shapefile_path}")
        return None

    try:
        logger.info(f"Loading road network dari {shapefile_path}...")

        # Load shapefile (use pyogrio engine to avoid fiona compatibility issues)
        gdf = gpd.read_file(shapefile_path, engine='pyogrio')

        # Pastikan CRS benar (WGS84)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")

        logger.info(f"Loaded {len(gdf)} road features")

        # Filter hanya LineString
        gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
        logger.info(f"After filter: {len(gdf)} LineString features")

        # Build NetworkX graph
        G = nx.Graph()

        # Extract nodes dari setiap line
        node_id = 0
        node_map = {}  # (lat, lon) -> node_id

        for idx, row in gdf.iterrows():
            geom = row.geometry

            # Handle MultiLineString
            if geom.geom_type == 'MultiLineString':
                lines = list(geom.geoms)
            else:
                lines = [geom]

            for line in lines:
                coords = list(line.coords)

                # Add nodes
                for coord in coords:
                    # Handle both 2D (lon, lat) and 3D (lon, lat, z) coordinates
                    if len(coord) >= 2:
                        lon, lat = coord[0], coord[1]
                    else:
                        continue

                    key = (round(lat, 6), round(lon, 6))
                    if key not in node_map:
                        node_map[key] = node_id
                        G.add_node(node_id, pos=(lat, lon))
                        node_id += 1

                # Add edges along the line
                for i in range(len(coords) - 1):
                    coord1, coord2 = coords[i], coords[i + 1]
                    lon1, lat1 = coord1[0], coord1[1]
                    lon2, lat2 = coord2[0], coord2[1]

                    n1 = node_map[(round(lat1, 6), round(lon1, 6))]
                    n2 = node_map[(round(lat2, 6), round(lon2, 6))]

                    # Calculate distance (Haversine approximation)
                    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
                    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)

                    dlat = lat2_rad - lat1_rad
                    dlon = lon2_rad - lon1_rad
                    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
                    c = 2 * np.arcsin(np.sqrt(a))
                    distance_m = 6371000 * c  # Earth radius in meters

                    # Get road type for speed (default 30 km/h)
                    highway = row.get('highway', 'residential')
                    speed_kmh = get_road_speed(highway)
                    speed_m_min = (speed_kmh * 1000) / 60  # m/min

                    time_min = distance_m / speed_m_min if speed_m_min > 0 else float('inf')

                    G.add_edge(n1, n2, weight=time_min, distance=distance_m, road_type=highway)

        logger.info(f"Built graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Create nodes GeoDataFrame
        nodes_data = []
        for node_id, data in G.nodes(data=True):
            lat, lon = data['pos']
            nodes_data.append({'node_id': node_id, 'lat': lat, 'lon': lon, 'geometry': Point(lon, lat)})

        nodes_gdf = gpd.GeoDataFrame(nodes_data, geometry='geometry', crs="EPSG:4326")

        return RoadGraph(graph=G, gdf=gdf, nodes_gdf=nodes_gdf)

    except Exception as e:
        logger.error(f"Error loading road network: {e}")
        return None


def get_road_speed(highway: str) -> float:
    """Return speed km/h berdasarkan tipe jalan."""
    speed_map = {
        'motorway': 80,
        'trunk': 70,
        'primary': 60,
        'secondary': 50,
        'tertiary': 40,
        'residential': 30,
        'unclassified': 25,
        'service': 20,
        'track': 15,
        'path': 8,
        'footway': 5,
    }
    return speed_map.get(highway, 30)


def find_route(
    road_graph: RoadGraph,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    transport_speed_kmh: float = 5.0
) -> Dict:
    """
    Cari rute terpendek antara dua titik menggunakan Dijkstra.

    Args:
        road_graph: RoadGraph object
        start_lat, start_lon: Koordinat titik awal
        end_lat, end_lon: Koordinat titik tujuan
        transport_speed_kmh: Kecepatan transportasi (default 5 km/h untuk jalan kaki)

    Returns:
        Dict dengan route_path, distance_km, time_min
    """
    try:
        # Find nearest nodes
        start_node_idx, start_dist = road_graph.get_nearest_node(start_lat, start_lon)
        end_node_idx, end_dist = road_graph.get_nearest_node(end_lat, end_lon)

        # Run Dijkstra
        path = nx.shortest_path(
            road_graph.graph,
            source=start_node_idx,
            target=end_node_idx,
            weight='weight'  # weight = time in minutes
        )

        # Get path coordinates
        route_path = []
        for node_id in path:
            lat, lon = road_graph.graph.nodes[node_id]['pos']
            route_path.append([lat, lon])

        # Calculate total distance
        total_distance_m = 0
        for i in range(len(path) - 1):
            n1, n2 = path[i], path[i + 1]
            if road_graph.graph.has_edge(n1, n2):
                total_distance_m += road_graph.graph[n1][n2]['distance']

        distance_km = total_distance_m / 1000

        # Calculate travel time
        time_min = (distance_km / transport_speed_kmh) * 60

        return {
            'route_path': route_path,
            'distance_km': round(distance_km, 2),
            'walk_time_min': int(time_min),
            'success': True
        }

    except Exception as e:
        logger.error(f"Error finding route: {e}")
        # Fallback: straight line
        return {
            'route_path': [[start_lat, start_lon], [end_lat, end_lon]],
            'distance_km': round(haversine_distance(start_lat, start_lon, end_lat, end_lon), 2),
            'walk_time_min': int((haversine_distance(start_lat, start_lon, end_lat, end_lon) / transport_speed_kmh) * 60),
            'success': False
        }


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Hitung distance antara dua titik dalam km (Haversine formula)."""
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return 6371 * c  # Earth radius in km


# Global cache for road graph
_road_graph_cache: Optional[RoadGraph] = None


def get_or_load_road_graph(shapefile_path: str = None) -> Optional[RoadGraph]:
    """Get cached road graph atau load baru jika belum ada."""
    global _road_graph_cache

    if _road_graph_cache is not None:
        return _road_graph_cache

    if shapefile_path is None:
        # Default path
        current_dir = os.path.dirname(__file__)
        data_dir = os.path.join(current_dir, "..", "..", "data", "Vektor")
        shapefile_path = os.path.join(data_dir, "Jalan_Bantul.shp")

    _road_graph_cache = load_road_network(shapefile_path)
    return _road_graph_cache
