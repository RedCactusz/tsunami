"""
============================================================================
TSUNAMISIM WEBGIS BACKEND SERVER v5.0 (MERGED)
============================================================================
Clean Architecture - Modular Services Integration
FastAPI backend untuk:
- Bathymetry serving (BATNAS, DEMNAS, GEBCO)
- SWE tsunami simulation (TsunamiSWESolver v5.0)
- Evacuation ABM simulation
- Network analysis & routing

MIGRATION NOTES:
- ✅ Keeps user's data path configuration
- ✅ New modular architecture (AppState singleton)
- ✅ Backward compatible with old cache functions
- ✅ New /api/* endpoints with clean design
- ✅ GPU acceleration support (Numba JIT, CuPy optional)
- ✅ Proper error handling, logging, rate limiting

Version: 5.0.0 (Merged from .tmp/ with local path compatibility)
============================================================================
"""

import os
import json
import logging
import asyncio
import time
import sys
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from starlette.middleware.gzip import GZipMiddleware

# Add simulation core ke sys.path untuk imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "simulation", "core"))

# ════════════════════════════════════════════════════════════════════════════════
# IMPORTS - Spatial Utilities & Core Solvers
# ════════════════════════════════════════════════════════════════════════════════

# ✅ Spatial utilities (konsolidasi dari spatial_utils.py)
from spatial_utils import (
    haversine_m, haversine_km,
    validate_coordinates, sanitize_depth,
    describe_array, safe_divide,
    wave_speed, abe_initial_height, synolakis_runup,
    fault_efficiency,
    coords_to_geojson_point, features_to_feature_collection
)

# ✅ SWE Tsunami Solver v5.0 (refactored)
from swe_solver import (
    TsunamiSWESolver, FaultParameters, SimulationConfig,
    wells_coppersmith_scaling, blaser_scaling
)

# ✅ Acceleration modules
try:
    from swe_accelerated import warmup_numba
    SWE_ACCELERATED_AVAILABLE = True
except ImportError:
    SWE_ACCELERATED_AVAILABLE = False
    def warmup_numba():
        pass

# ✅ Evacuation ABM Solver
from evacuation_abm import EvacuationABMSolver

# ✅ Fault data & inundation connector
try:
    from fault_data import FAULT_PUBLIC_LABELS, JAVA_FAULTS, JAVA_MEGATHRUST
except ImportError:
    FAULT_PUBLIC_LABELS = {}
    JAVA_FAULTS = {}
    JAVA_MEGATHRUST = {}

try:
    from inundation_connector import (
        InundationConnector, InundationData,
        inundation_to_abm_dict, affected_villages_from_inundation,
        classify_danger_zone
    )
except ImportError:
    InundationConnector = None
    InundationData = None

# ✅ Legacy cache builder functions (backward compatibility)
try:
    from cache import build_road_cache, build_desa_cache, build_tes_cache
    LEGACY_CACHE_AVAILABLE = True
except ImportError:
    LEGACY_CACHE_AVAILABLE = False
    def build_road_cache(vd): return None
    def build_desa_cache(vd): return None
    def build_tes_cache(vd): return None

# ✅ Optional heavy dependencies
try:
    import rasterio
    from rasterio.transform import rowcol
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# ════════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ════════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("tsunamisim")

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - USER'S PATHS + SERVER CONFIG
# ════════════════════════════════════════════════════════════════════════════════

class Config:
    """Configuration — merges user's local paths dengan server settings."""
    
    # 🔧 Data directories (user's local paths)
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    RASTER_DIR = os.path.join(DATA_DIR, "Raster")
    VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")
    BATNAS_DIR = os.path.join(RASTER_DIR, "BATNAS")
    GEBCO_DIR = os.path.join(RASTER_DIR, "GEBCO_18_Mar_2026_54f29d9cc882")
    DEMNAS_DIR = os.path.join(RASTER_DIR, "DEMNAS")
    
    # Shapefile paths (explicit, user-friendly)
    DESA_SHP = os.path.join(VEKTOR_DIR, "Administrasi_Desa.shp")
    PANTAI_SHP = os.path.join(VEKTOR_DIR, "Garis_Pantai_Selatan.shp")
    JALAN_SHP = os.path.join(VEKTOR_DIR, "Jalan_Bantul.shp")
    TES_SHP = os.path.join(VEKTOR_DIR, "TES_Bantul.shp")
    
    # 🌐 Server configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # 🔐 CORS (user allows all in dev)
    CORS_ORIGINS = ["*"]
    CORS_ALLOW_CREDENTIALS = True
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]
    
    # ⏱️ Rate limiting
    RATE_LIMIT_PER_MINUTE = 60
    
    # 📊 Simulation limits
    MAX_SIMULATION_DURATION_MIN = 180
    MAX_ABM_AGENTS = 10000
    
    @classmethod
    def validate_dirs(cls):
        """Validate that required directories exist."""
        dirs_to_check = {
            "VEKTOR_DIR": cls.VEKTOR_DIR,
            "BATNAS_DIR": cls.BATNAS_DIR,
            "DEMNAS_DIR": cls.DEMNAS_DIR,
        }
        for name, path in dirs_to_check.items():
            if not os.path.isdir(path):
                logger.warning(f"⚠️  {name} not found: {path}")
            else:
                logger.info(f"✅ {name}: {path}")


# ════════════════════════════════════════════════════════════════════════════════
# BATHYMETRY MANAGERS (v5.0 design)
# ════════════════════════════════════════════════════════════════════════════════

class BathyCache:
    """Singleton cache untuk raster bathymetry — baca file SEKALI saja."""
    _instance = None
    _cache: Dict = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_load(self, key: str, lat_arr, lon_arr, manager):
        """Get cached grid atau load fresh."""
        cache_key = f"{key}_{len(lat_arr)}_{len(lon_arr)}_{lat_arr[0]:.4f}_{lon_arr[0]:.4f}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        grid = manager.query_grid_bulk(lat_arr, lon_arr)
        self._cache[cache_key] = grid.astype(np.float32) if NUMPY_AVAILABLE else grid
        return grid


class BathyManager:
    """Manager untuk BATNAS GeoTIFF tiles dengan 3-layer masking."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.tiles: List[Dict] = []
        self._load_tiles()
    
    def _load_tiles(self):
        """Scan direktori untuk GeoTIFF tiles."""
        if not os.path.isdir(self.data_dir):
            logger.warning(f"BATNAS directory not found: {self.data_dir}")
            return
        
        if not RASTERIO_AVAILABLE:
            logger.warning("Rasterio not available — BATNAS disabled")
            return
        
        for fname in os.listdir(self.data_dir):
            if not fname.lower().endswith(('.tif', '.tiff')):
                continue
            fpath = os.path.join(self.data_dir, fname)
            try:
                with rasterio.open(fpath) as src:
                    self.tiles.append({
                        'path': fpath,
                        'bounds': src.bounds,
                        'crs': src.crs,
                        'shape': src.shape,
                        'area': (src.bounds.right - src.bounds.left) * 
                                (src.bounds.top - src.bounds.bottom)
                    })
            except Exception as e:
                logger.error(f"Failed to load BATNAS tile {fname}: {e}")
        
        self.tiles.sort(key=lambda t: t['area'])
        logger.info(f"BATNAS: loaded {len(self.tiles)} tiles")
    
    def query_depth(self, lat: float, lon: float) -> Optional[float]:
        """Query depth pada satu titik (negatif=laut, positif=darat)."""
        if not RASTERIO_AVAILABLE or not self.tiles:
            return None
        
        for tile in self.tiles:
            b = tile['bounds']
            if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
                continue
            
            try:
                with rasterio.open(tile['path']) as src:
                    row, col = rowcol(src.transform, lon, lat)
                    if 0 <= row < src.shape[0] and 0 <= col < src.shape[1]:
                        val = float(src.read(1)[row, col])
                        sanitized = sanitize_depth(val)
                        if sanitized is not None:
                            return sanitized
            except Exception as e:
                logger.debug(f"BATNAS query error at ({lat},{lon}): {e}")
                continue
        
        return None

    def query_grid_bulk(self, lat_arr, lon_arr):
        """Vectorized rasterio query untuk speed."""
        if not NUMPY_AVAILABLE:
            return []
        
        rows, cols = len(lat_arr), len(lon_arr)
        grid = np.full((rows, cols), -1000.0, dtype=np.float32)
        
        if not RASTERIO_AVAILABLE or not self.tiles:
            return grid
        
        lon_grid, lat_grid = np.meshgrid(lon_arr, lat_arr)
        
        for tile in self.tiles:
            try:
                with rasterio.open(tile['path']) as src:
                    data = src.read(1)
                    transform = src.transform
                    
                    rows_idx, cols_idx = rowcol(transform, lon_grid.flatten(), lat_grid.flatten())
                    rows_idx = np.array(rows_idx)
                    cols_idx = np.array(cols_idx)
                    
                    valid = (rows_idx >= 0) & (rows_idx < src.shape[0]) & \
                            (cols_idx >= 0) & (cols_idx < src.shape[1])
                    
                    flat_grid = grid.flatten()
                    valid_idx = np.where(valid)[0]
                    
                    if valid_idx.size > 0:
                        vals = data[rows_idx[valid_idx], cols_idx[valid_idx]].astype(np.float32)
                        unfilled = flat_grid[valid_idx] <= -1000.0
                        sanitized_ok = (vals < -0.5) & (vals >= -7500.0) & ~np.isnan(vals)
                        fill_mask = unfilled & sanitized_ok
                        fill_idx = valid_idx[fill_mask]
                        flat_grid[fill_idx] = vals[fill_mask]
                    
                    grid = flat_grid.reshape((rows, cols))
            except Exception as e:
                logger.debug(f"Bulk BATNAS query error: {e}")
        
        return grid


class DEMManager:
    """Manager untuk DEMNAS elevation tiles."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.tiles: List[Dict] = []
        self._load_tiles()
    
    def _load_tiles(self):
        if not os.path.isdir(self.data_dir):
            logger.warning(f"DEMNAS directory not found: {self.data_dir}")
            return
        
        if not RASTERIO_AVAILABLE:
            return
        
        for fname in os.listdir(self.data_dir):
            if not fname.lower().endswith(('.tif', '.tiff')):
                continue
            fpath = os.path.join(self.data_dir, fname)
            try:
                with rasterio.open(fpath) as src:
                    self.tiles.append({
                        'path': fpath,
                        'bounds': src.bounds,
                        'shape': src.shape,
                        'area': (src.bounds.right - src.bounds.left) * 
                                (src.bounds.top - src.bounds.bottom)
                    })
            except Exception as e:
                logger.error(f"Failed to load DEMNAS tile {fname}: {e}")
        
        self.tiles.sort(key=lambda t: t['area'])
        logger.info(f"DEMNAS: loaded {len(self.tiles)} tiles")
    
    def query_elevation(self, lat: float, lon: float) -> Optional[float]:
        """Query elevation (positif=darat)."""
        if not RASTERIO_AVAILABLE or not self.tiles:
            return None
        
        for tile in self.tiles:
            b = tile['bounds']
            if not (b.left <= lon <= b.right and b.bottom <= lat <= b.top):
                continue
            
            try:
                with rasterio.open(tile['path']) as src:
                    row, col = rowcol(src.transform, lon, lat)
                    if 0 <= row < src.shape[0] and 0 <= col < src.shape[1]:
                        val = float(src.read(1)[row, col])
                        if val > -100 and val < 10000:
                            return val
            except Exception as e:
                logger.debug(f"DEMNAS query error: {e}")
                continue
        
        return None

    def query_grid_bulk(self, lat_arr, lon_arr):
        """Vectorized query untuk speed."""
        if not NUMPY_AVAILABLE:
            return []
        
        rows, cols = len(lat_arr), len(lon_arr)
        grid = np.full((rows, cols), -1000.0, dtype=np.float32)
        
        if not RASTERIO_AVAILABLE or not self.tiles:
            return grid
        
        lon_grid, lat_grid = np.meshgrid(lon_arr, lat_arr)
        
        for tile in self.tiles:
            try:
                with rasterio.open(tile['path']) as src:
                    data = src.read(1)
                    transform = src.transform
                    
                    rows_idx, cols_idx = rowcol(transform, lon_grid.flatten(), lat_grid.flatten())
                    rows_idx = np.array(rows_idx)
                    cols_idx = np.array(cols_idx)
                    
                    valid = (rows_idx >= 0) & (rows_idx < src.shape[0]) & \
                            (cols_idx >= 0) & (cols_idx < src.shape[1])
                    
                    flat_grid = grid.flatten()
                    valid_idx = np.where(valid)[0]
                    
                    if valid_idx.size > 0:
                        vals = data[rows_idx[valid_idx], cols_idx[valid_idx]].astype(np.float32)
                        unfilled = flat_grid[valid_idx] <= -1000.0
                        sanitized_ok = (vals > -100) & (vals < 10000) & ~np.isnan(vals)
                        fill_mask = unfilled & sanitized_ok
                        fill_idx = valid_idx[fill_mask]
                        flat_grid[fill_idx] = vals[fill_mask]
                    
                    grid = flat_grid.reshape((rows, cols))
            except Exception as e:
                logger.debug(f"Bulk DEMNAS query error: {e}")
        
        return grid


class GEBCOReader:
    """Reader untuk GEBCO bathymetry (fallback deep sea)."""
    
    def __init__(self, gebco_file: str):
        self.gebco_file = gebco_file
        self.available = os.path.isfile(gebco_file) and RASTERIO_AVAILABLE
        if self.available:
            logger.info(f"GEBCO loaded: {os.path.basename(gebco_file)}")
        else:
            logger.warning(f"GEBCO not available")
    
    def query_depth(self, lat: float, lon: float) -> Optional[float]:
        if not self.available:
            return None
        try:
            with rasterio.open(self.gebco_file) as src:
                row, col = rowcol(src.transform, lon, lat)
                if 0 <= row < src.shape[0] and 0 <= col < src.shape[1]:
                    val = float(src.read(1)[row, col])
                    if val < 0:
                        return sanitize_depth(val)
                    else:
                        return val
        except Exception as e:
            logger.debug(f"GEBCO query error: {e}")
        return None

    def query_grid_bulk(self, lat_arr, lon_arr):
        """Vectorized query."""
        if not NUMPY_AVAILABLE:
            return []
        
        rows, cols = len(lat_arr), len(lon_arr)
        grid = np.full((rows, cols), -1000.0, dtype=np.float32)
        
        if not self.available:
            return grid
            
        lon_grid, lat_grid = np.meshgrid(lon_arr, lat_arr)
        
        try:
            with rasterio.open(self.gebco_file) as src:
                data = src.read(1)
                transform = src.transform
                
                rows_idx, cols_idx = rowcol(transform, lon_grid.flatten(), lat_grid.flatten())
                rows_idx = np.array(rows_idx)
                cols_idx = np.array(cols_idx)
                
                valid = (rows_idx >= 0) & (rows_idx < src.shape[0]) & \
                        (cols_idx >= 0) & (cols_idx < src.shape[1])
                
                flat_grid = grid.flatten()
                valid_idx = np.where(valid)[0]
                
                if valid_idx.size > 0:
                    vals = data[rows_idx[valid_idx], cols_idx[valid_idx]].astype(np.float32)
                    unfilled = flat_grid[valid_idx] <= -1000.0
                    not_nan = ~np.isnan(vals)
                    ocean_ok = (vals < -0.5) & (vals >= -7500.0)
                    land_ok = vals >= 0
                    sanitized_ok = (ocean_ok | land_ok) & not_nan
                    fill_mask = unfilled & sanitized_ok
                    fill_idx = valid_idx[fill_mask]
                    flat_grid[fill_idx] = vals[fill_mask]
                
                grid = flat_grid.reshape((rows, cols))
        except Exception as e:
            logger.debug(f"Bulk GEBCO query error: {e}")
        
        return grid


# ════════════════════════════════════════════════════════════════════════════════
# APPLICATION STATE (v5.0 singleton architecture)
# ════════════════════════════════════════════════════════════════════════════════

class AppState:
    """Central application state — manages all solvers and data managers."""
    
    # Bathymetry managers
    batnas: Optional[BathyManager] = None
    demnas: Optional[DEMManager] = None
    gebco: Optional[GEBCOReader] = None
    
    # Solvers
    swe_solver: Optional[TsunamiSWESolver] = None
    abm_solver: Optional[EvacuationABMSolver] = None
    inundation_connector: Optional[InundationConnector] = None
    
    # Cache untuk hasil simulasi terakhir
    last_swe_result: Optional[Dict] = None
    
    # Legacy caches (backward compat)
    legacy_caches: Dict = {}
    
    # Rate limiting state
    request_counts: Dict[str, int] = {}
    request_reset_times: Dict[str, float] = {}
    
    # Thread pool untuk background tasks
    executor = ThreadPoolExecutor(max_workers=2)


# Singleton instance
app_state = AppState()


# ════════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS (Request/Response)
# ════════════════════════════════════════════════════════════════════════════════

class DepthQuery(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class SimulateRequest(BaseModel):
    """Request untuk simulasi tsunami SWE."""
    scenario_id: str = Field("default", description="ID skenario gempa")
    magnitude: Optional[float] = Field(None, ge=5.0, le=9.5)
    duration_min: float = Field(60.0, ge=1.0, le=180.0)
    resolution_mode: str = Field("auto")
    custom_epicenter: Optional[Dict[str, float]] = Field(None)
    depth_km: Optional[float] = Field(None, ge=1.0, le=100.0)


class ABMRequest(BaseModel):
    """Request untuk simulasi ABM evakuasi."""
    warning_time_min: float = Field(20.0, ge=0, le=180)
    duration_min: float = Field(120.0, ge=10, le=480)
    tsunami_height_m: float = Field(5.0, ge=0.1, le=20)
    num_agents: int = Field(100, ge=10, le=10000)
    inundation_geojson: Optional[Dict] = Field(None)
    affected_villages: Optional[List[Dict]] = Field(None)


class RoutingRequest(BaseModel):
    """Request untuk analisis rute evakuasi."""
    transport: str = Field("foot")
    safety_weight: float = Field(50.0, ge=0, le=100)
    tes_id: str = Field(...)
    origin_lat: float = Field(...)
    origin_lon: float = Field(...)
    inundation_geojson: Optional[Dict] = Field(None)


# ════════════════════════════════════════════════════════════════════════════════
# LIFECYCLE EVENTS & MIDDLEWARE
# ════════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown lifecycle."""
    logger.info("=" * 80)
    logger.info("🚀 TsunamiSim Backend v5.0 starting...")
    logger.info("=" * 80)
    
    # Validate directories
    Config.validate_dirs()
    
    # Pre-warm Numba JIT jika tersedia
    if SWE_ACCELERATED_AVAILABLE:
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, warmup_numba)
            logger.info("✅ Numba JIT warmed up")
        except Exception as e:
            logger.warning(f"Numba warmup failed (non-critical): {e}")
    
    # Initialize bathymetry managers
    logger.info("Initializing bathymetry managers...")
    app_state.batnas = BathyManager(Config.BATNAS_DIR)
    app_state.demnas = DEMManager(Config.DEMNAS_DIR)
    app_state.gebco = GEBCOReader(Config.GEBCO_DIR if os.path.isfile(Config.GEBCO_DIR) else 
                                   os.path.join(Config.RASTER_DIR, "GEBCO_18_Mar_2026_54f29d9cc882", 
                                               "gebco_2025_n-7.5_s-11.5_w108.0_e112.0_geotiff.tif"))
    
    # Initialize SWE solver
    try:
        logger.info("Initializing SWE Solver...")
        app_state.swe_solver = TsunamiSWESolver(
            batnas_manager=app_state.batnas,
            dem_manager=app_state.demnas,
            gebco_reader=app_state.gebco,
            desa_shp_path=Config.DESA_SHP if os.path.exists(Config.DESA_SHP) else None,
            coastline_shp_path=Config.PANTAI_SHP if os.path.exists(Config.PANTAI_SHP) else None,
        )
        logger.info("✅ SWE Solver initialized")
    except Exception as e:
        logger.error(f"⚠️  SWE Solver init failed: {e}")
        app_state.swe_solver = None
    
    # Initialize ABM solver
    try:
        logger.info("Initializing ABM Solver...")
        app_state.abm_solver = EvacuationABMSolver(
            vektor_dir=Config.VEKTOR_DIR,
            dem_mgr=app_state.demnas
        )
        # Run build_caches di background
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, app_state.abm_solver.build_caches)
        logger.info("✅ ABM Solver initialization started in background")
    except Exception as e:
        logger.warning(f"⚠️  ABM Solver init failed (non-fatal): {e}")
        app_state.abm_solver = None
    
    # Initialize Inundation Connector jika tersedia
    if InundationConnector:
        try:
            app_state.inundation_connector = InundationConnector(
                desa_shp_path=Config.DESA_SHP if os.path.exists(Config.DESA_SHP) else None,
                dem_manager=app_state.demnas,
            )
            logger.info("✅ Inundation Connector initialized")
        except Exception as e:
            logger.warning(f"Inundation Connector init failed: {e}")
    
    # Load legacy caches untuk backward compatibility
    if LEGACY_CACHE_AVAILABLE:
        try:
            logger.info("Loading legacy caches...")
            app_state.legacy_caches['desa'] = build_desa_cache(Config.VEKTOR_DIR)
            app_state.legacy_caches['tes'] = build_tes_cache(Config.VEKTOR_DIR)
            app_state.legacy_caches['roads'] = build_road_cache(Config.VEKTOR_DIR)
            logger.info("✅ Legacy caches loaded")
        except Exception as e:
            logger.warning(f"Legacy cache loading failed: {e}")
    
    logger.info(f"🌐 Server listening on {Config.HOST}:{Config.PORT}")
    logger.info("=" * 80)
    
    yield
    
    logger.info("🛑 Server shutting down...")


# ════════════════════════════════════════════════════════════════════════════════
# FASTAPI APP INITIALIZATION
# ════════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="TsunamiSim Backend API v5.0",
    description="Tsunami Simulation & Evacuation Backend (Merged architecture)",
    version="5.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=Config.CORS_ALLOW_CREDENTIALS,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ════════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE - Rate Limiting & Security
# ════════════════════════════════════════════════════════════════════════════════

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple IP-based rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    if client_ip not in app_state.request_counts:
        app_state.request_counts[client_ip] = 0
        app_state.request_reset_times[client_ip] = current_time
    
    # Reset counter tiap menit
    if current_time - app_state.request_reset_times[client_ip] > 60:
        app_state.request_counts[client_ip] = 0
        app_state.request_reset_times[client_ip] = current_time
        
    app_state.request_counts[client_ip] += 1
    
    if app_state.request_counts[client_ip] > Config.RATE_LIMIT_PER_MINUTE * 100:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"}
        )
    
    response = await call_next(request)
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS - HEALTH & INFO
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "TsunamiSim Backend API",
        "version": "5.0.0",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "5.0.0",
        "services": {
            "batnas": bool(app_state.batnas and app_state.batnas.tiles),
            "demnas": bool(app_state.demnas and app_state.demnas.tiles),
            "gebco": bool(app_state.gebco and app_state.gebco.available),
            "swe_solver": bool(app_state.swe_solver),
            "abm_solver": bool(app_state.abm_solver),
        }
    }


@app.get("/api/health")
async def api_health():
    """API health check (modern endpoint)."""
    return await health()


@app.get("/api/info")
async def api_info():
    """Information tentang server dan data yang tersedia."""
    info_data = {
        "batnas_tiles": len(app_state.batnas.tiles) if app_state.batnas else 0,
        "demnas_tiles": len(app_state.demnas.tiles) if app_state.demnas else 0,
        "gebco_available": bool(app_state.gebco and app_state.gebco.available),
        "swe_solver_available": bool(app_state.swe_solver),
        "abm_solver_available": bool(app_state.abm_solver),
    }
    
    # Add legacy cache info
    if app_state.legacy_caches:
        for cache_name, cache_data in app_state.legacy_caches.items():
            if cache_data:
                info_data[f"{cache_name}_count"] = cache_data.get("count", 0)
    
    return info_data


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS - BATHYMETRY (Modern /api/* style)
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/api/depth")
async def query_depth(lat: float = Query(...), lon: float = Query(...)):
    """Query depth/elevation pada titik tertentu."""
    if not validate_coordinates(lat, lon):
        raise HTTPException(400, "Invalid coordinates")
    
    depth = None
    source = None
    
    if app_state.batnas:
        depth = app_state.batnas.query_depth(lat, lon)
        if depth is not None:
            source = "BATNAS"
    
    if depth is None and app_state.demnas:
        elev = app_state.demnas.query_elevation(lat, lon)
        if elev is not None:
            depth = elev
            source = "DEMNAS"
    
    if depth is None and app_state.gebco:
        depth = app_state.gebco.query_depth(lat, lon)
        if depth is not None:
            source = "GEBCO"
    
    if depth is None:
        return {"lat": lat, "lon": lon, "depth": None, "source": None}
    
    return {
        "lat": lat,
        "lon": lon,
        "depth_m": depth,
        "is_ocean": depth < 0,
        "source": source,
        "wave_speed_mps": wave_speed(abs(depth)) if depth < 0 else 0
    }


@app.post("/api/depth/batch")
async def query_depth_batch(points: List[DepthQuery] = Body(...)):
    """Batch query untuk multiple points."""
    if len(points) > 1000:
        raise HTTPException(400, "Max 1000 points per request")
    
    results = []
    for p in points:
        depth = None
        source = None
        
        if app_state.batnas:
            depth = app_state.batnas.query_depth(p.lat, p.lon)
            if depth is not None:
                source = "BATNAS"
        
        if depth is None and app_state.gebco:
            depth = app_state.gebco.query_depth(p.lat, p.lon)
            if depth is not None:
                source = "GEBCO"
        
        results.append({
            "lat": p.lat,
            "lon": p.lon,
            "depth_m": depth,
            "source": source
        })
    
    return {"results": results, "count": len(results)}


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS - SWE TSUNAMI SIMULATION
# ════════════════════════════════════════════════════════════════════════════════

@app.post("/api/simulate")
async def simulate_tsunami(req: SimulateRequest):
    """Jalankan simulasi tsunami SWE."""
    if app_state.swe_solver is None:
        raise HTTPException(503, "SWE Solver unavailable")
    
    try:
        # Basic simulation dengan parameter dari request
        magnitude = req.magnitude or 7.5
        epicenter_lat = req.custom_epicenter.get("lat", -9.0) if req.custom_epicenter else -9.0
        epicenter_lon = req.custom_epicenter.get("lon", 110.3) if req.custom_epicenter else 110.3
        
        logger.info(f"Starting SWE simulation: Mw={magnitude}, epicenter=({epicenter_lat},{epicenter_lon})")
        
        # Jalankan simulasi di executor
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    app_state.executor,
                    app_state.swe_solver.simulate,
                    magnitude,
                    epicenter_lat,
                    epicenter_lon,
                    req.duration_min,
                ),
                timeout=600.0
            )
        except asyncio.TimeoutError:
            raise HTTPException(503, "Simulation timeout")
        
        # Sanitize result sebelum kirim ke frontend
        response = {
            "success": True,
            "magnitude": magnitude,
            "max_wave_height_m": result.get("max_wave_height_m", 0),
            "inundation_area_km2": result.get("inundation_area_km2", 0),
            "arrival_time_min": result.get("arrival_time_min", 0),
            "affected_villages": result.get("affected_villages", []),
            "inundation_geojson": result.get("inundation_geojson", {}),
            "statistics": result.get("statistics", {}),
        }
        
        # Cache result untuk ABM
        app_state.last_swe_result = result
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SWE simulation failed")
        raise HTTPException(500, f"Simulation error: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS - EVACUATION ABM
# ════════════════════════════════════════════════════════════════════════════════

@app.post("/api/abm/simulate")
async def abm_simulate(req: ABMRequest):
    """Jalankan simulasi ABM evakuasi."""
    if app_state.abm_solver is None:
        raise HTTPException(503, "ABM Solver unavailable")
    
    # Tunggu build_caches selesai (max 120 detik)
    if app_state.abm_solver.router is None:
        logger.info("[ABM] Waiting for caches to build...")
        for i in range(120):
            await asyncio.sleep(1)
            if app_state.abm_solver.router is not None:
                break
        else:
            raise HTTPException(503, "ABM graph not ready after 120 seconds")
    
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                app_state.abm_solver.run_abm,
                req.dict()
            ),
            timeout=300.0
        )
        
        return {
            "status": "ok",
            "num_agents": result.get("total_agents", 0),
            "safe_count": result.get("safe_count", 0),
            "trapped_count": result.get("trapped_count", 0),
            "frames": result.get("frames", []),
            "statistics": result.get("statistics", {}),
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(504, "ABM simulation timeout")
    except Exception as e:
        logger.exception("ABM simulation failed")
        raise HTTPException(500, f"ABM error: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════════
# LEGACY ENDPOINTS (Backward Compatibility)
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/admin/desa")
async def get_desa():
    """Legacy endpoint: Get desa data."""
    cache = app_state.legacy_caches.get("desa")
    if cache:
        return {
            "source": "cache",
            "count": cache.get("count", 0),
            "desa": cache.get("desa", []),
        }
    return {"source": "none", "desa": []}


@app.get("/admin/tes")
async def get_tes():
    """Legacy endpoint: Get TES data."""
    cache = app_state.legacy_caches.get("tes")
    if cache:
        return {
            "source": "cache",
            "count": cache.get("count", 0),
            "tes": cache.get("tes", []),
        }
    return {"source": "none", "tes": []}


@app.get("/network/roads")
async def get_roads():
    """Legacy endpoint: Get roads data."""
    cache = app_state.legacy_caches.get("roads")
    if cache:
        return {
            "source": "cache",
            "count": cache.get("feature_count", 0),
            "roads": cache.get("roads", []),
        }
    return {"source": "none", "roads": []}


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info" if not Config.DEBUG else "debug"
    )
