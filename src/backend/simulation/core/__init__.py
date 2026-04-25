"""Shared utilities for SWE and ABM simulations."""

from .spatial_utils import (
    # Constants
    EARTH_RADIUS_M, EARTH_RADIUS_KM, GRAVITY, DEG_TO_RAD, RAD_TO_DEG,
    # Distance & geometry
    haversine_m, haversine_km, haversine_vectorized,
    bearing_degrees, destination_point,
    point_in_polygon, polygon_area_m2, bbox_from_points,
    bbox_intersects, create_grid,
    # Interpolation
    bilinear_interpolation, nearest_neighbor_fill,
    # Pathfinding
    dijkstra, astar, reconstruct_path,
    # Elevation & slope
    calculate_slope_percent, calculate_slope_degrees,
    elevation_penalty, slope_penalty,
    # Utilities
    safe_divide, validate_coordinates, clamp,
    sanitize_depth, describe_array,
    # Tsunami physics
    wave_speed, abe_initial_height, synolakis_runup,
    geometric_spreading_decay, fault_efficiency,
    # Geojson
    coords_to_geojson_point, coords_to_geojson_linestring,
    features_to_feature_collection,
    shp_to_geojson
)
from .cache import (
    build_road_cache, build_desa_cache, build_tes_cache
)

__all__ = [
    # Constants
    'EARTH_RADIUS_M', 'EARTH_RADIUS_KM', 'GRAVITY', 'DEG_TO_RAD', 'RAD_TO_DEG',
    # Distance & geometry
    'haversine_m', 'haversine_km', 'haversine_vectorized',
    'bearing_degrees', 'destination_point',
    'point_in_polygon', 'polygon_area_m2', 'bbox_from_points',
    'bbox_intersects', 'create_grid',
    # Interpolation
    'bilinear_interpolation', 'nearest_neighbor_fill',
    # Pathfinding
    'dijkstra', 'astar', 'reconstruct_path',
    # Elevation & slope
    'calculate_slope_percent', 'calculate_slope_degrees',
    'elevation_penalty', 'slope_penalty',
    # Utilities
    'safe_divide', 'validate_coordinates', 'clamp',
    'sanitize_depth', 'describe_array',
    # Tsunami physics
    'wave_speed', 'abe_initial_height', 'synolakis_runup',
    'geometric_spreading_decay', 'fault_efficiency',
    # Geojson
    'coords_to_geojson_point', 'coords_to_geojson_linestring',
    'features_to_feature_collection', 'shp_to_geojson',
    # Cache builders
    'build_road_cache', 'build_desa_cache', 'build_tes_cache'
]
