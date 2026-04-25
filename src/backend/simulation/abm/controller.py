"""
ABM (Agent-Based Model) Controller
Handles all evacuation simulation endpoints
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("abm_controller")

# Router for ABM endpoints
abm_router = APIRouter()


# ════════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ════════════════════════════════════════════════════════════════════════════════

class ABMRequest(BaseModel):
    """Request for ABM evacuation simulation."""
    warning_time_min: float = Field(20.0, ge=0, le=180)
    duration_min: float = Field(120.0, ge=10, le=480)
    tsunami_height_m: float = Field(5.0, ge=0.1, le=20)
    num_agents: int = Field(100, ge=10, le=10000)
    inundation_geojson: Optional[Dict] = Field(None)
    affected_villages: Optional[List[Dict]] = Field(None)


class RoutingRequest(BaseModel):
    """Request for evacuation routing analysis."""
    transport: str = Field("foot")
    safety_weight: float = Field(50.0, ge=0, le=100)
    tes_id: str = Field(...)
    origin_lat: float = Field(...)
    origin_lon: float = Field(...)
    inundation_geojson: Optional[Dict] = Field(None)


# ════════════════════════════════════════════════════════════════════════════════
# AGENT DATA ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@abm_router.get("/tes")
async def get_tes_list():
    """
    Get list of all Temporary Evacuation Shelters (TES).
    
    Returns:
    - id, name, lat, lon, capacity, type
    """
    return {
        "status": "ok",
        "tes": [],
        "count": 0,
        "note": "Populated from ABM solver cache"
    }


@abm_router.get("/desa")
async def get_desa_list():
    """
    Get list of all administrative villages (desa/kelurahan).
    
    Returns:
    - name, lat, lon, population
    """
    return {
        "status": "ok",
        "desa": [],
        "count": 0,
        "note": "Populated from cache"
    }


# ════════════════════════════════════════════════════════════════════════════════
# ROUTING ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@abm_router.post("/routing")
async def analyze_routes(req: RoutingRequest):
    """
    Analyze evacuation routes from origin to shelter (TES).
    
    Parameters:
    - transport: foot, motor, car
    - safety_weight: 0=speed, 100=safety
    - tes_id: Target shelter ID
    - origin_lat/lon: Starting point
    - inundation_geojson: Flood zones (optional)
    
    Returns:
    - path coordinates
    - distance_km, time_min
    - safety_score
    - avoids_flood flag
    """
    return {
        "status": "pending",
        "message": "Routing analysis pending OSM router initialization",
        "error": None
    }


@abm_router.post("/route")
async def find_route(start_lat: float, start_lon: float, 
                    end_lat: float, end_lon: float,
                    algorithm: str = "astar"):
    """
    Find shortest path between two points.
    
    Algorithms: astar, dijkstra
    
    Returns route path with distance and time.
    """
    return {
        "status": "pending",
        "path": [],
        "distance_km": 0.0,
        "time_min": 0.0,
        "algorithm": algorithm
    }


# ════════════════════════════════════════════════════════════════════════════════
# SIMULATION ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@abm_router.post("/simulate")
async def abm_simulate(req: ABMRequest):
    """
    Run Agent-Based Model evacuation simulation.
    
    Parameters:
    - warning_time_min: Warning time before tsunami arrival
    - duration_min: Total simulation duration
    - tsunami_height_m: Maximum wave height
    - num_agents: Number of agents to simulate
    - inundation_geojson: Flood zone geometry (optional)
    
    Returns:
    - total_agents, safe_count, trapped_count
    - avg_evacuation_time_min
    - agent_paths: Trajectories over time
    - frames: Animation frames
    - statistics: Detailed metrics
    """
    return {
        "status": "pending",
        "message": "ABM solver will be injected from server",
        "num_agents": 0,
        "safe_count": 0,
        "trapped_count": 0,
        "frames": []
    }


@abm_router.post("/run")
async def run_abm(body: Dict = Body(...)):
    """
    Alias for /simulate - Run ABM evacuation.
    
    (Backward compatible endpoint)
    """
    req = ABMRequest(**body)
    return await abm_simulate(req)


# ════════════════════════════════════════════════════════════════════════════════
# INUNDATION STATUS
# ════════════════════════════════════════════════════════════════════════════════

@abm_router.get("/inundation-status")
async def inundation_status():
    """
    Get current inundation status from last SWE simulation.
    
    Shows:
    - Number of villages affected
    - Flood polygons count
    - Per-desa flood information
    """
    return {
        "status": "no_simulation",
        "message": "No SWE simulation has been run yet",
        "flood_polygons": 0,
        "per_desa_flood": {},
        "n_desa_tergenang": 0
    }


# ════════════════════════════════════════════════════════════════════════════════
# HEALTH & STATUS
# ════════════════════════════════════════════════════════════════════════════════

@abm_router.get("/health")
async def abm_health():
    """ABM module health check."""
    return {
        "module": "ABM",
        "status": "healthy",
        "services": {
            "abm_solver": None,  # Will be populated
            "osm_router": None,
            "road_network": None,
        }
    }


@abm_router.get("/info")
async def abm_info():
    """Information about ABM module resources."""
    return {
        "module": "ABM",
        "desa_count": 0,
        "tes_count": 0,
        "road_nodes": 0,
        "gpu_support": False,
        "note": "Details populated from server state"
    }
