"""
Agent Generator - Generate agents dari Pemukiman ke TES Terdekat
Modular script, independent, menggunakan global data
"""
import random
import logging
from typing import List, Dict

# ✅ Fix import (relative path)
from .data_loader import get_pemukiman_data, get_tes_data

logger = logging.getLogger(__name__)

# Spatial utils
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Hitung jarak dalam meter (Haversine formula)."""
    from math import radians, sin, cos, sqrt, asin

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    return 6371000 * c


def generate_agents_from_pemukiman(
    graph,
    agents_per_pemukiman: int = 10,
    swe_inundation_geojson = None,
    dem_manager = None,
    wave_arrival_func = None  # ✅ Added: Function to calculate wave arrival time
) -> List[Dict]:
    """
    Generate agents dari Pemukiman.geojson ke TES terdekat.

    Args:
        graph: EvacuationGraph untuk nearest_node
        agents_per_pemukiman: Jumlah agent per pemukiman
        swe_inundation_geojson: GeoJSON inundasi dari SWE (optional)
        dem_manager: DEM Manager untuk query elevasi (optional)
        wave_arrival_func: Function untuk menghitung wave arrival time (optional)

    Returns:
        List of agent dicts
    """
    from .evacuation_abm import Agent

    # Load data
    pemukiman_list = get_pemukiman_data()
    tes_list = get_tes_data()

    if not pemukiman_list:
        logger.error("[AgentGenerator] No pemukiman data!")
        return []

    if not tes_list:
        logger.error("[AgentGenerator] No TES data!")
        return []

    # ✅ Build KDTree dari SWE inundation data (jika ada)
    kdtree = None
    inundation_points = []
    has_swe = False

    if swe_inundation_geojson is not None:
        try:
            from scipy.spatial import cKDTree as KDTree
            import numpy as np

            # Extract inundation points dari geojson
            for feature in swe_inundation_geojson.get('features', []):
                geom = feature.get('geometry', {})
                props = feature.get('properties', {})

                if geom.get('type') == 'Point':
                    # SWE output uses Point geometry with flood_depth in properties
                    coords = geom.get('coordinates', [])
                    depth = props.get('flood_depth', props.get('depth', props.get('h_max', 1.0)))
                    if len(coords) >= 2:
                        lon, lat = coords[0], coords[1]
                        inundation_points.append((lat, lon, depth))  # lat, lon, depth
                elif geom.get('type') == 'Polygon':
                    coords = geom.get('coordinates', [[]])[0]  # Exterior ring
                    depth = props.get('flood_depth', props.get('depth', props.get('h_max', 1.0)))
                    for coord in coords:
                        inundation_points.append((coord[1], coord[0], depth))  # lat, lon, depth
                elif geom.get('type') == 'MultiPolygon':
                    for polygon in geom.get('coordinates', []):
                        coords = polygon[0]  # Exterior ring
                        depth = props.get('flood_depth', props.get('depth', props.get('h_max', 1.0)))
                        for coord in coords:
                            inundation_points.append((coord[1], coord[0], depth))

            if inundation_points:
                inundation_array = np.array(inundation_points)
                kdtree = KDTree(inundation_array[:, :2])  # Hanya lat, lon untuk indexing
                has_swe = True
                logger.info(f"[AgentGenerator] ✅ Built KDTree with {len(inundation_points)} inundation points")
        except Exception as e:
            logger.warning(f"[AgentGenerator] Failed to build inundation KDTree: {e}")

    logger.info(f"[AgentGenerator] Generating agents from {len(pemukiman_list)} pemukiman → {len(tes_list)} TES")
    logger.info(f"[AgentGenerator] Has SWE inundation data: {has_swe}")

    # ✅ FILTER TES YANG AMAN (tidak terinundasi)
    # Menggunakan dynamic radius berdasarkan 4 titik inundasi terdekat
    safe_tes_list = []
    inundated_tes_list = []

    if kdtree is not None:
        for tes in tes_list:
            # Query 4 titik inundasi terdekat
            tes_coords = (tes['lat'], tes['lon'])

            # KDTree.query dengan k=4 untuk mendapatkan 4 tetangga terdekat
            distances, indices = kdtree.query(tes_coords, k=4)

            # Handle case jika kurang dari 4 titik yang ditemukan
            if distances.ndim == 0:
                distances = np.array([distances])
                indices = np.array([indices])

            # Filter out infinite distances (titik yang tidak ditemukan)
            valid_mask = distances != float('inf')
            valid_distances = distances[valid_mask]
            valid_indices = indices[valid_mask]

            if len(valid_distances) == 0:
                # Tidak ada titik inundasi dalam radius, anggap aman
                safe_tes_list.append(tes)
                continue

            # Ambil 4 titik terdekat (atau kurang jika tidak ada 4)
            k_nearest = min(4, len(valid_distances))
            nearest_distances = valid_distances[:k_nearest]

            # Hitung dynamic radius: setengah dari jarak maksimum antar 4 titik
            # Ini mengasumsikan 4 titik membentuk bounding box
            # Radius buffer = 0.5 × max_distance
            max_distance = np.max(nearest_distances)
            dynamic_radius = max_distance * 0.5

            # Cek apakah ada titik inundasi dalam dynamic radius dengan depth > 0.3m
            is_inundated = False
            max_flood_depth = 0.0
            min_flood_distance = float('inf')

            for i in range(len(valid_distances)):
                if valid_distances[i] <= dynamic_radius:
                    flood_depth = inundation_points[valid_indices[i]][2]
                    if flood_depth > 0.3:  # Banjir > 30cm
                        is_inundated = True
                        if flood_depth > max_flood_depth:
                            max_flood_depth = flood_depth
                        if valid_distances[i] < min_flood_distance:
                            min_flood_distance = valid_distances[i]

            if is_inundated:
                inundated_tes_list.append(tes['name'])
                logger.info(f"[AgentGenerator] ❌ TES {tes['name']} INUNDATED ({max_flood_depth:.2f}m at {min_flood_distance*111000:.0f}m, radius={dynamic_radius*111000:.0f}m) - NOT SAFE")
            else:
                safe_tes_list.append(tes)

        if len(inundated_tes_list) > 0:
            logger.warning(f"[AgentGenerator] ⚠️  {len(inundated_tes_list)} TES marked as inundated and EXCLUDED:")
            for tes_name in inundated_tes_list:
                logger.warning(f"[AgentGenerator]    - {tes_name}")
    else:
        # Tidak ada data inundasi, anggap semua TES aman
        safe_tes_list = tes_list
        logger.info("[AgentGenerator] No inundation data - all TES considered safe")

    logger.info(f"[AgentGenerator] ✅ Safe TES available: {len(safe_tes_list)}/{len(tes_list)}")

    # Initialize agents list
    agents = []
    agent_id = 0

    # Stats
    total_pemukiman = len(pemukiman_list)
    skipped_inundated = 0
    skipped_no_pop = 0
    generated_count = 0

    for pemukiman in pemukiman_list:
        if pemukiman['population'] <= 0:
            continue

        dlat = pemukiman['centroid_lat']
        dlon = pemukiman['centroid_lon']

        # ✅ CEK INUNDASI - untuk set flood_depth dan hazard risk, tapi GENERATE SEMUA AGENT
        # Logika: Semua pemukiman generate agent (baik yang aman maupun yang terkena tsunami)
        # - Area terinundasi → orang MUNGKIN SELAMAT kalau evakuasi cepat
        # - Area aman → orang mungkin ikut evakuasi karena takut/panik
        flood_depth = 0.0
        is_inundated = False

        if kdtree is not None:
            dist, idx = kdtree.query((dlat, dlon), distance_upper_bound=0.005)  # ~500m radius
            is_inundated = (dist != float('inf'))
            if is_inundated and idx < len(inundation_points):
                flood_depth = inundation_points[idx][2]

        # ✅ TIDAK ADA SKIP - Generate agent dari SEMUA pemukiman!

        # Cari TES terdekat yang AMAN (sudah difilter sebelumnya)
        nearest_safe_tes = None
        min_safe_dist = float('inf')

        for tes in safe_tes_list:
            dist = haversine_m(dlat, dlon, tes['lat'], tes['lon'])
            if dist < min_safe_dist:
                min_safe_dist = dist
                nearest_safe_tes = tes

        if nearest_safe_tes is None:
            # Fallback: gunakan TES terdekat (meski mungkin banjir)
            logger.warning(f"[AgentGenerator] No safe TES for {pemukiman['name']} - using nearest TES as fallback")
            for tes in tes_list:
                dist = haversine_m(dlat, dlon, tes['lat'], tes['lon'])
                if dist < min_safe_dist:
                    min_safe_dist = dist
                    nearest_safe_tes = tes

        if nearest_safe_tes is None:
            continue

        # Nearest node di road graph dengan max distance lebih besar (20km)
        home_node = graph.nearest_node(dlat, dlon, max_dist_m=20000)
        if home_node is None:
            # Fallback: gunakan koordinat langsung tanpa graph node
            # Agent akan tetap bisa di-visualisasi walau tanpa routing
            logger.warning(f"No graph node near pemukiman {pemukiman['name']} (within 20km) - using direct coordinates")
            home_node = -1  # Special marker for no-graph-node agents

        # Generate agents dari pemukiman ini
        n_agents = min(agents_per_pemukiman, pemukiman['population'], 100)  # Max 100 per pemukiman
        if n_agents == 0:
            continue

        pop_per_agent = max(1, pemukiman['population'] // n_agents)

        for i in range(n_agents):
            # Modal split: 80% foot, 15% motor, 5% car
            rand_val = random.random()
            if rand_val < 0.80:
                transport_mode = 'foot'
            elif rand_val < 0.95:
                transport_mode = 'motor'
            else:
                transport_mode = 'car'

            # Jitter position agar tidak bertumpuk
            home_lat_jitter = dlat + random.uniform(-0.0005, 0.0005)
            home_lon_jitter = dlon + random.uniform(-0.0005, 0.0005)

            # Speed berdasarkan transport mode
            speeds = {'foot': 1.38, 'motor': 5.66, 'car': 4.17}
            base_speed = speeds[transport_mode]
            speed_variation = random.uniform(0.85, 1.15)

            # Distance to coast
            pemukiman_coast_dist = 0.0  # TODO: calculate if coastline available

            # ✅ Calculate wave arrival time (if function provided)
            wave_arrival_min = None
            if wave_arrival_func is not None:
                try:
                    wave_arrival_min = wave_arrival_func(dlat, dlon)
                    logger.info(f"[AgentGenerator] pemukiman {pemukiman['name']}: wave_arrival_min={wave_arrival_min}")
                except Exception as e:
                    logger.warning(f"[AgentGenerator] Failed to calculate wave_arrival for pemukiman {pemukiman['name']}: {e}")
            else:
                logger.debug(f"[AgentGenerator] wave_arrival_func is None for pemukiman {pemukiman['name']}")

            # Hazard risk level
            if flood_depth >= 3.0 or pemukiman_coast_dist < 0.5:
                risk_level = 'EKSTREM'
            elif flood_depth >= 1.5 or pemukiman_coast_dist < 1.0:
                risk_level = 'TINGGI'
            elif flood_depth >= 0.5 or pemukiman_coast_dist < 2.0:
                risk_level = 'SEDANG'
            else:
                risk_level = 'AMAN'

            agents.append({
                'id': agent_id,
                'home_lat': home_lat_jitter,
                'home_lon': home_lon_jitter,
                'home_node': home_node,
                'lat': home_lat_jitter,  # Untuk compatibility
                'lon': home_lon_jitter,  # Untuk compatibility
                'desa_name': pemukiman['name'],
                'desa_id': pemukiman['id'],
                'population': pop_per_agent,
                'status': 'waiting',
                'counted': False,
                'shelter_id': nearest_safe_tes['id'],
                'transport_mode': transport_mode,
                'speed_mps': base_speed * speed_variation,
                'weight': pop_per_agent,
                'distance_to_coast_km': pemukiman_coast_dist,
                'in_hazard_zone': is_inundated,
                'flood_depth_m': flood_depth,
                'hazard_risk_level': risk_level,
                'wave_arrival_min': wave_arrival_min,  # ✅ Wave arrival time for survival logic
                # Extra fields
                'target_tes_name': nearest_safe_tes['name'],
                'target_tes_lat': nearest_safe_tes['lat'],
                'target_tes_lon': nearest_safe_tes['lon'],
                'target_tes_distance_km': min_safe_dist / 1000.0,
            })

            agent_id += 1
            generated_count += 1

    # ✅ Logging statistik lengkap
    logger.info(f"[AgentGenerator] ✅ Generated {len(agents)} agents from {generated_count} pemukiman")
    logger.info(f"[AgentGenerator] 📊 Statistics:")
    logger.info(f"  - Total pemukiman: {total_pemukiman}")
    logger.info(f"  - Skipped (inundated): {skipped_inundated}")
    logger.info(f"  - Skipped (no pop): {skipped_no_pop}")
    logger.info(f"  - Generated from: {generated_count} pemukiman")

    # Modal split stats
    if agents:
        foot_count = sum(1 for a in agents if a['transport_mode'] == 'foot')
        motor_count = sum(1 for a in agents if a['transport_mode'] == 'motor')
        car_count = sum(1 for a in agents if a['transport_mode'] == 'car')
        logger.info(f"  - Modal split: foot={foot_count}, motor={motor_count}, car={car_count}")

    return agents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents = generate_agents_from_pemukiman(None, agents_per_pemukiman=10)
    print(f"Generated {len(agents)} agents")
