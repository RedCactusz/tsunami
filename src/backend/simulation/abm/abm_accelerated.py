"""
============================================================================
ABM GPU ACCELERATOR — CUDA/CuPy acceleration for Evacuation ABM
============================================================================
Menggunakan RTX 3060 GPU untuk mempercepat:
1. Flood grid parsing (wave_frames → flood cells)
2. Batch nearest-node lookup (KDTree GPU)
3. Batch flood checking per timestep
4. Batch agent position updates

Fallback: NumPy + scipy jika CUDA tidak tersedia
============================================================================
"""

import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger(__name__)

# ── GPU availability ──
try:
    import cupy as cp
    CUPY_AVAILABLE = True
    GPU_NAME = cp.cuda.Device(0).attributes.get('DeviceName', 'Unknown GPU')
    logger.info(f"ABM GPU: CuPy available — {GPU_NAME}")
except Exception:
    CUPY_AVAILABLE = False
    cp = None

try:
    from scipy.spatial import cKDTree
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def get_abm_gpu_status() -> Dict:
    """Return GPU status for ABM acceleration."""
    status = {
        "cupy_available": CUPY_AVAILABLE,
        "scipy_available": SCIPY_AVAILABLE,
        "gpu_name": None,
        "gpu_memory_mb": 0,
    }
    if CUPY_AVAILABLE:
        try:
            dev = cp.cuda.Device(0)
            mem = dev.mem_info
            status["gpu_name"] = str(dev)
            status["gpu_memory_mb"] = int(mem[1] / 1024 / 1024)
        except Exception:
            pass
    return status


# ============================================================================
# 1. GPU-ACCELERATED FLOOD GRID PARSING
# ============================================================================

def parse_wave_frames_gpu(wave_frames: List[Dict], ny: int, nx: int,
                          flood_threshold: float = 0.1
                          ) -> Tuple[Dict[float, Set], Dict[Tuple[int,int], float]]:
    """
    Parse wave_frames into flood_grids and wave_arrival using GPU.
    
    Returns:
        flood_grids: {t_min -> set((j, i))}
        wave_arrival: {(j, i) -> first_arrival_t_min}
    """
    flood_grids = {}
    wave_arrival = {}
    
    if not wave_frames or ny < 2 or nx < 2:
        return flood_grids, wave_arrival
    
    use_gpu = CUPY_AVAILABLE and ny * nx > 5000  # GPU worth it for large grids
    xp = cp if use_gpu else np
    
    if use_gpu:
        logger.info(f"ABM GPU: Parsing {len(wave_frames)} frames ({ny}x{nx}) on GPU")
    
    # Track first arrival per cell
    arrival_grid = xp.full((ny, nx), xp.inf, dtype=xp.float32)
    
    for frame in wave_frames:
        t_min = frame.get('t_min', 0) if isinstance(frame, dict) else 0
        eta_flat = frame.get('eta_flat', []) if isinstance(frame, dict) else frame
        
        if not eta_flat:
            continue
        
        # Convert to array on GPU/CPU
        try:
            eta_arr = xp.array(eta_flat, dtype=xp.float32)
            if len(eta_arr) != ny * nx:
                # Try reshape if size matches approximately
                if len(eta_arr) > ny * nx:
                    eta_arr = eta_arr[:ny * nx]
                else:
                    continue
            eta_2d = eta_arr.reshape(ny, nx)
        except Exception:
            continue
        
        # Find flooded cells (|eta| >= threshold)
        flooded_mask = xp.abs(eta_2d) >= flood_threshold
        
        # Update wave arrival (only for first time)
        newly_flooded = flooded_mask & (arrival_grid == xp.inf)
        arrival_grid[newly_flooded] = t_min
        
        # Extract flooded cell indices
        if use_gpu:
            flooded_idx = cp.asnumpy(xp.argwhere(flooded_mask))
        else:
            flooded_idx = np.argwhere(flooded_mask)
        
        flood_grids[t_min] = set(map(tuple, flooded_idx))
    
    # Convert arrival grid to dict
    if use_gpu:
        arrival_np = cp.asnumpy(arrival_grid)
    else:
        arrival_np = arrival_grid
    
    valid_mask = arrival_np < np.inf
    valid_idx = np.argwhere(valid_mask)
    for j, i in valid_idx:
        wave_arrival[(int(j), int(i))] = float(arrival_np[j, i])
    
    logger.info(f"ABM {'GPU' if use_gpu else 'CPU'}: "
                f"{len(flood_grids)} frames parsed, "
                f"{len(wave_arrival)} wave arrival cells")
    
    return flood_grids, wave_arrival


# ============================================================================
# 2. GPU-ACCELERATED NEAREST NODE (KDTree + batch)
# ============================================================================

class GPUNodeIndex:
    """
    Spatial index for graph nodes using KDTree + optional GPU batch queries.
    Replaces O(N) brute-force nearest_node() with O(log N) KDTree.
    """
    
    def __init__(self, nodes: Dict[int, Tuple[float, float]]):
        """
        Args:
            nodes: {node_id: (lat, lon)}
        """
        self.node_ids = list(nodes.keys())
        self.coords = np.array([(nodes[nid][0], nodes[nid][1]) for nid in self.node_ids],
                               dtype=np.float64)
        self._tree = None
        
        if SCIPY_AVAILABLE and len(self.node_ids) > 0:
            self._tree = cKDTree(self.coords)
            logger.info(f"GPUNodeIndex: KDTree built with {len(self.node_ids)} nodes")
    
    def nearest(self, lat: float, lon: float, max_dist_deg: float = 0.05) -> Optional[int]:
        """Find nearest node — O(log N) with KDTree."""
        if self._tree is None:
            return self._brute_force(lat, lon)
        
        dist, idx = self._tree.query([lat, lon], distance_upper_bound=max_dist_deg)
        if dist == float('inf'):
            return None
        return self.node_ids[idx]
    
    def nearest_batch(self, points: np.ndarray, max_dist_deg: float = 0.05) -> List[Optional[int]]:
        """
        Batch nearest-node lookup for multiple points.
        
        Args:
            points: np.ndarray of shape (N, 2) → [(lat, lon), ...]
        
        Returns:
            List of node_ids (None if no node within max_dist)
        """
        if self._tree is None or len(points) == 0:
            return [self._brute_force(p[0], p[1]) for p in points]
        
        dists, idxs = self._tree.query(points, distance_upper_bound=max_dist_deg)
        
        results = []
        for d, i in zip(dists, idxs):
            if d == float('inf') or i >= len(self.node_ids):
                results.append(None)
            else:
                results.append(self.node_ids[i])
        return results
    
    def _brute_force(self, lat, lon):
        """Fallback brute force."""
        if len(self.coords) == 0:
            return None
        diffs = self.coords - np.array([lat, lon])
        dists = np.sum(diffs ** 2, axis=1)
        idx = np.argmin(dists)
        return self.node_ids[idx]


# ============================================================================
# 3. GPU-ACCELERATED BATCH FLOOD CHECK
# ============================================================================

def batch_flood_check_gpu(agent_lats: np.ndarray, agent_lons: np.ndarray,
                          t_min: float, grid_meta: Dict,
                          flood_grids: Dict[float, Set]) -> np.ndarray:
    """
    Check flood status for ALL agents in one vectorized operation.
    
    Returns:
        np.ndarray of bool — True if agent at that position is flooded
    """
    n = len(agent_lats)
    if n == 0 or not grid_meta or not flood_grids:
        return np.zeros(n, dtype=bool)
    
    lat_min = grid_meta.get('lat_min', 0)
    lat_max = grid_meta.get('lat_max', 0)
    lon_min = grid_meta.get('lon_min', 0)
    lon_max = grid_meta.get('lon_max', 0)
    ny = grid_meta.get('ny', 1)
    nx = grid_meta.get('nx', 1)
    
    lat_range = max(lat_max - lat_min, 1e-9)
    lon_range = max(lon_max - lon_min, 1e-9)
    
    # Find the relevant flood frame
    avail = sorted([t for t in flood_grids if t <= t_min], reverse=True)
    if not avail:
        return np.zeros(n, dtype=bool)
    
    flooded_cells = flood_grids[avail[0]]
    if not flooded_cells:
        return np.zeros(n, dtype=bool)
    
    use_gpu = CUPY_AVAILABLE and n > 500
    xp = cp if use_gpu else np
    
    # Convert to arrays
    lats = xp.asarray(agent_lats, dtype=xp.float32) if use_gpu else agent_lats.astype(np.float32)
    lons = xp.asarray(agent_lons, dtype=xp.float32) if use_gpu else agent_lons.astype(np.float32)
    
    # Compute grid indices for all agents at once
    js = xp.clip(((lats - lat_min) / lat_range * (ny - 1)).astype(xp.int32), 0, ny - 1)
    is_ = xp.clip(((lons - lon_min) / lon_range * (nx - 1)).astype(xp.int32), 0, nx - 1)
    
    # Check bounds
    in_bounds = ((lats >= lat_min) & (lats <= lat_max) &
                 (lons >= lon_min) & (lons <= lon_max))
    
    if use_gpu:
        js_np = cp.asnumpy(js)
        is_np = cp.asnumpy(is_)
        in_bounds_np = cp.asnumpy(in_bounds)
    else:
        js_np, is_np, in_bounds_np = js, is_, in_bounds
    
    # Check each agent against flooded cells
    result = np.zeros(n, dtype=bool)
    for idx in range(n):
        if in_bounds_np[idx]:
            result[idx] = (int(js_np[idx]), int(is_np[idx])) in flooded_cells
    
    return result


# ============================================================================
# 4. GPU-ACCELERATED AGENT BATCH UPDATE
# ============================================================================

def batch_update_agents_gpu(
    agent_dists: np.ndarray,       # current distance covered
    agent_speeds: np.ndarray,      # speed m/s per agent
    agent_path_lengths: np.ndarray, # total path distance per agent
    agent_statuses: np.ndarray,    # 0=waiting, 1=moving, 2=arrived, 3=stranded
    agent_delays: np.ndarray,      # response delay (seconds)
    agent_wave_arrivals: np.ndarray, # wave arrival time (minutes), inf if none
    current_time_s: float,
    warning_time_s: float,
    dt_s: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Batch update ALL agent positions and statuses in one vectorized operation.
    
    Status codes: 0=waiting, 1=moving, 2=arrived, 3=stranded
    
    Returns:
        (new_statuses, new_dists, progress_pct)
    """
    n = len(agent_dists)
    if n == 0:
        return agent_statuses.copy(), agent_dists.copy(), np.zeros(0)
    
    use_gpu = CUPY_AVAILABLE and n > 200
    xp = cp if use_gpu else np
    
    # Transfer to GPU if needed
    dists = xp.asarray(agent_dists, dtype=xp.float32)
    speeds = xp.asarray(agent_speeds, dtype=xp.float32)
    path_lens = xp.asarray(agent_path_lengths, dtype=xp.float32)
    statuses = xp.asarray(agent_statuses, dtype=xp.int32)
    delays = xp.asarray(agent_delays, dtype=xp.float32)
    wave_arr = xp.asarray(agent_wave_arrivals, dtype=xp.float32)
    
    current_time_min = current_time_s / 60.0
    new_statuses = statuses.copy()
    new_dists = dists.copy()
    
    # ── Calculate time to tsunami arrival ──
    time_to_arrival = wave_arr - current_time_min
    
    # ── Wave arrival stranding (vectorized) ──
    # Agent stranded if wave has been here for more than 2 minutes
    wave_strand_mask = ((wave_arr < xp.inf) & 
                        (time_to_arrival <= -2.0) & 
                        (statuses != 2))  # not arrived
    new_statuses[wave_strand_mask] = 3  # stranded
    
    # ── Waiting → Moving transition (vectorized) ──
    can_move = ((statuses == 0) & 
                (current_time_s >= warning_time_s + delays) &
                (new_statuses != 3))
    new_statuses[can_move] = 1  # moving
    
    # ── Dynamic Speed Multipliers (Adaptive Speed) ──
    speed_mult = xp.ones_like(speeds)
    
    # Wading: caught in water (0 to -2 mins) -> 50% speed
    wading_mask = (time_to_arrival <= 0.0) & (time_to_arrival > -2.0)
    speed_mult[wading_mask] = 0.5
    
    # Sprinting / Hurrying: wave is coming soon (< 10 mins) -> 1.5x speed
    sprinting_mask = (time_to_arrival > 0.0) & (time_to_arrival <= 10.0)
    speed_mult[sprinting_mask] = 1.5
    
    # ── Moving agents: advance distance (vectorized) ──
    moving_mask = (new_statuses == 1)
    step_dist = (speeds * speed_mult) * dt_s
    new_dists[moving_mask] += step_dist[moving_mask]
    
    # ── Check arrivals (vectorized) ──
    arrived_mask = moving_mask & (new_dists >= path_lens) & (path_lens > 0)
    new_statuses[arrived_mask] = 2  # arrived
    
    # ── Progress percentage ──
    progress = xp.where(path_lens > 0, new_dists / path_lens * 100.0, 0.0)
    progress = xp.clip(progress, 0, 100)
    
    # Transfer back to CPU
    if use_gpu:
        return (cp.asnumpy(new_statuses), 
                cp.asnumpy(new_dists), 
                cp.asnumpy(progress))
    return new_statuses, new_dists, progress


# ============================================================================
# 5. GPU-ACCELERATED FLOOD EDGE MARKING
# ============================================================================

def mark_flooded_edges_gpu(node_coords: Dict[int, Tuple[float, float]],
                            edge_list: List[Tuple[int, int]],
                            flood_points_tree,
                            flood_radius_deg: float = 0.002) -> Set[Tuple[int, int]]:
    """
    Mark edges whose midpoints fall within flood zones using batch KDTree query.
    Much faster than per-edge point-in-polygon for large graphs.
    
    Returns:
        Set of (u, v) edge tuples that are flooded
    """
    if not edge_list or flood_points_tree is None:
        return set()
    
    # Compute midpoints of all edges
    midpoints = np.zeros((len(edge_list), 2), dtype=np.float64)
    for idx, (u, v) in enumerate(edge_list):
        if u in node_coords and v in node_coords:
            lat1, lon1 = node_coords[u]
            lat2, lon2 = node_coords[v]
            midpoints[idx] = [0.5 * (lat1 + lat2), 0.5 * (lon1 + lon2)]
    
    # Batch KDTree query — all midpoints at once
    dists, _ = flood_points_tree.query(midpoints, distance_upper_bound=flood_radius_deg)
    
    # Mark edges within flood radius
    flooded_edges = set()
    for idx, d in enumerate(dists):
        if d != float('inf'):
            flooded_edges.add(edge_list[idx])
    
    logger.info(f"GPU edge flood marking: {len(flooded_edges)}/{len(edge_list)} edges flooded")
    return flooded_edges


# ============================================================================
# MODULE INFO
# ============================================================================

__version__ = "1.0.0"
__all__ = [
    'get_abm_gpu_status',
    'parse_wave_frames_gpu',
    'GPUNodeIndex',
    'batch_flood_check_gpu',
    'batch_update_agents_gpu',
    'mark_flooded_edges_gpu',
    'CUPY_AVAILABLE',
]
