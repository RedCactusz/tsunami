"""
server.py — WebGIS Tsunami Simulation Backend
API Gateway (FastAPI) - Orchestration layer only
==================================================
Logika bisnis dihandle di simulation/core/
Cache builders di simulation/core/cache.py
"""

import os
import asyncio
from typing import Optional, Any, Dict
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

# Import simulation modules
from simulation.core.cache import build_road_cache, build_desa_cache, build_tes_cache
from simulation.core.spatial_utils import MasterBathymetry, DEMManager

# ── Global state ──────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RASTER_DIR = os.path.join(DATA_DIR, "Raster")
VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")

# Caches
ROAD_GEOJSON_CACHE: Optional[dict] = None
ROAD_GRAPH_CACHE: Optional[dict] = None
DESA_CACHE: Optional[dict] = None
TES_CACHE: Optional[dict] = None

# Managers
manager: Optional[MasterBathymetry] = None
dem_manager: Optional[DEMManager] = None

# ── FastAPI setup ─────────────────────────────────────────────
app = FastAPI(title="WebGIS Tsunami API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# ═══════════════════════════════════════════════════════════════
# STARTUP EVENTS
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Initialize caches on startup."""
    global ROAD_GEOJSON_CACHE, DESA_CACHE, TES_CACHE
    
    print("\n🚀 [Startup] Membangun data caches...")
    loop = asyncio.get_event_loop()
    
    if os.path.isdir(VEKTOR_DIR):
        print(f"📂 VEKTOR_DIR: {VEKTOR_DIR}")
        DESA_CACHE = await loop.run_in_executor(None, build_desa_cache, VEKTOR_DIR)
        TES_CACHE = await loop.run_in_executor(None, build_tes_cache, VEKTOR_DIR)
        ROAD_GEOJSON_CACHE = await loop.run_in_executor(None, build_road_cache, VEKTOR_DIR)
    else:
        print(f"⚠ VEKTOR_DIR tidak ditemukan: {VEKTOR_DIR}")
    
    print("\n✅ [Startup] Cache siap")


# ═══════════════════════════════════════════════════════════════
# API ENDPOINTS — Status & Admin Data
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint."""
    return {"app": "WebGIS Tsunami", "status": "online"}


@app.get("/admin/desa")
async def get_desa():
    """Get desa (kelurahan) data."""
    if DESA_CACHE:
        return {
            "source": "geojson_cache",
            "source_file": DESA_CACHE.get("source_file"),
            "count": DESA_CACHE.get("count"),
            "desa": DESA_CACHE.get("desa", []),
        }
    return {"source": "none", "desa": []}


@app.get("/admin/tes")
async def get_tes():
    """Get TES (Titik Evakuasi Sementara) data."""
    if TES_CACHE:
        return {
            "source": "geojson_cache",
            "source_file": TES_CACHE.get("source_file"),
            "count": TES_CACHE.get("count"),
            "tes": TES_CACHE.get("tes", []),
        }
    return {"source": "none", "tes": []}


@app.get("/network/roads")
async def get_roads():
    """Get road network data."""
    if ROAD_GEOJSON_CACHE:
        return {
            "source": "geojson_cache",
            "source_file": ROAD_GEOJSON_CACHE.get("source_file"),
            "count": ROAD_GEOJSON_CACHE.get("feature_count"),
            "roads": ROAD_GEOJSON_CACHE.get("roads", []),
        }
    return {"source": "none", "roads": []}


# ═══════════════════════════════════════════════════════════════
# PLACEHOLDER ENDPOINTS — Import dari simulation/core nanti
# ═══════════════════════════════════════════════════════════════

@app.post("/simulate")
async def run_simulation(body: Dict[str, Any]):
    """
    Simulasi tsunami SWE.
    
    TODO: Import dari simulation/core/swe_solver.py
    Request body:
        {
            "epicenter_lat": float,
            "epicenter_lon": float,
            "mw": float (magnitude),
            "fault_type": str,
            ...
        }
    """
    return {"error": "Endpoint tidak aktif — swe_solver belum diintegrasikan"}


@app.post("/network/routing")
async def analyze_routing(body: Dict[str, Any]):
    """
    Analisis rute evakuasi.
    
    TODO: Import dari simulation/core/evacuation_abm.py
    """
    return {"error": "Endpoint tidak aktif — evacuation_abm belum diintegrasikan"}


@app.post("/abm/simulate")
async def run_abm(body: Dict[str, Any]):
    """
    Simulasi Agent-Based Model evakuasi.
    
    TODO: Import dari simulation/core/evacuation_abm.py
    """
    return {"error": "Endpoint tidak aktif — evacuation_abm belum diintegrasikan"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
