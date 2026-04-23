"""
server.py — WebGIS Tsunami Simulation Backend
API Gateway (FastAPI) - Orchestration layer only
==================================================
Logika bisnis dihandle di simulation/core/
Cache builders di simulation/core/cache.py
"""

import os
import math
import asyncio
import random
from typing import Optional, Any, Dict, List, Tuple
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

# Import simulation modules
from simulation.core.cache import build_road_cache, build_desa_cache, build_tes_cache
from simulation.core.evacuation_abm import EvacuationABMSolver
from simulation.core.swe_solver import TsunamiSimulator
from simulation.core.spatial_utils import MasterBathymetry, DEMManager

# ── Global state ──────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RASTER_DIR = os.path.join(DATA_DIR, "Raster")
VEKTOR_DIR = os.path.join(DATA_DIR, "Vektor")
BATNAS_DIR = os.path.join(RASTER_DIR, "BATNAS")
GEBCO_DIR = os.path.join(RASTER_DIR, "GEBCO_18_Mar_2026_54f29d9cc882")
DEMNAS_DIR = os.path.join(RASTER_DIR, "DEMNAS")

# Caches
ROAD_GEOJSON_CACHE: Optional[dict] = None
ROAD_GRAPH_CACHE: Optional[dict] = None
DESA_CACHE: Optional[dict] = None
TES_CACHE: Optional[dict] = None

# Managers
MASTER_BATHY: Optional[MasterBathymetry] = None
DEM_MANAGER: Optional[DEMManager] = None
ABM_SOLVER: Optional[EvacuationABMSolver] = None

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
    global MASTER_BATHY, DEM_MANAGER, ABM_SOLVER

    print("\n🚀 [Startup] Membangun data caches...")
    loop = asyncio.get_event_loop()

    if os.path.isdir(VEKTOR_DIR):
        print(f"📂 VEKTOR_DIR: {VEKTOR_DIR}")
        DESA_CACHE = await loop.run_in_executor(None, build_desa_cache, VEKTOR_DIR)
        TES_CACHE = await loop.run_in_executor(None, build_tes_cache, VEKTOR_DIR)
        ROAD_GEOJSON_CACHE = await loop.run_in_executor(None, build_road_cache, VEKTOR_DIR)
    else:
        print(f"⚠ VEKTOR_DIR tidak ditemukan: {VEKTOR_DIR}")

    print(f"📂 BATNAS_DIR: {BATNAS_DIR}")
    print(f"📂 GEBCO_DIR: {GEBCO_DIR}")
    MASTER_BATHY = MasterBathymetry(
        BATNAS_DIR if os.path.isdir(BATNAS_DIR) else None,
        GEBCO_DIR if os.path.isdir(GEBCO_DIR) else None,
    )

    if os.path.isdir(DEMNAS_DIR):
        print(f"📂 DEMNAS_DIR: {DEMNAS_DIR}")
        DEM_MANAGER = DEMManager(DEMNAS_DIR)
    else:
        print(f"⚠ DEMNAS_DIR tidak ditemukan: {DEMNAS_DIR}")
        DEM_MANAGER = None

    ABM_SOLVER = EvacuationABMSolver(vektor_dir=VEKTOR_DIR, dem_mgr=DEM_MANAGER)
    await loop.run_in_executor(None, ABM_SOLVER.build_caches)

    print("\n✅ [Startup] Cache siap")


def _default_epicenter() -> Tuple[float, float]:
    if DESA_CACHE and DESA_CACHE.get("desa"):
        d = DESA_CACHE["desa"][0]
        lat = d.get("lat") if d.get("lat") is not None else -8.2
        lon = d.get("lon") if d.get("lon") is not None else 110.28
        return float(lat), float(lon)
    return -8.2, 110.28


def _build_wave_path(stats: dict) -> list:
    dist_km = float(stats.get("dist_to_bantul_km", 30.0))
    arrival_min = float(stats.get("arrival_time_min", 30.0))
    max_h = float(stats.get("h0_final_m", 5.0))
    points = []
    for factor, source in [
        (0.0, "BLEND"),
        (0.1, "BLEND"),
        (0.3, "BLEND"),
        (0.6, "BLEND"),
        (1.0, "GEBCO"),
        (1.5, "GEBCO"),
    ]:
        km = round(dist_km * factor, 1)
        arrival = round(max(0.0, km / max(1.0, dist_km) * arrival_min), 1)
        height = round(max(0.2, max_h * math.exp(-factor * 1.2)), 2)
        speed = round(max(120.0, km / max(1e-6, arrival / 60) if arrival > 0 else 600.0), 1)
        points.append({
            "distance_km": km,
            "arrival_time_min": arrival,
            "wave_height_m": height,
            "speed_kmh": speed,
            "source": source,
        })
    return points


def _build_impact_result(stats: dict) -> dict:
    area_km2 = float(stats.get("inundation_area_km2", 5.0))
    total = max(1, int(area_km2 * 150))
    high = max(0, int(total * 0.25))
    medium = max(0, int(total * 0.30))
    low = max(0, int(total * 0.25))
    very_low = max(0, total - high - medium - low)
    villages = []
    source_villages = []
    if DESA_CACHE and DESA_CACHE.get("desa"):
        source_villages = DESA_CACHE["desa"][:6]
    else:
        source_villages = [
            {"name": "Gadingsari", "lat": -8.042, "lon": 110.254},
            {"name": "Srigading", "lat": -8.039, "lon": 110.281},
            {"name": "Tirtosari", "lat": -8.042, "lon": 110.305},
        ]
    for idx, village in enumerate(source_villages):
        percentage = 80 - idx * 12
        villages.append({
            "kelurahan": village.get("name", f"Desa {idx+1}"),
            "population": max(100, int(total * 0.05)),
            "terdampak": max(50, int(total * 0.04)),
            "percentage": max(10, min(90, percentage)),
            "zona_bahaya": "Sangat Tinggi" if idx == 0 else "Tinggi" if idx == 1 else "Sedang",
            "color": "#f87171" if idx < 2 else "#fb923c",
            "coordinates": [
                float(village.get("lat", -8.0)),
                float(village.get("lon", 110.28)),
            ],
        })
    return {
        "summary": {
            "total_terdampak": total,
            "zona_sangat_tinggi": high,
            "zona_tinggi": medium,
            "zona_sedang": low,
            "zona_rendah": very_low,
        },
        "affected_villages": villages,
        "chart_data": {
            "donut": [
                {"label": "Zona Sangat Tinggi", "value": high, "color": "#f87171"},
                {"label": "Zona Tinggi", "value": medium, "color": "#fb923c"},
                {"label": "Zona Sedang", "value": low, "color": "#fbbf24"},
                {"label": "Zona Rendah", "value": very_low, "color": "#a3e635"},
            ],
        },
    }


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
# Simulation and evacuation endpoints
# ═══════════════════════════════════════════════════════════════

@app.post("/simulate")
async def run_simulation(body: Dict[str, Any]):
    """
    Simulasi tsunami SWE.
    """
    if body is None:
        raise HTTPException(status_code=400, detail="Body JSON diperlukan")

    mw = float(body.get("magnitude") or body.get("mw") or 6.5)
    fault_type = str(body.get("fault_type", "vertical"))
    source_mode = str(body.get("source_mode", "fault"))
    depth_km = float(body.get("depth_km", 20.0))
    duration_min = float(body.get("duration_min", 45.0))

    if source_mode == "custom" and body.get("lat") is not None and body.get("lon") is not None:
        epicenter_lat = float(body["lat"])
        epicenter_lon = float(body["lon"])
    else:
        epicenter_lat, epicenter_lon = _default_epicenter()

    is_megathrust = source_mode == "mega"
    try:
        simulator = TsunamiSimulator()
        simulator.bathy = MASTER_BATHY or MasterBathymetry(
            BATNAS_DIR if os.path.isdir(BATNAS_DIR) else None,
            GEBCO_DIR if os.path.isdir(GEBCO_DIR) else None,
        )
        result = simulator.run(
            epicenter_lat=epicenter_lat,
            epicenter_lon=epicenter_lon,
            mw=mw,
            fault_type=fault_type,
            depth_km=depth_km,
            duration_min=duration_min,
            is_megathrust=is_megathrust,
            dem_manager=DEM_MANAGER,
            save_frames=10,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulasi SWE gagal: {exc}")

    stats = result.get("statistics", {})
    swe = {
        "wave_path": _build_wave_path(stats),
        "max_inundation_m": float(stats.get("runup_bantul_m", 0.0)),
        "arrival_time_min": float(stats.get("arrival_time_min", 0.0)),
        "affected_area_km2": float(stats.get("inundation_area_km2", 0.0)),
        "inundation_geojson": result.get("inundation_geojson"),
    }
    impact = _build_impact_result(stats)
    return {"swe": swe, "impact": impact}


@app.post("/network/routing")
async def analyze_routing(body: Dict[str, Any]):
    """
    Analisis rute evakuasi.
    """
    if body is None:
        raise HTTPException(status_code=400, detail="Body JSON diperlukan")
    if ABM_SOLVER is None:
        raise HTTPException(status_code=500, detail="Solver ABM tidak tersedia")

    transport = str(body.get("transport", "foot"))
    speed_kmh = float(body.get("speed_kmh", 5.0))
    safety_weight = float(body.get("safety_weight", 30.0))
    origin_lat = body.get("origin_lat")
    origin_lon = body.get("origin_lon")
    tes_id = body.get("tes_id")

    if origin_lat is None or origin_lon is None:
        if DESA_CACHE and DESA_CACHE.get("desa"):
            origin = DESA_CACHE["desa"][0]
            origin_lat = origin.get("lat") if origin.get("lat") is not None else -8.2
            origin_lon = origin.get("lon") if origin.get("lon") is not None else 110.28
        else:
            origin_lat, origin_lon = -8.2, 110.28
    origin = {"lat": float(origin_lat), "lon": float(origin_lon)}

    destination = None
    if tes_id and TES_CACHE and TES_CACHE.get("tes"):
        for tes in TES_CACHE["tes"]:
            if str(tes.get("name", "")).lower() == str(tes_id).lower() or str(tes.get("id", "")).lower() == str(tes_id).lower():
                destination = tes
                break
    if destination is None:
        if TES_CACHE and TES_CACHE.get("tes"):
            destination = TES_CACHE["tes"][0]
        else:
            destination = {"name": "TES Default", "lat": -8.0, "lon": 110.28}

    weight = "composite"
    if safety_weight < 20:
        weight = "distance"
    elif safety_weight > 45:
        weight = "time"

    try:
        route_data = ABM_SOLVER.compute_route(
            origin=origin,
            destination={"lat": float(destination["lat"]), "lon": float(destination["lon"]), "name": destination.get("name", "TES")},
            method="network",
            transport=transport,
            weight=weight,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rute evakuasi gagal: {exc}")

    if route_data.get("error"):
        raise HTTPException(status_code=500, detail=route_data["error"])

    routes = []
    for route in route_data.get("routes", []):
        status = "optimal"
        if route.get("has_flood_risk"):
            status = "darurat"
        elif route.get("method", "").lower().startswith("dijkstra_time"):
            status = "alternatif"

        routes.append({
            "desa": origin.get("name", "Asal"),
            "target_tes": destination.get("name", "TES"),
            "route_path": route.get("path", []),
            "distance_km": float(route.get("distance_km", 0.0)),
            "walk_time_min": float(route.get("time_min", 0.0)),
            "can_evacuate": not bool(route.get("has_flood_risk")),
            "status": status,
            "color": route.get("color", "#60a5fa"),
            "score": round(max(0.0, 1.0 - float(route.get("distance_km", 0.0)) / 10.0), 2),
        })

    summary = {
        "total_routes": len(routes),
        "can_evacuate": sum(1 for r in routes if r["can_evacuate"]),
        "cannot_evacuate": sum(1 for r in routes if not r["can_evacuate"]),
        "success_rate": int(round(100 * sum(1 for r in routes if r["can_evacuate"]) / max(1, len(routes)))),
    }
    return {"routes": routes, "summary": summary}


@app.post("/routing")
async def analyze_routing_alias(body: Dict[str, Any]):
    return await analyze_routing(body)


@app.post("/abm/simulate")
async def run_abm(body: Dict[str, Any]):
    """
    Simulasi Agent-Based Model evakuasi.
    """
    if body is None:
        raise HTTPException(status_code=400, detail="Body JSON diperlukan")
    if ABM_SOLVER is None:
        raise HTTPException(status_code=500, detail="Solver ABM tidak tersedia")

    transport = str(body.get("transport", "foot"))
    warning_time_min = float(body.get("warning_time_min", 20.0))
    sim_duration_min = float(body.get("sim_duration_min", 120.0))
    flood_height_m = float(body.get("flood_height_m", 5.0))

    desa_list = DESA_CACHE.get("desa") if DESA_CACHE else []
    tes_list = TES_CACHE.get("tes") if TES_CACHE else []
    roads = ABM_SOLVER.road_cache.get("roads") if ABM_SOLVER and ABM_SOLVER.road_cache else []

    body_payload = {
        "desa_list": desa_list,
        "tes_list": tes_list,
        "roads": roads,
        "transport": transport,
        "warning_time_min": warning_time_min,
        "sim_duration_min": sim_duration_min,
        "inundation_runup_m": flood_height_m,
        "use_osm_buildings": False,
        "osm_timeout": 5,
    }
    try:
        abm_data = ABM_SOLVER.run_abm(body_payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulasi ABM gagal: {exc}")

    if abm_data.get("error"):
        raise HTTPException(status_code=500, detail=abm_data["error"])

    agents = abm_data.get("agents", [])
    timeline = []
    for frame in abm_data.get("timeline", []):
        agents_frame = []
        for pos in frame.get("positions", []):
            status_map = {
                "waiting": "evacuating",
                "moving": "evacuating",
                "arrived": "safe",
                "stranded": "trapped",
            }
            agents_frame.append({
                "id": pos.get("id", ""),
                "lat": float(pos.get("lat", 0.0)),
                "lon": float(pos.get("lon", 0.0)),
                "status": status_map.get(pos.get("status", ""), "evacuating"),
            })
        timeline.append({"time_min": float(frame.get("t_min", 0.0)), "agents": agents_frame})

    return {
        "total_agents": len(agents),
        "safe_count": sum(1 for a in agents if a.get("status") == "arrived"),
        "trapped_count": sum(1 for a in agents if a.get("status") == "stranded"),
        "avg_evacuation_time_min": float(abm_data.get("summary", {}).get("avg_time_min", 0.0)),
        "frames": timeline,
    }


@app.post("/abm")
async def run_abm_alias(body: Dict[str, Any]):
    return await run_abm(body)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
