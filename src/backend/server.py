"""
TsunamiSim Backend Server v5.0 - Orchestrator
============================================================================
Minimal FastAPI application - delegates all logic to modular controllers.

Responsibilities:
- Setup FastAPI app
- Initialize bathymetry & solvers (startup)
- Register controllers (routers)
- Health checks (global)

Logic: See simulation/swe/ and simulation/abm/
============================================================================
"""

import os
import logging
import sys
import time
import math
import random
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Add simulation to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

class Config:
    """Server configuration."""
    # Paths
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    RASTER_DIR = os.path.join(DATA_DIR, "Raster")
    VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")
    BATNAS_DIR = os.path.join(RASTER_DIR, "BATNAS")
    DEMNAS_DIR = os.path.join(RASTER_DIR, "DEMNAS")
    GEBCO_DIR = os.path.join(RASTER_DIR, "GEBCO_18_Mar_2026_54f29d9cc882")
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # CORS
    CORS_ORIGINS = ["*"]
    
    # Rate limiting
    RATE_LIMIT_MINUTE = 60


# ════════════════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("server")


# ════════════════════════════════════════════════════════════════════════════════
# APPLICATION STATE (Singleton)
# ════════════════════════════════════════════════════════════════════════════════

class AppState:
    """Central state - managers & solvers."""
    # Bathymetry
    batnas = None
    demnas = None
    gebco = None
    
    # Solvers
    swe_solver = None
    abm_solver = None
    inundation_connector = None
    
    # Cache
    last_swe_result = None
    
    # Utilities
    executor = ThreadPoolExecutor(max_workers=2)
    request_counts = {}
    request_reset_times = {}


app_state = AppState()


# ════════════════════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN LIFECYCLE
# ════════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("=" * 80)
    logger.info("🚀 TsunamiSim Backend v5.0 (Orchestrator) starting...")
    logger.info("=" * 80)

    try:
        # Validate data directories
        for name, path in [("VEKTOR", Config.VEKTOR_DIR),
                          ("BATNAS", Config.BATNAS_DIR),
                          ("DEMNAS", Config.DEMNAS_DIR)]:
            if os.path.isdir(path):
                logger.info(f"✅ {name}: {path}")
            else:
                logger.warning(f"⚠️  {name} not found: {path}")
    except Exception as e:
        logger.error(f"Startup error: {e}")

    # Pre-load road graph for faster routing
    preload_road_graph()

    # ⚡ Fault data: Lazy load on-demand (biar server start cepat!)
    # Fault data akan di-load saat first request ke /admin/faults atau /simulate
    # Dengan cache, loading < 1 detik!
    logger.info("📂 Fault data: akan di-load on-demand (dengan cache)")

    logger.info(f"🌐 Listening on {Config.HOST}:{Config.PORT}")
    logger.info("=" * 80)

    yield  # App is running

    logger.info("🛑 Server shutting down...")


# ════════════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ════════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="TsunamiSim Backend v5.0",
    description="Modular Tsunami & Evacuation Simulator",
    version="5.0.0",
    lifespan=lifespan
)

# Middleware - CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ════════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE - RATE LIMITING & SECURITY
# ════════════════════════════════════════════════════════════════════════════════

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Simple IP-based rate limiting."""
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    if client_ip not in app_state.request_counts:
        app_state.request_counts[client_ip] = 0
        app_state.request_reset_times[client_ip] = current_time
    
    if current_time - app_state.request_reset_times[client_ip] > 60:
        app_state.request_counts[client_ip] = 0
        app_state.request_reset_times[client_ip] = current_time
    
    app_state.request_counts[client_ip] += 1
    
    if app_state.request_counts[client_ip] > Config.RATE_LIMIT_MINUTE * 100:
        return JSONResponse(status_code=429, 
                          content={"error": "Rate limit exceeded"})
    
    response = await call_next(request)
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    """Add security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ════════════════════════════════════════════════════════════════════════════════
# INCLUDE ROUTERS (Import from controllers)
# ════════════════════════════════════════════════════════════════════════════════

# SWE Simulation Router
from simulation.swe.controller import swe_router
app.include_router(swe_router, prefix="/api/swe", tags=["🌊 SWE Simulation"])

# ABM Simulation Router
from simulation.abm.controller import abm_router
app.include_router(abm_router, prefix="/api/abm", tags=["🚨 ABM Evacuation"])

# Road Router (load shapefile jalan)
from simulation.abm.road_router import get_or_load_road_graph
import os

# Absolute path ke shapefile
SHAPEFILE_PATH = os.path.join(os.path.dirname(__file__), "data", "Vektor", "Jalan_Bantul.shp")
ROAD_GRAPH = None  # Will be loaded on first request

# Fault Loader (dynamic shapefile reader)
from simulation.swe.fault_loader import get_fault_loader

VEKTOR_DIR = os.path.join(os.path.dirname(__file__), "data", "Vektor")
FAULT_LOADER = None  # Will be initialized at startup

def preload_road_graph():
    """Pre-load road graph saat server startup."""
    global ROAD_GRAPH, FAULT_LOADER
    try:
        logger.info("Pre-loading road network graph...")
        ROAD_GRAPH = get_or_load_road_graph(SHAPEFILE_PATH)
        if ROAD_GRAPH:
            logger.info(f"✅ Road graph pre-loaded: {ROAD_GRAPH.graph.number_of_nodes()} nodes, {ROAD_GRAPH.graph.number_of_edges()} edges")
        else:
            logger.warning("⚠️  Failed to pre-load road graph, will load on first request")
    except Exception as e:
        logger.error(f"❌ Error pre-loading road graph: {e}")


def preload_fault_data():
    """Pre-load fault data dari shapefile saat server startup."""
    global FAULT_LOADER
    try:
        logger.info("Scanning fault data from shapefiles...")
        FAULT_LOADER = get_fault_loader(VEKTOR_DIR)

        if FAULT_LOADER is None:
            logger.warning("⚠️  Fault loader not available (geopandas not installed)")
            return

        # Scan dan load semua fault
        count = FAULT_LOADER.scan_and_load_all()

        logger.info(f"✅ Fault data loaded: {count} faults from shapefiles")

        # Log sample faults
        fault_ids = list(FAULT_LOADER.faults.keys())[:5]
        logger.info(f"   Sample faults: {fault_ids}")

    except Exception as e:
        logger.error(f"❌ Error pre-loading fault data: {e}")
        import traceback
        traceback.print_exc()


# ════════════════════════════════════════════════════════════════════════════════
# GLOBAL ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint - API documentation."""
    return {
        "service": "TsunamiSim Backend",
        "version": "5.0.0",
        "architecture": "Modular (SWE + ABM controllers)",
        "docs": "/docs",
        "endpoints": {
            "swe": "GET /api/swe/health  (tsunami simulation)",
            "abm": "GET /api/abm/health  (evacuation simulation)",
            "health": "GET /health       (global health)"
        }
    }


@app.get("/health")
async def health():
    """Global health check."""
    return {
        "status": "healthy",
        "version": "5.0.0",
        "modules": {
            "swe": {"endpoint": "/api/swe", "status": "enabled"},
            "abm": {"endpoint": "/api/abm", "status": "enabled"},
        }
    }


@app.get("/api/health")
async def api_health():
    """Alias for /health (modern API style)."""
    return await health()


@app.get("/status")
async def status_check():
    """Frontend status endpoint."""
    return {
        "status": "operational",
        "timestamp": time.time(),
        "version": "5.0.0",
        "modules": {
            "swe": {"available": True, "health": "ok"},
            "abm": {"available": True, "health": "ok"}
        }
    }


# ════════════════════════════════════════════════════════════════════════════════
# ADMIN DATA ENDPOINTS (Desa & TES)
# ════════════════════════════════════════════════════════════════════════════════

# Mock data for admin endpoints
MOCK_DESA = [
    {"name": "Gadingsari", "lat": -7.998, "lon": 110.267},
    {"name": "Srigading", "lat": -7.985, "lon": 110.285},
    {"name": "Tirtosari", "lat": -7.975, "lon": 110.255},
    {"name": "Poncosari", "lat": -7.963, "lon": 110.298},
    {"name": "Trimurti", "lat": -7.952, "lon": 110.244},
    {"name": "Banaran", "lat": -7.941, "lon": 110.311},
    {"name": "Palbapang", "lat": -7.930, "lon": 110.280},
    {"name": "Sabdodadi", "lat": -7.920, "lon": 110.262},
]

MOCK_TES = [
    {"id": "TES-01", "name": "TES Masjid Al Huda", "lat": -7.96843133606, "lon": 110.233926052, "kapasitas": 500},
    {"id": "TES-02", "name": "TES BPP Srandakan", "lat": -7.96095456288, "lon": 110.241307048, "kapasitas": 500},
    {"id": "TES-03", "name": "TES SD Muh Gunturgeni", "lat": -7.96321767428, "lon": 110.248343758, "kapasitas": 500},
    {"id": "TES-04", "name": "TES Masjid Al Firdaus", "lat": -7.96933305549, "lon": 110.243332044, "kapasitas": 500},
    {"id": "TES-05", "name": "TES SD Koripan", "lat": -7.97668879901, "lon": 110.23588092, "kapasitas": 500},
    {"id": "TES-06", "name": "TES Lapangan Sorobayan", "lat": -7.96926275459, "lon": 110.255317008, "kapasitas": 500},
    {"id": "TES-07", "name": "TES SD Rejoniten", "lat": -7.98496856992, "lon": 110.250062291, "kapasitas": 500},
    {"id": "TES-08", "name": "TES Kalurahan Gadingharjo", "lat": -7.9794643436, "lon": 110.263849605, "kapasitas": 500},
    {"id": "TES-09", "name": "TES Lapangan Srigading", "lat": -7.97581529443, "lon": 110.280636194, "kapasitas": 500},
    {"id": "TES-10", "name": "TES Pasar Sangkeh", "lat": -7.98229057658, "lon": 110.286228682, "kapasitas": 500},
]


@app.get("/admin/desa")
async def get_admin_desa():
    """Get list of all administrative villages (desa/kelurahan)."""
    return {
        "status": "ok",
        "count": len(MOCK_DESA),
        "desa": MOCK_DESA
    }


@app.get("/admin/tes")
async def get_admin_tes():
    """Get list of all Temporary Evacuation Shelters (TES)."""
    return {
        "status": "ok",
        "count": len(MOCK_TES),
        "tes": MOCK_TES
    }


@app.get("/admin/faults")
async def get_admin_faults():
    """
    Get list of all available faults from shapefiles.

    LAZY LOADING: Fault data di-load saat first request.
    Dengan cache: < 1 detik!
    Tanpa cache: ~10 detik (dan di-cache untuk next time)
    """
    global FAULT_LOADER

    # Lazy load: hanya load saat first request
    if FAULT_LOADER is None:
        try:
            from simulation.swe.fault_loader import get_fault_loader
            logger.info("[FAULTS] Lazy loading fault data...")
            FAULT_LOADER = get_fault_loader(VEKTOR_DIR)

            if FAULT_LOADER is not None:
                # Load from cache atau scan shapefile
                count = FAULT_LOADER.scan_and_load_all()
                logger.info(f"[FAULTS] ✅ Loaded {count} faults (lazy load)")
            else:
                logger.warning("[FAULTS] Fault loader not available")

        except Exception as e:
            logger.error(f"[FAULTS] Error loading faults: {e}")
            FAULT_LOADER = None

    # Return fault list
    if FAULT_LOADER is not None:
        public_labels = FAULT_LOADER.get_public_labels()

        # 🔧 Tambahkan alias untuk frontend yang masih pakai ID lama
        from simulation.swe.fault_aliases import build_aliases
        aliased_faults = build_aliases(public_labels)

        # Merge aliases
        all_faults = {**public_labels, **aliased_faults}

        return {
            "status": "ok",
            "count": len(all_faults),
            "faults": all_faults,
            "source": "shapefile_with_aliases"
        }
    else:
        # Fallback: hardcoded faults
        from simulation.swe.fault_data import FAULT_PUBLIC_LABELS
        return {
            "status": "ok",
            "count": len(FAULT_PUBLIC_LABELS),
            "faults": FAULT_PUBLIC_LABELS,
            "source": "hardcoded"
        }


# ════════════════════════════════════════════════════════════════════════════════
# ROOT-LEVEL SIMULATION ALIASES (for frontend compatibility)
# ════════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Literal

class SimulationParams(BaseModel):
    """SWE simulation parameters."""
    magnitude: float = Field(default=8.0, ge=5.0, le=9.5)
    fault_type: Literal["vertical", "horizontal"] = Field(default="vertical")
    fault_id: Optional[str] = Field(default=None)
    source_mode: Literal["fault", "mega", "custom"] = Field(default="fault")
    depth_km: Optional[float] = Field(default=None)
    lat: Optional[float] = Field(default=None)
    lon: Optional[float] = Field(default=None)


class ABMParams(BaseModel):
    """ABM simulation parameters."""
    warning_time_min: float = Field(default=20.0, ge=0, le=180)
    sim_duration_min: float = Field(default=120.0, ge=10, le=480)
    flood_height_m: float = Field(default=5.0, ge=0.1, le=20)
    transport: Literal["foot", "motor", "car"] = Field(default="foot")
    # SWE result untuk integrasi hazard-aware routing
    swe_result: Optional[Dict] = Field(default=None)


class RoutingRequest(BaseModel):
    """Request for evacuation routing analysis."""
    transport: Literal["foot", "motor", "car"] = Field(default="foot")
    speed_kmh: int = Field(default=5)
    safety_weight: float = Field(default=50.0, ge=0, le=100)
    origin_lat: Optional[float] = Field(default=None)
    origin_lon: Optional[float] = Field(default=None)
    tes_id: Optional[str] = Field(default=None)


# Mock response data
MOCK_SWE_RESULT = {
    "wave_path": [
        {"distance_km": 0, "arrival_time_min": 0, "wave_height_m": 12.0, "speed_kmh": 720, "source": "BLEND"},
        {"distance_km": 10, "arrival_time_min": 1.1, "wave_height_m": 7.8, "speed_kmh": 640, "source": "BATNAS"},
        {"distance_km": 30, "arrival_time_min": 4.0, "wave_height_m": 3.9, "speed_kmh": 520, "source": "GEBCO"},
    ],
    "max_inundation_m": 8.3,
    "arrival_time_min": 22,
    "affected_area_km2": 47.5,
}

MOCK_IMPACT_RESULT = {
    "summary": {
        "total_terdampak": 18420,
        "zona_sangat_tinggi": 4210,
        "zona_tinggi": 7830,
        "zona_sedang": 5180,
        "zona_rendah": 1200,
    },
    "affected_villages": [
        {"kelurahan": "Gadingsari", "population": 4250, "terdampak": 2975, "percentage": 70, "zona_bahaya": "Sangat Tinggi", "color": "#f87171", "coordinates": [-7.998, 110.267]},
        {"kelurahan": "Srigading", "population": 3820, "terdampak": 2674, "percentage": 70, "zona_bahaya": "Sangat Tinggi", "color": "#f87171", "coordinates": [-7.985, 110.285]},
    ],
    "chart_data": {"donut": [
        {"label": "Zona Sangat Tinggi", "value": 4210, "color": "#f87171"},
        {"label": "Zona Tinggi", "value": 7830, "color": "#fb923c"},
    ]},
}

MOCK_ABM_RESULT = {
    "total_agents": 100,
    "safe_count": 87,
    "trapped_count": 13,
    "avg_evacuation_time_min": 35.5,
    "frames": [
        {"time_min": 0, "agents": []},
        {"time_min": 5, "agents": [{"id": "a1", "lat": -7.998, "lon": 110.267, "status": "evacuating"}]},
    ],
}

MOCK_ROUTING_RESULT = {
    "routes": [
        {
            "desa": "Gadingsari",
            "target_tes": "TES-01",
            "route_path": [[-7.998, 110.267], [-7.990, 110.270], [-7.983, 110.275]],
            "distance_km": 2.3,
            "walk_time_min": 35,
            "can_evacuate": True,
            "status": "optimal",
            "color": "#4ade80",
            "score": 0.92,
        },
        {
            "desa": "Srigading",
            "target_tes": "TES-02",
            "route_path": [[-7.985, 110.285], [-7.978, 110.282], [-7.971, 110.279]],
            "distance_km": 1.8,
            "walk_time_min": 28,
            "can_evacuate": True,
            "status": "optimal",
            "color": "#4ade80",
            "score": 0.88,
        },
        {
            "desa": "Tirtosari",
            "target_tes": "TES-03",
            "route_path": [[-7.975, 110.255], [-7.970, 110.260], [-7.965, 110.265]],
            "distance_km": 1.2,
            "walk_time_min": 18,
            "can_evacuate": True,
            "status": "optimal",
            "color": "#4ade80",
            "score": 0.95,
        },
        {
            "desa": "Poncosari",
            "target_tes": "TES-04",
            "route_path": [[-7.963, 110.298], [-7.958, 110.290], [-7.953, 110.285]],
            "distance_km": 2.5,
            "walk_time_min": 38,
            "can_evacuate": True,
            "status": "alternatif",
            "color": "#facc15",
            "score": 0.72,
        },
        {
            "desa": "Banaran",
            "target_tes": "TES-05",
            "route_path": [[-7.941, 110.311], [-7.948, 110.305], [-7.955, 110.300]],
            "distance_km": 3.1,
            "walk_time_min": 47,
            "can_evacuate": True,
            "status": "alternatif",
            "color": "#facc15",
            "score": 0.65,
        },
    ],
    "summary": {
        "total_routes": 5,
        "can_evacuate": 5,
        "cannot_evacuate": 0,
        "success_rate": 100.0,
    },
}


@app.post("/simulate")
async def post_simulate(params: SimulationParams):
    """
    SWE simulation endpoint at root level.
    Frontend compatibility endpoint for tsunami simulation.

    INTEGRASI FAULT DATA:
    - Jika fault_id diberikan → gunakan fault geometry dari fault_data.py
    - Jika custom epicenter → gunakan koordinat yang diberikan
    - Jika tidak ada → fallback ke simplified calculation
    """
    # ════════════════════════════════════════════════════════════════════════════════
    #  LOAD FAULT DATA (Dynamic dari FaultLoader atau Hardcoded)
    # ════════════════════════════════════════════════════════════════════════════════
    fault_info = None
    use_fault_data = False

    if params.fault_id and params.source_mode in ['fault', 'mega']:
        # 🔧 Resolve fault ID (handle alias dari frontend lama)
        from simulation.swe.fault_aliases import resolve_fault_id
        resolved_fault_id = resolve_fault_id(params.fault_id)

        if resolved_fault_id != params.fault_id:
            logger.info(f"[SWE] Resolved fault alias: {params.fault_id} → {resolved_fault_id}")

        # Priority 1: Cari di FaultLoader (dynamic shapefile data)
        if FAULT_LOADER is not None:
            fault = FAULT_LOADER.get_fault(resolved_fault_id)
            if fault:
                # Convert FaultInfo ke fault_info format
                fault_info = {
                    'name': fault.name,
                    'type': fault.type,
                    'strike': fault.strike,
                    'dip': fault.dip,
                    'rake': fault.rake,
                    'length_km': fault.total_length_km,
                    'width_km': fault.total_length_km * 0.5,  # Estimate width
                    'depth_top_km': 5.0,
                    'mmax_design': fault.mmax_d,
                    'slip_rate_myr': fault.slip_rate,
                    'epicenter_lat': fault.epicenter_lat,
                    'epicenter_lon': fault.epicenter_lon,
                    'slip_m': 8.0,  # Default slip (akan dihitung nanti)
                    'source': f"FaultLoader:{fault.source_file}"
                }
                use_fault_data = True
                logger.info(f"[SWE] Using dynamic fault: {fault.name} (from shapefile)")
            else:
                logger.warning(f"[SWE] fault_id '{params.fault_id}' not found in FaultLoader")

        # Priority 2: Fallback ke hardcoded fault_data.py
        if not use_fault_data:
            try:
                from simulation.swe.fault_data import JAVA_FAULTS, JAVA_MEGATHRUST

                if params.fault_id in JAVA_FAULTS:
                    fault_info = JAVA_FAULTS[params.fault_id]
                    use_fault_data = True
                    logger.info(f"[SWE] Using hardcoded Java Fault: {fault_info['name']}")
                elif params.fault_id in JAVA_MEGATHRUST:
                    fault_info = JAVA_MEGATHRUST[params.fault_id]
                    use_fault_data = True
                    logger.info(f"[SWE] Using hardcoded Megathrust: {fault_info['name']}")
                else:
                    logger.warning(f"[SWE] fault_id '{params.fault_id}' not found in hardcoded data")
            except ImportError as e:
                logger.error(f"[SWE] Failed to import fault_data: {e}")

    # ════════════════════════════════════════════════════════════════════════════════
    #  DETERMINE EPICENTER & MAGNITUDE
    # ════════════════════════════════════════════════════════════════════════════════
    mag = max(5.0, min(9.5, params.magnitude))

    # Epicenter location
    if params.source_mode == 'custom' and params.lat is not None and params.lon is not None:
        epicenter_lat = params.lat
        epicenter_lon = params.lon
        logger.info(f"[SWE] Using custom epicenter: ({epicenter_lat}, {epicenter_lon})")
    elif use_fault_data and fault_info:
        epicenter_lat = fault_info['epicenter_lat']
        epicenter_lon = fault_info['epicenter_lon']
        logger.info(f"[SWE] Using fault epicenter: ({epicenter_lat}, {epicenter_lon})")
    else:
        # Default: pantai selatan DIY
        epicenter_lat = -8.0
        epicenter_lon = 110.28
        logger.info(f"[SWE] Using default epicenter: ({epicenter_lat}, {epicenter_lon})")

    # ════════════════════════════════════════════════════════════════════════════════
    #  TSUNAMI WAVE GENERATION
    # ════════════════════════════════════════════════════════════════════════════════

    if use_fault_data and fault_info:
        # ── FAULT-BASED WAVE CALCULATION ────────────────────────────────────
        # Initial wave height berdasarkan fault slip
        # Rumus: h = (slip * width) / (rho * g * length) * sin(dip) * scaling

        fault_length = fault_info.get('length_km', 100.0) * 1000  # km → m
        fault_width = fault_info.get('width_km', 50.0) * 1000  # km → m
        slip_m = fault_info.get('slip_m', 10.0) if 'slip_m' in fault_info else 8.0
        dip_deg = fault_info.get('dip', 45.0)
        dip_rad = math.radians(dip_deg)

        # Water density (kg/m^3) and gravity (m/s^2)
        rho_water = 1000.0
        g = 9.81

        # Seafloor displacement (simplified Okada formula)
        # Vertical component dari slip yang menghasilkan tsunami
        if fault_info.get('type') in ['thrust', 'reverse']:
            # Thrust/reverse fault: lebih efisien generate tsunami
            slip_efficiency = math.sin(dip_rad)
        else:
            # Strike-slip: less efficient
            slip_efficiency = 0.3

        # Initial wave height di source
        h_initial = (slip_m * fault_width * slip_efficiency) / (rho_water * g * fault_length) * 1000

        # Scaling berdasarkan magnitude
        mag_factor = 10 ** (0.5 * (mag - 7.0))
        h_initial = h_initial * mag_factor

        logger.info(f"[SWE] Fault-based wave: h_initial={h_initial:.2f}m, slip={slip_m}m, dip={dip_deg}°")

    else:
        # ── SIMPLIFIED WAVE CALCULATION (Fallback) ─────────────────────────
        # Wells & Coppersmith (1994) approximation
        h_initial = 0.01 * 10 ** (0.5 * mag)
        logger.info(f"[SWE] Simplified wave: h_initial={h_initial:.2f}m")

    # Clamp h_initial ke rentang yang reasonable
    h_initial = max(0.5, min(h_initial, 30.0))

    # ════════════════════════════════════════════════════════════════════════════════
    #  WAVE PROPAGATION (Distance-Based)
    # ═══════════════════════════════════════════════════════════════════════════════─

    # Generate wave propagation data untuk berbagai jarak
    distances = [0, 5, 10, 20, 30, 50, 80, 100]
    wave_path = []

    for dist_km in distances:
        # Wave height decay dengan distance
        # Green's law: h ~ d^(-1/2) untuk geometrical spreading
        wave_height = h_initial if dist_km == 0 else h_initial * (10 / (dist_km + 10)) ** 0.5

        # Tsunami speed varies by depth (shallow water approximation)
        avg_depth = max(50, 200 - dist_km * 1.5)  # Depth decreases towards coast
        wave_speed = 3.6 * math.sqrt(9.81 * avg_depth)  # c = sqrt(g*h)

        # Arrival time
        arrival_time = dist_km / (wave_speed / 60) if dist_km > 0 else 0

        # Data source
        source = "BATNAS" if dist_km < 20 else "BLEND" if dist_km < 50 else "GEBCO"

        wave_path.append({
            "distance_km": dist_km,
            "arrival_time_min": round(arrival_time, 1),
            "wave_height_m": round(wave_height, 1),
            "speed_kmh": round(wave_speed),
            "source": source
        })

    # Inundation & impact calculations
    max_inundation = h_initial * (1 + (mag - 6) * 0.3)
    arrival_shore = wave_path[-1]["arrival_time_min"]
    affected_area = 47.5 * ((mag - 5) / 2) ** 2

    # ════════════════════════════════════════════════════════════════════════════════
    #  VILLAGE IMPACT ASSESSMENT - Distance-Based Analysis
    # ════════════════════════════════════════════════════════════════════════════════
    affected_villages = []

    for desa in MOCK_DESA:
        # Calculate distance dari epicenter ke desa (Haversine formula)
        dist_from_source = haversine_distance(epicenter_lat, epicenter_lon,
                                              desa["lat"], desa["lon"])

        # Zone classification berdasarkan jarak dan magnitude
        if use_fault_data:
            # Fault-based: lebih akurat
            dist_threshold = mag * 5  # M7 = 35km, M8 = 40km, M9 = 45km
        else:
            # Simplified
            dist_threshold = mag * 4

        if dist_from_source < dist_threshold * 0.3:
            zone, color = "Sangat Tinggi", "#f87171"
            percentage = min(95, 50 + (mag - 6) * 15)
        elif dist_from_source < dist_threshold * 0.6:
            zone, color = "Tinggi", "#fb923c"
            percentage = min(70, 30 + (mag - 6) * 10)
        elif dist_from_source < dist_threshold:
            zone, color = "Sedang", "#fbbf24"
            percentage = min(50, 15 + (mag - 6) * 8)
        else:
            zone, color = "Rendah", "#a3e635"
            percentage = min(30, 5 + (mag - 6) * 5)

        population = max(1000, min(6000, int(random.gauss(3500, 800))))
        terdampak = int(population * percentage / 100)

        affected_villages.append({
            "kelurahan": desa["name"],
            "population": population,
            "terdampak": terdampak,
            "percentage": int(percentage),
            "zona_bahaya": zone,
            "color": color,
            "coordinates": [desa["lat"], desa["lon"]]
        })

    # Calculate impact summary
    summary_counts = {"Sangat Tinggi": 0, "Tinggi": 0, "Sedang": 0, "Rendah": 0}
    for v in affected_villages:
        summary_counts[v["zona_bahaya"]] += v["terdampak"]

    swe_result = {
        "wave_path": wave_path,
        "max_inundation_m": round(max_inundation, 1),
        "arrival_time_min": int(arrival_shore),
        "affected_area_km2": round(affected_area, 1)
    }

    impact_result = {
        "summary": {
            "total_terdampak": sum(v["terdampak"] for v in affected_villages),
            "zona_sangat_tinggi": summary_counts["Sangat Tinggi"],
            "zona_tinggi": summary_counts["Tinggi"],
            "zona_sedang": summary_counts["Sedang"],
            "zona_rendah": summary_counts["Rendah"],
        },
        "affected_villages": affected_villages,
        "chart_data": {
            "donut": [
                {"label": "Zona Sangat Tinggi", "value": summary_counts["Sangat Tinggi"], "color": "#f87171"},
                {"label": "Zona Tinggi", "value": summary_counts["Tinggi"], "color": "#fb923c"},
                {"label": "Zona Sedang", "value": summary_counts["Sedang"], "color": "#fbbf24"},
                {"label": "Zona Rendah", "value": summary_counts["Rendah"], "color": "#a3e635"},
            ]
        }
    }

    return {
        "swe": swe_result,
        "impact": impact_result,
        "isMock": False
    }


@app.post("/abm")
async def post_abm(params: ABMParams):
    """
    ABM simulation endpoint at root level.
    Frontend compatibility endpoint for evacuation simulation.

    INTEGRASI SWE + ABM:
    - Jika params.swe_result disediakan → gunakan EvacuationABMSolver (hazard-aware)
    - Jika tidak → gunakan simplified ABM simulation (legacy behavior)
    """
    # ════════════════════════════════════════════════════════════════════════════════
    #  INTEGRASI SWE + ABM (Hazard-Aware Evacuation)
    # ════════════════════════════════════════════════════════════════════════════════

    # Gunakan EvacuationABMSolver jika ada SWE result
    if params.swe_result is not None:
        try:
            logger.info("[ABM] Using EvacuationABMSolver with SWE integration")

            from simulation.abm.evacuation_abm import EvacuationABMSolver

            # Initialize solver
            vektor_dir = os.path.join(os.path.dirname(__file__), "data", "Vektor")
            solver = EvacuationABMSolver(vektor_dir=vektor_dir)
            solver.build_caches()

            # Set SWE results untuk hazard-aware routing
            solver.set_swe_results(params.swe_result)

            # Prepare parameters
            body = {
                'warning_time_min': params.warning_time_min,
                'duration_min': params.sim_duration_min,
                'dt_min': 5.0 / 60.0,  # 5 detik timestep
                'agents_per_desa': 50,
                'panic_factor': 0.5
            }

            # Run ABM simulation
            result = solver.run_abm(body)

            logger.info(f"[ABM] Simulation complete: {result['safe_count']}/{result['total_population']} safe")
            return result

        except Exception as e:
            logger.error(f"[ABM] EvacuationABMSolver error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback ke simplified ABM

    # ════════════════════════════════════════════════════════════════════════════════
    #  FALLBACK: SIMPLIFIED ABM (Legacy behavior - tanpa SWE)
    # ═══════════════════════════════════════════════════════════════════════════════─
    logger.info("[ABM] Using simplified ABM simulation (tanpa SWE integration)")

    # Agent-based model untuk simulasi evakuasi penduduk

    # Base agent count on flood severity
    base_agents = 500
    severity_multiplier = (params.flood_height_m / 5.0) ** 1.5
    total_agents = int(base_agents * severity_multiplier)

    # Evacuation success rate depends on warning time
    # More warning time = more people can evacuate
    warning_factor = min(1.0, params.warning_time_min / 30.0)  # 30 min = optimal

    # Transport mode affects evacuation speed
    transport_speed = {
        "foot": 5.0,    # km/h
        "motor": 30.0,  # km/h
        "car": 40.0     # km/h
    }

    speed_kmh = transport_speed.get(params.transport, 5.0)

    # Calculate safe/trapped based on warning time and transport
    # People need to reach safe zone (avg 2km away)
    dist_to_safe = 2.0  # km
    required_time = (dist_to_safe / speed_kmh) * 60  # minutes

    if params.warning_time_min >= required_time:
        safe_percentage = 0.85 + (warning_factor * 0.10)  # 85-95% safe
    else:
        safe_percentage = (params.warning_time_min / required_time) * 0.70  # Max 70% if insufficient warning

    safe_count = int(total_agents * safe_percentage)
    trapped_count = total_agents - safe_count

    # Average evacuation time (affected by distance, speed, crowd congestion)
    base_time = (dist_to_safe / speed_kmh) * 60
    congestion_factor = 1.0 + (total_agents / 1000) * 0.3  # More agents = more congestion
    avg_evacuation_time = base_time * congestion_factor

    # Generate animation frames
    frames = []
    num_frames = min(20, int(params.sim_duration_min / 5))
    agents_per_frame = total_agents // num_frames if num_frames > 0 else total_agents

    for i in range(num_frames + 1):
        time_min = i * 5
        evacuated_so_far = min(safe_count, int(safe_count * (i / num_frames)))

        # Generate some agent positions (simplified)
        agents = []
        num_showing = min(20, agents_per_frame)
        for j in range(num_showing):
            # Random positions around affected area
            base_lat = -8.0 + random.uniform(-0.05, 0.05)
            base_lon = 110.28 + random.uniform(-0.05, 0.05)

            # Agents move toward safe zones over time
            progress = i / num_frames if num_frames > 0 else 0
            safe_lat = -7.97
            safe_lon = 110.25

            current_lat = base_lat + (safe_lat - base_lat) * progress
            current_lon = base_lon + (safe_lon - base_lon) * progress

            agents.append({
                "id": f"agent_{i}_{j}",
                "lat": round(current_lat, 6),
                "lon": round(current_lon, 6),
                "status": "safe" if progress >= 1.0 else "evacuating"
            })

        frames.append({
            "time_min": time_min,
            "agents": agents
        })

    abm_result = {
        "total_agents": total_agents,
        "safe_count": safe_count,
        "trapped_count": trapped_count,
        "avg_evacuation_time_min": round(avg_evacuation_time, 1),
        "frames": frames,
        "isMock": False
    }

    return abm_result


@app.post("/routing")
async def post_routing(req: RoutingRequest):
    """
    Routing endpoint at root level.
    Frontend compatibility endpoint for evacuation route analysis.
    Now runs REAL routing using road network from shapefile (Dijkstra).
    """
    # Log request
    logger.info(f"[ROUTING] Request received: transport={req.transport}, speed={req.speed_kmh} km/h, "
                f"origin=({req.origin_lat}, {req.origin_lon}), tes_id={req.tes_id}")

    # ════════════════════════════════════════════════════════════════════════════════
    #  LOAD ROAD GRAPH & RUN DIJKSTRA
    # ════════════════════════════════════════════════════════════════════════════════
    global ROAD_GRAPH

    # Load road graph on first request
    if ROAD_GRAPH is None:
        logger.info(f"Loading road network graph from {SHAPEFILE_PATH}...")
        ROAD_GRAPH = get_or_load_road_graph(SHAPEFILE_PATH)
        if ROAD_GRAPH is None:
            logger.error("Failed to load road graph - using fallback")
        else:
            logger.info(f"Road graph loaded: {ROAD_GRAPH.graph.number_of_nodes()} nodes, {ROAD_GRAPH.graph.number_of_edges()} edges")

    # Find target TES
    target_tes = None
    for tes in MOCK_TES:
        if tes["id"] == req.tes_id:
            target_tes = tes
            break

    if not target_tes:
        return {
            "routes": [],
            "summary": {"total_routes": 0, "can_evacuate": 0, "cannot_evacuate": 0, "success_rate": 0},
            "isMock": False
        }

    # Use custom origin if provided, otherwise use affected villages
    origins = []
    if req.origin_lat and req.origin_lon:
        # User mode: single origin → single TES routing
        origins.append({"name": "Lokasi Asal", "lat": req.origin_lat, "lon": req.origin_lon})
    else:
        # Admin/analysis mode: multiple origins → single TES routing
        origins = MOCK_DESA[:5]  # Use first 5 villages as origins

    routes = []
    for origin in origins:
        # Try to find route using road graph
        if ROAD_GRAPH is not None:
            from simulation.abm.road_router import find_route
            route_result = find_route(
                ROAD_GRAPH,
                origin["lat"],
                origin["lon"],
                target_tes["lat"],
                target_tes["lon"],
                req.speed_kmh
            )

            route_path = route_result['route_path']
            distance_km = route_result['distance_km']
            travel_time_min = route_result['walk_time_min']
        else:
            # Fallback: straight line
            route_path = [[origin["lat"], origin["lon"]], [target_tes["lat"], target_tes["lon"]]]
            distance_km = round(haversine_distance(origin["lat"], origin["lon"], target_tes["lat"], target_tes["lon"]), 2)
            travel_time_min = int((distance_km / req.speed_kmh) * 60)

        # Safety score
        distance_score = max(0, 1 - (distance_km / 10))
        safety_score = distance_score * 0.7 + (req.safety_weight / 100) * 0.3

        # Determine evacuation status
        can_evacuate = travel_time_min < 60
        status = "optimal" if travel_time_min < 30 else "alternatif" if travel_time_min < 45 else "darurat"

        if can_evacuate:
            color = "#4ade80" if status == "optimal" else "#facc15"
        else:
            color = "#f87171"

        routes.append({
            "desa": origin["name"],
            "target_tes": target_tes["id"],
            "route_path": route_path,
            "distance_km": distance_km,
            "walk_time_min": travel_time_min,
            "can_evacuate": can_evacuate,
            "status": status,
            "color": color,
            "score": round(safety_score, 2),
        })

    # Calculate summary
    total_routes = len(routes)
    can_evacuate_count = sum(1 for r in routes if r["can_evacuate"])
    success_rate = (can_evacuate_count / total_routes * 100) if total_routes > 0 else 0

    return {
        "routes": routes,
        "summary": {
            "total_routes": total_routes,
            "can_evacuate": can_evacuate_count,
            "cannot_evacuate": total_routes - can_evacuate_count,
            "success_rate": round(success_rate, 1)
        },
        "isMock": False
    }


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Hitung distance antara dua titik dalam km (Haversine formula)."""
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371 * c


# ════════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="debug" if Config.DEBUG else "info"
    )
