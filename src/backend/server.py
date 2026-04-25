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
    """
    return {
        "swe": MOCK_SWE_RESULT,
        "impact": MOCK_IMPACT_RESULT,
    }


@app.post("/abm")
async def post_abm(params: ABMParams):
    """
    ABM simulation endpoint at root level.
    Frontend compatibility endpoint for evacuation simulation.
    """
    return MOCK_ABM_RESULT


@app.post("/routing")
async def post_routing(req: RoutingRequest):
    """
    Routing endpoint at root level.
    Frontend compatibility endpoint for evacuation route analysis.
    
    Parameters:
    - transport: foot, motor, car
    - speed_kmh: Average travel speed
    - safety_weight: 0=speed optimized, 100=safety optimized
    - origin_lat/lon: Starting coordinates
    - tes_id: Target evacuation shelter ID
    
    Returns: RoutingResult with evacuation routes
    """
    return MOCK_ROUTING_RESULT


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
