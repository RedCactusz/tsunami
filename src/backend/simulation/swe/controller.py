"""
SWE (Shallow Water Equations) Controller
Handles all tsunami simulation endpoints
"""

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging

# Import from shared core module
from ..core import validate_coordinates, wave_speed

logger = logging.getLogger("swe_controller")

# Router for SWE endpoints
swe_router = APIRouter()



# ════════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════════════════════

class DepthQuery(BaseModel):
    """Single point bathymetry query."""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class SimulateRequest(BaseModel):
    """Request for SWE tsunami simulation."""
    scenario_id: str = Field("default", description="Scenario ID")
    magnitude: Optional[float] = Field(None, ge=5.0, le=9.5)
    duration_min: float = Field(60.0, ge=1.0, le=180.0)
    resolution_mode: str = Field("auto")
    custom_epicenter: Optional[Dict[str, float]] = Field(None)
    depth_km: Optional[float] = Field(None, ge=1.0, le=100.0)


# ════════════════════════════════════════════════════════════════════════════════
# BATHYMETRY ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@swe_router.get("/depth")
async def query_depth(lat: float = Query(...), lon: float = Query(...)):
    """
    Query depth/elevation pada titik tertentu.
    Returns: depth_m, is_ocean flag, wave speed.
    """
    if not validate_coordinates(lat, lon):
        raise HTTPException(400, "Invalid coordinates")
    
    # Note: app_state akan di-inject dari server.py
    return {
        "lat": lat,
        "lon": lon,
        "depth_m": None,
        "is_ocean": None,
        "source": "pending",
        "note": "Bathymetry managers akan di-inject dari server"
    }


@swe_router.post("/depth/batch")
async def query_depth_batch(points: List[DepthQuery] = Body(...)):
    """
    Batch query untuk multiple points.
    Max 1000 points per request.
    """
    if len(points) > 1000:
        raise HTTPException(400, "Max 1000 points per request")
    
    results = [
        {
            "lat": p.lat,
            "lon": p.lon,
            "depth_m": None,
            "source": "pending"
        }
        for p in points
    ]
    
    return {"results": results, "count": len(results)}


# ════════════════════════════════════════════════════════════════════════════════
# SIMULATION ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@swe_router.get("/scenarios")
async def get_scenarios():
    """
    Get available tsunami scenarios (public labels only).
    No technical fault parameters exposed.
    """
    return {
        "status": "ok",
        "scenarios": [],  # Will be populated from fault_data
        "note": "List populated from FAULT_PUBLIC_LABELS"
    }


@swe_router.post("/simulate")
async def simulate_tsunami(req: SimulateRequest):
    """
    Run SWE tsunami simulation.
    
    Returns:
    - max_wave_height_m
    - inundation_area_km2
    - arrival_time_min
    - affected_villages
    - inundation_geojson
    - statistics
    """
    return {
        "status": "pending",
        "message": "SWE solver will be injected from server",
        "success": False
    }


@swe_router.get("/scaling/wells-coppersmith")
async def scaling_wc(magnitude: float, fault_type: str = "thrust"):
    """
    Wells & Coppersmith (1994) scaling relations for earthquakes.
    """
    if not (5.0 <= magnitude <= 9.5):
        raise HTTPException(400, "Magnitude must be 5.0-9.5")
    
    return {
        "magnitude": magnitude,
        "fault_type": fault_type,
        "reference": "Wells & Coppersmith (1994)",
        "note": "Scaling computed via simulation.swe.swe_solver"
    }


@swe_router.get("/scaling/blaser")
async def scaling_blaser(magnitude: float, fault_type: str = "thrust"):
    """
    Blaser et al. (2010) scaling relations (subduction zones).
    """
    if not (5.0 <= magnitude <= 9.5):
        raise HTTPException(400, "Magnitude must be 5.0-9.5")
    
    return {
        "magnitude": magnitude,
        "fault_type": fault_type,
        "reference": "Blaser et al. (2010)",
        "note": "Scaling computed via simulation.swe.swe_solver"
    }


# ════════════════════════════════════════════════════════════════════════════════
# HEALTH & STATUS
# ════════════════════════════════════════════════════════════════════════════════

@swe_router.get("/health")
async def swe_health():
    """SWE module health check."""
    return {
        "module": "SWE",
        "status": "healthy",
        "services": {
            "swe_solver": None,  # Will be populated
            "bathymetry_managers": None,
            "inundation_connector": None,
        }
    }


@swe_router.get("/info")
async def swe_info():
    """Information about SWE module resources."""
    return {
        "module": "SWE",
        "bathymetry_tiles": 0,
        "scenarios_available": 0,
        "gpu_support": False,
        "note": "Details populated from server state"
    }
