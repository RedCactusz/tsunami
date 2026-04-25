"""
============================================================================
SWE TSUNAMI SOLVER - REAL BATHYMETRY ONLY
============================================================================
Shallow Water Equations solver untuk simulasi tsunami.

PENTING: Solver ini HANYA menggunakan data bathymetry REAL dari:
- BATNAS (Nasional Bathymetry - BIG)
- DEMNAS (Nasional DEM - BIG)
- GEBCO (fallback untuk deep sea)

❌ TIDAK ADA SYNTHETIC BATHYMETRY
✅ SEMUA data dari sumber real

Metodologi: COMCOT (Wang 2009) equivalent
Referensi: Okada (1985), Synolakis (1987)

Author: Kelompok 3 - Mini Project Komputasi Geospasial S2 Geomatika UGM
Version: 2.0.0 (Refactored, No Synthetic Data)
============================================================================
"""

import math
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

import numpy as np

from ..core import (
    haversine_m, haversine_vectorized,
    GRAVITY, EARTH_RADIUS_M, DEG_TO_RAD,
    create_grid, bilinear_interpolation, nearest_neighbor_fill,
    wave_speed, abe_initial_height, synolakis_runup,
    geometric_spreading_decay, fault_efficiency,
    safe_divide, clamp, sanitize_depth,
    describe_array, validate_coordinates
)

# Optional: Numba JIT untuk performance
try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def wrapper(func):
            return func
        return wrapper if not args else args[0]
    prange = range

try:
    from scipy.ndimage import distance_transform_edt
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Import acceleration strategies (optional)
try:
    from .swe_accelerated import select_strategy, swe_step_numpy, swe_step_numba, swe_step_cupy, CUPY_AVAILABLE
    ACCELERATION_AVAILABLE = True
except ImportError:
    ACCELERATION_AVAILABLE = False
    CUPY_AVAILABLE = False
    select_strategy = None
    swe_step_numpy = None
    swe_step_numba = None
    swe_step_cupy = None

try:
    import cupy as cp
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ============================================================================
# KONSTANTA FISIKA
# ============================================================================
RIGIDITY_MU = 40e9
POISSON_NU = 0.25

DEFAULT_DOMAIN = {
    'lat_min': -9.3,
    'lat_max': -7.75,
    'lon_min': 109.5,
    'lon_max': 110.7,
    'dx_deg': 0.005
}

NEARSHORE_DEPTH_THRESHOLD = 50.0

MANNING_COEFFS = {
    'open_ocean': 0.013,
    'shoreline': 0.025,
    'water_body': 0.007,
    'shrub': 0.040,
    'forest': 0.070,
    'orchard': 0.035,
    'open_land': 0.015,
    'agriculture': 0.025,
    'settlement': 0.045,
    'mangrove': 0.025,
    'fish_pond': 0.010
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class FaultParameters:
    strike: float
    dip: float
    rake: float
    length_km: float
    width_km: float
    slip_m: float
    depth_top_km: float
    epicenter_lat: float
    epicenter_lon: float
    magnitude: float
    fault_type: str = "thrust"


@dataclass
class SimulationConfig:
    duration_min: float = 60.0
    dt_auto: bool = True
    dt_fixed: float = 2.0
    output_interval_sec: float = 30.0
    use_nonlinear: bool = True
    use_friction: bool = True
    sponge_cells: int = 5
    coarse_mode: bool = True
    resolution_mode: str = 'auto'
    domain: Dict[str, float] = field(default_factory=lambda: DEFAULT_DOMAIN.copy())


@dataclass
class SWEResults:
    wave_frames: List[np.ndarray]
    time_stamps: List[float]
    max_wave_height: np.ndarray
    arrival_time: np.ndarray
    max_runup_m: float
    inundation_area_km2: float
    affected_villages: List[Dict]
    statistics: Dict[str, Any]
    grid_info: Dict[str, Any]


# ============================================================================
# OKADA (1985) - SEAFLOOR DEFORMATION
# ============================================================================

class OkadaSolver:
    """Analytical Okada (1985) untuk deformasi seafloor."""
    
    def __init__(self, poisson_ratio: float = POISSON_NU):
        self.nu = poisson_ratio
    
    def compute_deformation(self, fault: FaultParameters,
                              lon_grid: np.ndarray, 
                              lat_grid: np.ndarray) -> np.ndarray:
        """
        Hitung displacement vertikal (Uz) pada grid.
        
        Returns:
            Uz: Array 2D displacement vertikal (meter)
        """
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(fault.epicenter_lat * DEG_TO_RAD)
        
        X = (lon_grid - fault.epicenter_lon) * m_per_deg_lon
        Y = (lat_grid - fault.epicenter_lat) * m_per_deg_lat
        
        strike_rad = fault.strike * DEG_TO_RAD
        cos_s = math.cos(strike_rad)
        sin_s = math.sin(strike_rad)
        
        X_rot = X * cos_s + Y * sin_s
        Y_rot = -X * sin_s + Y * cos_s
        
        L = fault.length_km * 1000.0
        W = fault.width_km * 1000.0
        d = fault.depth_top_km * 1000.0
        U = fault.slip_m
        
        dip_rad = fault.dip * DEG_TO_RAD
        rake_rad = fault.rake * DEG_TO_RAD
        
        Uz = np.zeros_like(X_rot)
        
        corners = [
            (-L / 2, 0, 1),
            (L / 2, 0, -1),
            (-L / 2, W, -1),
            (L / 2, W, 1)
        ]
        
        for xi, eta, sign in corners:
            Uz += sign * self._okada_chinnery(
                X_rot - xi, Y_rot - eta * math.cos(dip_rad), d + eta * math.sin(dip_rad),
                dip_rad, rake_rad, U
            )
            
        # Kalibrasi amplitudo spasial Okada dengan rumus empiris Abe (1979)
        # H0 = 10^(0.5 * Mw - 3.2)
        H0 = 10**(0.5 * fault.magnitude - 3.2)
        
        # Faktor efisiensi tsunamigenik berdasarkan mekanisme sesar (rake)
        # - Thrust/reverse (rake≈90°): sin²(90°) = 1.0 → displacement vertikal penuh
        # - Strike-slip   (rake≈0°):  sin²(0°)  = 0.0 → displacement vertikal minimal
        # - Oblique        (rake≈45°): sin²(45°) = 0.5 → campuran
        # Minimum 0.05 agar strike-slip tetap menghasilkan deformasi kecil (realistis)
        rake_rad = fault.rake * DEG_TO_RAD
        tsunami_efficiency = max(math.sin(rake_rad) ** 2, 0.05)
        H0_effective = H0 * tsunami_efficiency
        
        max_uz = np.max(np.abs(Uz))
        if max_uz > 0:
            Uz = Uz * (H0_effective / max_uz)
        
        return Uz
    
    def _okada_chinnery(self, x: np.ndarray, y: np.ndarray, d: float,
                         dip: float, rake: float, U: float) -> np.ndarray:
        """Chinnery's notation untuk Okada integrals."""
        sin_d = math.sin(dip)
        cos_d = math.cos(dip)
        sin_r = math.sin(rake)
        cos_r = math.cos(rake)
        
        p = y * cos_d + d * sin_d
        q = y * sin_d - d * cos_d
        
        R = np.sqrt(x ** 2 + p ** 2 + q ** 2)
        R = np.where(R < 1e-6, 1e-6, R)
        
        # Strike-slip vertical component
        uz_ss = -U * cos_r / (2 * math.pi) * (
            q * sin_d / R + 
            np.arctan(x * y / (q * R + 1e-10))
        )
        
        # Dip-slip vertical component
        uz_ds = -U * sin_r / (2 * math.pi) * (
            q * cos_d / R - 
            sin_d * np.log(R + p + 1e-10) +
            (y * sin_d - d * cos_d) / (R + 1e-10)
        )
        
        return uz_ss + uz_ds


# ============================================================================
# BATHYMETRY HANDLER - REAL DATA ONLY (NO SYNTHETIC!)
# ============================================================================

class RealBathymetryGrid:
    """
    Handler bathymetry grid yang HANYA menggunakan data REAL.
    
    Data sources (priority):
    1. BATNAS (Indonesia ocean - highest resolution)
    2. DEMNAS (land elevation)
    3. GEBCO (deep sea fallback)
    
    ❌ NO SYNTHETIC BATHYMETRY
    """
    
    def __init__(self, batnas_manager=None, dem_manager=None, gebco_reader=None):
        self.batnas = batnas_manager
        self.dem = dem_manager
        self.gebco = gebco_reader
        
        if not any([self.batnas, self.dem, self.gebco]):
            raise ValueError(
                "❌ No real bathymetry data source available!\n"
                "Required: BATNAS, DEMNAS, or GEBCO.\n"
                "Synthetic bathymetry is DISABLED for scientific accuracy."
            )
        
        logger.info(f"RealBathymetryGrid initialized: "
                    f"BATNAS={bool(self.batnas)}, DEM={bool(self.dem)}, "
                    f"GEBCO={bool(self.gebco)}")
    
    def build_grid(self, domain: Dict[str, float]) -> Dict[str, np.ndarray]:
        """
        Build unified bathymetry grid dari data real.
        
        Convention:
        - depth < 0: Ocean (kedalaman)
        - depth > 0: Land (elevasi)
        - depth = 0: Shoreline
        
        Returns:
            {
                'lons': 1D array,
                'lats': 1D array,
                'depth': 2D array (meter),
                'source_map': 2D array (0=missing, 1=BATNAS, 2=DEM, 3=GEBCO),
                'coverage_pct': float
            }
        
        Raises:
            ValueError: Jika coverage < 10% (data tidak cukup)
        """
        lons, lats, LON, LAT = create_grid(
            domain['lon_min'], domain['lon_max'],
            domain['lat_min'], domain['lat_max'],
            domain['dx_deg']
        )
        
        ny, nx = LAT.shape
        depth = np.full((ny, nx), np.nan, dtype=np.float64)
        source_map = np.zeros((ny, nx), dtype=np.uint8)
        
        logger.info(f"Building REAL bathymetry grid: {nx}x{ny} cells")
        
        # 3. Fill values (priority: BATNAS -> DEMNAS -> GEBCO)
        try:
            from swe_accelerated import BathyCache
            has_cache = True
        except ImportError:
            has_cache = False
            
        lat_arr = LAT[:, 0]
        lon_arr = LON[0, :]
        
        if self.batnas:
            logger.info("  [1/3] Filling from BATNAS (bulk)...")
            if has_cache:
                batnas_grid = BathyCache.get_instance().get_or_load('batnas', lat_arr, lon_arr, self.batnas)
                mask = np.isnan(depth) & (batnas_grid > -999.0)
                depth[mask] = batnas_grid[mask]
                filled_batnas = np.sum(mask)
            else:
                filled_batnas = 0
                for i in range(ny):
                    for j in range(nx):
                        if not np.isnan(depth[i, j]):
                            continue
                        val = self._safe_query(self.batnas, LAT[i, j], LON[i, j])
                        if val is not None:
                            depth[i, j] = val
                            filled_batnas += 1
            logger.info(f"        BATNAS filled {filled_batnas} cells")
        
        if self.dem:
            logger.info("  [2/3] Filling from DEMNAS (bulk)...")
            if has_cache:
                demnas_grid = BathyCache.get_instance().get_or_load('demnas', lat_arr, lon_arr, self.dem)
                mask = np.isnan(depth) & (demnas_grid > -999.0)
                depth[mask] = demnas_grid[mask]
                filled_demnas = np.sum(mask)
            else:
                filled_demnas = 0
                for i in range(ny):
                    for j in range(nx):
                        if not np.isnan(depth[i, j]):
                            continue
                        val = self._safe_query(self.dem, LAT[i, j], LON[i, j])
                        if val is not None:
                            depth[i, j] = val
                            filled_demnas += 1
            logger.info(f"        DEMNAS filled {filled_demnas} cells")
            
        if self.gebco:
            logger.info("  [3/3] Filling from GEBCO (bulk)...")
            if has_cache:
                gebco_grid = BathyCache.get_instance().get_or_load('gebco', lat_arr, lon_arr, self.gebco)
                mask = np.isnan(depth) & (gebco_grid > -999.0)
                depth[mask] = gebco_grid[mask]
                filled_gebco = np.sum(mask)
            else:
                filled_gebco = 0
                for i in range(ny):
                    for j in range(nx):
                        if not np.isnan(depth[i, j]):
                            continue
                        val = self._safe_query(self.gebco, LAT[i, j], LON[i, j])
                        if val is not None:
                            depth[i, j] = val
                            filled_gebco += 1
            logger.info(f"        GEBCO filled {filled_gebco} cells")
        
        # Validasi coverage
        total_cells = nx * ny
        filled_cells = np.sum(~np.isnan(depth))
        coverage_pct = 100.0 * filled_cells / total_cells
        
        logger.info(f"Coverage: {coverage_pct:.1f}% ({filled_cells}/{total_cells})")
        
        if coverage_pct < 10.0:
            raise ValueError(
                f"❌ Insufficient real data coverage: {coverage_pct:.1f}%\n"
                "Need at least 10% real bathymetry data. "
                "Please provide BATNAS, DEMNAS, or GEBCO for this domain."
            )
        
        # Fill remaining NaN via nearest-neighbor (dari data real, bukan synthetic)
        if filled_cells < total_cells:
            logger.info("  Filling gaps via nearest-neighbor from REAL data...")
            mask = ~np.isnan(depth)
            depth = self._nn_fill(depth, mask)
        
        return {
            'lons': lons,
            'lats': lats,
            'depth': depth,
            'source_map': source_map,
            'coverage_pct': coverage_pct,
            'shape': (ny, nx),
            'dx_deg': domain['dx_deg']
        }
    
    def _safe_query(self, source, lat: float, lon: float) -> Optional[float]:
        """Query depth dari source dengan error handling."""
        try:
            if hasattr(source, 'query_depth'):
                return source.query_depth(lat, lon)
            elif hasattr(source, 'query_elevation'):
                return source.query_elevation(lat, lon)
            elif hasattr(source, 'get_value'):
                return source.get_value(lat, lon)
            elif callable(source):
                return source(lat, lon)
        except Exception as e:
            logger.debug(f"Query failed at ({lat}, {lon}): {e}")
        return None
    
    def _nn_fill(self, grid: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Fill NaN menggunakan nearest-neighbor dari REAL data."""
        if SCIPY_AVAILABLE:
            _, (yi, xi) = distance_transform_edt(~mask, return_indices=True)
            return grid[yi, xi]
        else:
            return nearest_neighbor_fill(grid, mask)


# ============================================================================
# MANNING ROUGHNESS GRID
# ============================================================================

class ManningGrid:
    """Build Manning's roughness grid dari OSM landuse atau default."""
    
    def __init__(self, osm_fetcher=None):
        self.osm_fetcher = osm_fetcher
    
    def build_grid(self, bathy_grid: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Build Manning roughness grid.
        
        Default logic:
        - Ocean (depth < 0): open_ocean = 0.013
        - Shoreline (-5 < depth < 5): shoreline = 0.025
        - Land (depth > 0): settlement = 0.045 (conservative untuk Bantul)
        """
        depth = bathy_grid['depth']
        manning = np.full_like(depth, MANNING_COEFFS['open_ocean'])
        
        # Shoreline zone
        shoreline_mask = (depth > -5) & (depth < 5)
        manning[shoreline_mask] = MANNING_COEFFS['shoreline']
        
        # Land zone (default settlement)
        land_mask = depth >= 5
        manning[land_mask] = MANNING_COEFFS['settlement']
        
        # TODO: Override dengan OSM landuse jika tersedia
        if self.osm_fetcher:
            try:
                self._apply_osm_landuse(manning, bathy_grid)
            except Exception as e:
                logger.warning(f"OSM landuse overlay failed: {e}")
        
        return manning
    
    def _apply_osm_landuse(self, manning: np.ndarray, bathy_grid: Dict):
        """Apply OSM landuse polygons untuk override default Manning."""
        # Implementation bergantung pada struktur osm_fetcher
        pass


# Linear SWE step logic moved to swe_accelerated.py


class LinearSWESolver:
    """Linear SWE solver dengan leap-frog FD pada C-grid."""
    
    def __init__(self, bathy_grid: Dict, manning_grid: np.ndarray,
                   config: SimulationConfig):
        self.bathy = bathy_grid
        self.manning = manning_grid
        self.config = config
        
        self.lons = bathy_grid['lons']
        self.lats = bathy_grid['lats']
        self.depth = bathy_grid['depth']
        
        self.ny, self.nx = self.depth.shape
        
        # H = still water depth (positif di laut)
        self.H = np.where(self.depth < 0, -self.depth, 0.0)
        
        # dx, dy dalam meter
        lat_mid = 0.5 * (self.lats[0] + self.lats[-1])
        self.dx = config.domain['dx_deg'] * 111_320.0 * math.cos(lat_mid * DEG_TO_RAD)
        self.dy = config.domain['dx_deg'] * 111_320.0
        
        # CFL timestep
        h_max = float(np.max(self.H))
        c_max = wave_speed(h_max)
        if config.dt_auto:
            self.dt = max(0.5, min(0.5 * min(self.dx, self.dy) / max(c_max, 1.0), 5.0))
        else:
            self.dt = config.dt_fixed
        
        self.strategy = select_strategy(min(self.dx, self.dy))
        logger.info(f"SWE Solver: {self.nx}x{self.ny}, dx={self.dx:.0f}m, "
                    f"dt={self.dt:.2f}s, h_max={h_max:.0f}m, c_max={c_max:.1f}m/s, strategy={self.strategy}")
    
    def run(self, initial_eta: np.ndarray) -> SWEResults:
        """
        Jalankan simulasi SWE dengan initial condition tertentu.
        
        Args:
            initial_eta: Displacement awal (dari Okada)
        
        Returns:
            SWEResults
        """
        eta = initial_eta.copy()
        u = np.zeros_like(eta)
        v = np.zeros_like(eta)
        
        # Tracking
        max_eta = np.abs(eta).copy()
        arrival = np.full_like(eta, -1.0)
        arrival[np.abs(eta) > 0.1] = 0.0
        
        # Output frames
        wave_frames = [eta.copy()]
        time_stamps = [0.0]
        
        total_time = self.config.duration_min * 60.0
        n_steps = int(total_time / self.dt)
        output_interval_steps = max(1, int(self.config.output_interval_sec / self.dt))
        
        logger.info(f"Running {n_steps} steps ({total_time}s simulation)...")
        
        sponge = self._build_sponge_layer()
        if self.strategy == 'cupy':
            eta_gpu = cp.asarray(eta)
            u_gpu = cp.asarray(u)
            v_gpu = cp.asarray(v)
            H_gpu = cp.asarray(self.H)
            manning_gpu = cp.asarray(self.manning)
            sponge_gpu = cp.asarray(sponge)
            max_eta_gpu = cp.asarray(max_eta)
            arrival_gpu = cp.asarray(arrival)

        for step in range(1, n_steps + 1):
            if self.strategy == 'numpy':
                eta, u, v = swe_step_numpy(
                    eta, u, v, self.H, self.manning,
                    self.dt, self.dx, self.dy, GRAVITY, self.config.use_friction
                )
            elif self.strategy == 'numba':
                eta, u, v = swe_step_numba(
                    eta, u, v, self.H, self.manning,
                    self.dt, self.dx, self.dy, GRAVITY, self.config.use_friction
                )
            elif self.strategy == 'cupy':
                eta_gpu, u_gpu, v_gpu = swe_step_cupy(
                    eta_gpu, u_gpu, v_gpu, H_gpu, manning_gpu,
                    self.dt, self.dx, self.dy, GRAVITY, self.config.use_friction
                )
            
            # Apply sponge boundary
            if self.strategy == 'cupy':
                eta_gpu *= sponge_gpu
                u_gpu *= sponge_gpu
                v_gpu *= sponge_gpu
                
                abs_eta = cp.abs(eta_gpu)
                max_eta_gpu = cp.maximum(max_eta_gpu, abs_eta)
                new_arrivals = (arrival_gpu < 0) & (abs_eta > 0.1)
                arrival_gpu[new_arrivals] = step * self.dt
            else:
                eta *= sponge
                u *= sponge
                v *= sponge
                
                abs_eta = np.abs(eta)
                max_eta = np.maximum(max_eta, abs_eta)
                new_arrivals = (arrival < 0) & (abs_eta > 0.1)
                arrival[new_arrivals] = step * self.dt
            
            # Save frame
            if step % output_interval_steps == 0:
                if self.strategy == 'cupy':
                    wave_frames.append(cp.asnumpy(eta_gpu).copy())
                else:
                    wave_frames.append(eta.copy())
                time_stamps.append(step * self.dt)
            
            if step % 100 == 0:
                if self.strategy == 'cupy':
                    logger.debug(f"  Step {step}/{n_steps}, max|eta|={float(cp.max(abs_eta)):.2f}m")
                else:
                    logger.debug(f"  Step {step}/{n_steps}, max|eta|={np.max(abs_eta):.2f}m")
        
        if self.strategy == 'cupy':
            max_eta = cp.asnumpy(max_eta_gpu)
            arrival = cp.asnumpy(arrival_gpu)
        
        # Ekstrapolasi inundasi ke darat (Bathtub model)
        max_eta = self._apply_bathtub_inundation(max_eta)
        # Calculate runup & inundation
        max_runup = self._calculate_runup(max_eta)
        inundation_km2 = self._calculate_inundation_area(max_eta)
        
        # Statistics
        valid_eta_mask = max_eta > 0.01
        mean_eta = float(np.mean(max_eta[valid_eta_mask])) if np.any(valid_eta_mask) else 0.0
        
        stats = {
            'max_wave_height_m': float(np.max(max_eta)),
            'mean_wave_height_m': mean_eta,
            'simulation_steps': n_steps,
            'dt_seconds': self.dt,
            'grid_resolution_m': self.dx,
            'numba_enabled': NUMBA_AVAILABLE
        }
        
        return SWEResults(
            wave_frames=wave_frames,
            time_stamps=time_stamps,
            max_wave_height=max_eta,
            arrival_time=arrival,
            max_runup_m=max_runup,
            inundation_area_km2=inundation_km2,
            affected_villages=self._assess_villages(max_eta),
            statistics=stats,
            grid_info={
                'lons': self.lons.tolist(),
                'lats': self.lats.tolist(),
                'shape': [self.ny, self.nx],
                'dx_deg': self.config.domain['dx_deg']
            }
        )
        
    def _assess_villages(self, max_eta: np.ndarray) -> List[Dict]:
        """
        Nilai dampak gelombang per desa menggunakan InundationConnector.
        Prioritas: shapefile Administrasi_Desa → fallback Bantul statis.
        """
        if max_eta is None or max_eta.size == 0:
            logger.warning("[Villages] max_eta kosong, skip")
            return []

        # Gunakan InundationConnector jika tersedia
        try:
            from inundation_connector import InundationConnector, affected_villages_from_inundation
            connector = InundationConnector(
                desa_shp_path=getattr(self, '_desa_shp_path', None),
                dem_manager=getattr(self, '_dem_manager', None),
            )
            desa_list = connector._load_desa()
            depth_proxy = np.where(self.depth >= 0, self.depth, -100.0).astype(np.float32)
            per_desa = connector._assess_villages(
                max_eta, self.lats, self.lons, depth_proxy, desa_list
            )
            results = []
            for name, info in per_desa.items():
                if info.wave_height_m < 0.05:
                    continue
                results.append({
                    'desa':          info.name,
                    'name':          info.name,
                    'lat':           info.lat,
                    'lon':           info.lon,
                    'latitude':      info.lat,
                    'longitude':     info.lon,
                    'population':    info.population,
                    'terdampak':     info.terdampak,
                    'percentage':    min(100, int(info.wave_height_m * 20)),
                    'wave_height_m': info.wave_height_m,
                    'danger_zone':   info.danger_zone,
                    'zona_bahaya':   info.danger_zone,
                    'dist_km':       info.dist_coast_km,
                    'coordinates':   [info.lat, info.lon],
                })
            logger.info(f"[Villages] InundationConnector: {len(results)} desa terdampak")
            return results
        except Exception as e:
            logger.warning(f"[Villages] InundationConnector gagal ({e}), pakai fallback statis")

        # Fallback statis — pesisir Bantul
        villages_static = [
            {'name': 'Gadingsari',  'population': 4250, 'lat': -7.998, 'lon': 110.267},
            {'name': 'Srigading',   'population': 3820, 'lat': -7.985, 'lon': 110.285},
            {'name': 'Tirtosari',   'population': 3100, 'lat': -7.975, 'lon': 110.255},
            {'name': 'Poncosari',   'population': 5640, 'lat': -7.963, 'lon': 110.298},
            {'name': 'Trimurti',    'population': 2900, 'lat': -7.952, 'lon': 110.244},
            {'name': 'Banaran',     'population': 4100, 'lat': -7.941, 'lon': 110.311},
            {'name': 'Palbapang',   'population': 3600, 'lat': -7.930, 'lon': 110.280},
            {'name': 'Sabdodadi',   'population': 2800, 'lat': -7.920, 'lon': 110.262},
            {'name': 'Srandakan',   'population': 3200, 'lat': -7.935, 'lon': 110.253},
            {'name': 'Srihardono',  'population': 3500, 'lat': -7.912, 'lon': 110.278},
        ]
        results = []
        lat_min, lat_max = float(self.lats.min()), float(self.lats.max())
        lon_min, lon_max = float(self.lons.min()), float(self.lons.max())

        for v in villages_static:
            vlat, vlon = v['lat'], v['lon']
            if not (lat_min <= vlat <= lat_max and lon_min <= vlon <= lon_max):
                continue
            j = int(np.argmin(np.abs(self.lats - vlat)))
            i = int(np.argmin(np.abs(self.lons - vlon)))
            wh = float(max_eta[j, i])
            if wh < 0.05:
                continue
            pct = min(100, int(wh * 20))
            zone = ('Ekstrem' if wh >= 6 else 'Sangat Tinggi' if wh >= 3 else
                    'Tinggi' if wh >= 1.5 else 'Sedang' if wh >= 0.5 else 'Rendah')
            results.append({
                'desa': v['name'], 'name': v['name'],
                'lat': vlat, 'lon': vlon,
                'latitude': vlat, 'longitude': vlon,
                'population': v['population'],
                'terdampak': int(v['population'] * pct / 100),
                'percentage': pct,
                'wave_height_m': round(wh, 2),
                'danger_zone': zone, 'zona_bahaya': zone,
                'dist_km': round(max(0.0, (vlat - (-8.03)) * 111.32), 2),
                'coordinates': [vlat, vlon],
            })
        return results

        return results
    
    def _build_sponge_layer(self) -> np.ndarray:
        """Absorbing boundary layer (sponge) untuk mencegah refleksi."""
        sponge = np.ones((self.ny, self.nx))
        n_sponge = self.config.sponge_cells
        
        for k in range(n_sponge):
            factor = (k / n_sponge) ** 2
            sponge[k, :] = factor
            sponge[-(k + 1), :] = factor
            sponge[:, k] = np.minimum(sponge[:, k], factor)
            sponge[:, -(k + 1)] = np.minimum(sponge[:, -(k + 1)], factor)
        
        return sponge
        
    def _apply_bathtub_inundation(self, max_eta: np.ndarray) -> np.ndarray:
        """
        Ekstrapolasi elevasi air ke daratan (land) karena linear SWE tidak merambat ke darat.
        Menggunakan pendekatan static inundation (Bathtub Model) berdasarkan max runup pantai.
        
        Perbaikan v5.2:
        - Runup PROPORSIONAL terhadap h_nearshore (bukan fixed cap 25m)
        - Distance-decay dari garis pantai menggunakan EDT
        - Mw 6.5 → runup ~5m, Mw 8.0 → ~15m, Mw 9.0 → ~30m
        """
        shoreline_mask = (self.depth >= -10) & (self.depth <= 2)
        if not np.any(shoreline_mask):
            logger.warning("[Bathtub] Tidak ada sel shoreline ditemukan (depth antara -10 dan 2).")
            return max_eta
            
        # Gunakan persentil 90 untuk menghindari outlier numerik
        shore_eta = max_eta[shoreline_mask]
        shore_eta_positive = shore_eta[shore_eta > 0.1]
        if shore_eta_positive.size == 0:
            logger.info("[Bathtub] Tidak ada gelombang signifikan di garis pantai.")
            return max_eta
        
        h_nearshore = float(np.percentile(shore_eta_positive, 90))
        logger.info(f"[Bathtub] h_nearshore (p90, raw) = {h_nearshore:.2f}m")
        
        if h_nearshore < 0.3:
            return max_eta
            
        runup_raw = synolakis_runup(h_nearshore, beach_slope=0.04, d_ref=10.0)
        # ✅ Cap PROPORSIONAL — bukan fixed 25m
        # Ini memastikan Mw kecil → runup kecil → inundasi kecil
        max_allowed = max(h_nearshore * 3.0, 5.0)  # Minimum 5m
        max_allowed = min(max_allowed, 45.0)        # Max fisika
        runup_max = min(runup_raw, max_allowed)
        logger.info(f"[Bathtub] runup_max = {runup_max:.2f}m (h_nearshore={h_nearshore:.2f}m, raw={runup_raw:.2f}m)")
        
        # Ekstrapolasi ke darat (kedalaman positif = elevasi darat)
        land_mask = self.depth >= 0
        inundated_eta = max_eta.copy()
        
        # Bathtub model dengan distance-decay dari garis pantai
        bathtub_mask = land_mask & (self.depth < runup_max)
        
        # Distance decay: genangan berkurang seiring jarak dari pantai
        if SCIPY_AVAILABLE:
            # EDT dari shoreline (unit: sel)
            from scipy.ndimage import distance_transform_edt
            shore_binary = (self.depth >= -10) & (self.depth <= 2)
            dist_from_shore = distance_transform_edt(~shore_binary)
            # Konversi jarak sel ke meter
            dist_m = dist_from_shore * min(self.dx, self.dy)
            # Penetrasi maksimum berdasarkan runup (empiris: ~20x runup = jarak penetrasi)
            max_penetration_m = runup_max * 20.0  # Referensi: FEMA P-646
            # Decay factor: linear dari 1.0 (di pantai) ke 0.0 (di batas penetrasi)
            decay = np.clip(1.0 - (dist_m / max(max_penetration_m, 1.0)), 0.0, 1.0)
        else:
            decay = np.ones_like(max_eta)

        flood_depth = np.maximum(0.0, runup_max - self.depth) * decay
        # Hanya terapkan di sel darat yang eligible
        update_mask = bathtub_mask & (flood_depth > inundated_eta)
        inundated_eta[update_mask] = flood_depth[update_mask]
        
        # Log seberapa banyak sel darat yang tergenang
        land_cells = int(np.sum(land_mask))
        flooded_cells = int(np.sum(update_mask))
        pct = (flooded_cells / max(land_cells, 1)) * 100
        logger.info(f"[Bathtub] Inundasi mengenai {flooded_cells} dari {land_cells} sel darat ({pct:.1f}%).")
        
        return inundated_eta
    
    def _calculate_runup(self, max_eta: np.ndarray) -> float:
        """Hitung maximum runup di sepanjang pantai."""
        # Find shoreline cells (depth ~ 0)
        shoreline_mask = (self.depth >= -20) & (self.depth <= 0)
        
        if not np.any(shoreline_mask):
            return 0.0
        
        # Gunakan p90 bukan max untuk menghindari artefak
        shore_vals = max_eta[shoreline_mask]
        shore_vals = shore_vals[shore_vals > 0.1]
        if shore_vals.size == 0:
            return 0.0
        
        h_nearshore = float(np.percentile(shore_vals, 90))
        
        runup = synolakis_runup(h_nearshore, beach_slope=0.04, d_ref=10.0)
        # ✅ Cap proporsional — bukan fixed 25m
        max_allowed = max(h_nearshore * 3.0, 5.0)
        max_allowed = min(max_allowed, 45.0)
        return min(runup, max_allowed)
    
    def _calculate_inundation_area(self, max_eta: np.ndarray) -> float:
        """Hitung luas area inundasi dalam km²."""
        # Land cells yang kebanjiran
        land_mask = self.depth >= 0
        inundated = land_mask & (max_eta > 0.5)  # Threshold 0.5m
        
        n_cells = int(np.sum(inundated))
        cell_area_km2 = (self.dx * self.dy) / 1e6
        
        return n_cells * cell_area_km2


# ============================================================================
# FAULT SCALING LAWS
# ============================================================================

def wells_coppersmith_scaling(magnitude: float, 
                                fault_type: str = "thrust") -> Dict[str, float]:
    """
    Wells & Coppersmith (1994) scaling relations.
    
    Returns:
        {length_km, width_km, slip_m}
    """
    mw = magnitude
    ft = fault_type.lower()
    
    if 'strike' in ft:
        log_L = 0.74 * mw - 3.55
        log_W = 0.27 * mw - 0.76
    elif 'normal' in ft:
        log_L = 0.50 * mw - 2.01
        log_W = 0.35 * mw - 1.14
    else:  # thrust / reverse / megathrust
        log_L = 0.63 * mw - 2.44
        log_W = 0.41 * mw - 1.61
    
    L = 10 ** log_L
    W = 10 ** log_W
    
    # Slip dari moment: M0 = mu * A * D
    # Mw = (2/3) * log10(M0) - 10.7
    M0 = 10 ** (1.5 * (mw + 10.7))  # dyne-cm
    M0_Nm = M0 * 1e-7
    A = L * W * 1e6  # m²
    slip = M0_Nm / (RIGIDITY_MU * A)
    
    return {'length_km': L, 'width_km': W, 'slip_m': slip}


def blaser_scaling(magnitude: float, fault_type: str = "thrust") -> Dict[str, float]:
    """Blaser et al. (2010) scaling untuk subduction zones."""
    mw = magnitude
    ft = fault_type.lower()
    
    if 'mega' in ft or 'thrust' in ft:
        log_L = 0.59 * mw - 2.44
        log_W = 0.31 * mw - 0.98
    else:
        return wells_coppersmith_scaling(mw, ft)
    
    L = 10 ** log_L
    W = 10 ** log_W
    
    M0_Nm = 10 ** (1.5 * (mw + 10.7)) * 1e-7
    A = L * W * 1e6
    slip = M0_Nm / (RIGIDITY_MU * A)
    
    return {'length_km': L, 'width_km': W, 'slip_m': slip}


# ============================================================================
# MAIN SOLVER ENTRY POINT
# ============================================================================

class TsunamiSWESolver:
    """
    Main entry point untuk SWE tsunami simulation.
    HANYA menggunakan REAL bathymetry data.
    """
    
    def __init__(self, batnas_manager=None, dem_manager=None,
                  gebco_reader=None, osm_fetcher=None,
                  desa_shp_path: str = None,
                  coastline_shp_path: str = None):
        """
        Args:
            batnas_manager:      BathyManager — sumber bathymetry laut
            dem_manager:         DEMManager — DEMNAS Bantul (elevasi darat)
            gebco_reader:        GEBCO reader — fallback laut dalam
            osm_fetcher:         OSM landuse fetcher (Manning override)
            desa_shp_path:       Path ke Administrasi_Desa.shp (untuk village assessment)
            coastline_shp_path:  Path ke Garis_Pantai_Selatan.shp (land/sea boundary)
        """
        self.bathy_handler = RealBathymetryGrid(
            batnas_manager=batnas_manager,
            dem_manager=dem_manager,
            gebco_reader=gebco_reader
        )
        self.manning_handler = ManningGrid(osm_fetcher=osm_fetcher)
        self.okada = OkadaSolver()
        self.desa_shp_path = desa_shp_path
        self.coastline_shp_path = coastline_shp_path
        self._dem_manager = dem_manager

        # Cache
        self._cached_bathy = None
        self._cached_manning = None
        self._cached_domain_key = None
    
    @staticmethod
    def auto_expand_domain(fault: 'FaultParameters', base_domain: Dict) -> Dict:
        """
        Auto-expand domain agar mencakup epicenter + buffer sampai daratan.
        Ini penting karena epicenter megathrust biasanya di laut selatan (-9°S)
        sementara daratan Bantul di -7.8°S sampai -7.9°S.
        """
        domain = base_domain.copy()
        epi_lat = fault.epicenter_lat
        epi_lon = fault.epicenter_lon
        
        # Pastikan epicenter masuk dalam domain + buffer 0.5°
        buffer_lat = 0.5
        buffer_lon = 0.5
        
        if epi_lat - buffer_lat < domain['lat_min']:
            domain['lat_min'] = epi_lat - buffer_lat
        if epi_lat + buffer_lat > domain['lat_max']:
            domain['lat_max'] = max(domain['lat_max'], epi_lat + buffer_lat)
        if epi_lon - buffer_lon < domain['lon_min']:
            domain['lon_min'] = epi_lon - buffer_lon
        if epi_lon + buffer_lon > domain['lon_max']:
            domain['lon_max'] = epi_lon + buffer_lon
        
        # Pastikan domain mencakup daratan Bantul
        domain['lat_max'] = max(domain['lat_max'], -7.75)
        domain['lon_min'] = min(domain['lon_min'], 110.0)
        domain['lon_max'] = max(domain['lon_max'], 110.6)
        
        # Auto-adjust dx agar grid tidak terlalu besar
        # GPU CuPy (RTX 3060 6GB) bisa handle ~500x500 = 250K sel
        lat_range = domain['lat_max'] - domain['lat_min']
        lon_range = domain['lon_max'] - domain['lon_min']
        max_cells_1d = 500
        min_dx = max(lat_range, lon_range) / max_cells_1d
        domain['dx_deg'] = max(domain['dx_deg'], min_dx, 0.003)
        
        logger.info(f"Auto-expanded domain: lat[{domain['lat_min']:.2f}, {domain['lat_max']:.2f}], "
                    f"lon[{domain['lon_min']:.2f}, {domain['lon_max']:.2f}], dx={domain['dx_deg']:.4f}°")
        return domain

    def simulate(self, fault: FaultParameters, 
                  config: Optional[SimulationConfig] = None) -> SWEResults:
        """
        Jalankan full tsunami simulation.
        
        Args:
            fault: Parameter fault
            config: Simulation config (opsional)
        
        Returns:
            SWEResults
        """
        if config is None:
            config = SimulationConfig()
        
        # Validate fault
        if not validate_coordinates(fault.epicenter_lat, fault.epicenter_lon):
            raise ValueError(f"Invalid epicenter: ({fault.epicenter_lat}, {fault.epicenter_lon})")
        
        # Auto-expand domain agar mencakup epicenter + daratan
        config.domain = self.auto_expand_domain(fault, config.domain)
        
        # Build / cache bathymetry grid
        domain_key = f"{config.domain['lon_min']}_{config.domain['lon_max']}_" \
                      f"{config.domain['lat_min']}_{config.domain['lat_max']}_" \
                      f"{config.domain['dx_deg']}"
        
        if self._cached_domain_key != domain_key:
            logger.info("Building REAL bathymetry grid (first time or domain changed)...")
            self._cached_bathy = self.bathy_handler.build_grid(config.domain)
            self._cached_manning = self.manning_handler.build_grid(self._cached_bathy)
            self._cached_domain_key = domain_key
        
        bathy_grid = self._cached_bathy
        manning_grid = self._cached_manning
        
        # Compute Okada initial deformation
        logger.info("Computing Okada seafloor deformation...")
        LON, LAT = np.meshgrid(bathy_grid['lons'], bathy_grid['lats'])
        initial_eta = self.okada.compute_deformation(fault, LON, LAT)
        
        # Apply fault efficiency (strike-slip = 4%, thrust = 100%)
        efficiency = fault_efficiency(fault.fault_type)
        initial_eta *= efficiency
        
        # Mask out land initial condition (only ocean cells)
        ocean_mask = bathy_grid['depth'] < 0
        initial_eta = np.where(ocean_mask, initial_eta, 0.0)
        
        logger.info(f"Initial deformation: max={np.max(initial_eta):.2f}m, "
                    f"min={np.min(initial_eta):.2f}m, efficiency={efficiency}")
        
        # Run SWE
        solver = LinearSWESolver(bathy_grid, manning_grid, config)
        # Teruskan path shapefile untuk village assessment
        solver._desa_shp_path = self.desa_shp_path
        solver._dem_manager  = self._dem_manager
        results = solver.run(initial_eta)
        
        # Enrich metadata
        results.statistics['fault_efficiency'] = efficiency
        results.statistics['fault_type'] = fault.fault_type
        results.statistics['magnitude'] = fault.magnitude
        results.statistics['bathymetry_sources'] = {
            'batnas': bool(self.bathy_handler.batnas),
            'demnas': bool(self.bathy_handler.dem),
            'gebco': bool(self.bathy_handler.gebco),
            'coverage_pct': bathy_grid['coverage_pct']
        }
        
        logger.info(f"✅ Simulation complete. Max wave: {results.statistics['max_wave_height_m']:.2f}m, "
                    f"Runup: {results.max_runup_m:.2f}m, "
                    f"Inundation: {results.inundation_area_km2:.2f}km²")
        
        return results
    
    def estimate_fault_from_magnitude(self, magnitude: float, 
                                        epicenter_lat: float, 
                                        epicenter_lon: float,
                                        fault_type: str = "thrust",
                                        use_blaser: bool = False,
                                        depth_top_km: Optional[float] = None) -> FaultParameters:
        """
        Estimasi parameter fault dari magnitude menggunakan scaling laws.
        Berguna jika user hanya input magnitude + lokasi.
        
        Args:
            depth_top_km: Kedalaman puncak bidang sesar (km). 
                         Jika None, gunakan default per fault_type.
                         Gempa dangkal (<20km) lebih tsunamigenik.
        """
        if use_blaser:
            scaling = blaser_scaling(magnitude, fault_type)
        else:
            scaling = wells_coppersmith_scaling(magnitude, fault_type)
        
        # Default orientation untuk Java megathrust
        if 'mega' in fault_type.lower():
            strike = 275.0  # Java trench trend
            dip = 15.0
            rake = 90.0
            depth_top = depth_top_km if depth_top_km is not None else 5.0
        elif 'strike' in fault_type.lower():
            strike = 45.0
            dip = 90.0
            rake = 0.0
            depth_top = depth_top_km if depth_top_km is not None else 2.0
        else:  # thrust / normal
            strike = 90.0
            dip = 45.0
            rake = 90.0
            depth_top = depth_top_km if depth_top_km is not None else 5.0
        
        return FaultParameters(
            strike=strike,
            dip=dip,
            rake=rake,
            length_km=scaling['length_km'],
            width_km=scaling['width_km'],
            slip_m=scaling['slip_m'],
            depth_top_km=depth_top,
            epicenter_lat=epicenter_lat,
            epicenter_lon=epicenter_lon,
            magnitude=magnitude,
            fault_type=fault_type
        )


# ============================================================================
# MODULE INFO
# ============================================================================

__version__ = "2.0.0"
__all__ = [
    'TsunamiSWESolver',
    'OkadaSolver',
    'LinearSWESolver',
    'RealBathymetryGrid',
    'ManningGrid',
    'FaultParameters',
    'SimulationConfig',
    'SWEResults',
    'wells_coppersmith_scaling',
    'blaser_scaling',
    'MANNING_COEFFS'
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                         format='%(asctime)s [%(levelname)s] %(message)s')
    
    print("=" * 70)
    print("SWE Tsunami Solver v2.0.0 - REAL BATHYMETRY ONLY")
    print("=" * 70)
    print(f"Numba JIT: {'✅ ENABLED' if NUMBA_AVAILABLE else '❌ DISABLED'}")
    print(f"Scipy: {'✅ ENABLED' if SCIPY_AVAILABLE else '❌ DISABLED'}")
    print()
    print("❌ Synthetic bathymetry: DISABLED")
    print("✅ Only real data sources: BATNAS, DEMNAS, GEBCO")
    print("=" * 70)
    
    # Test fault scaling
    for mw in [7.0, 8.0, 9.0]:
        s = wells_coppersmith_scaling(mw, "megathrust")
        print(f"Mw {mw}: L={s['length_km']:.0f}km, W={s['width_km']:.0f}km, "
               f"slip={s['slip_m']:.2f}m")