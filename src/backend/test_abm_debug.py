#!/usr/bin/env python
"""Quick debug test untuk check ABM agent generation."""

import logging
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

from simulation.abm.evacuation_abm import EvacuationABMSolver

# Initialize solver
vektor_dir = os.path.join(os.path.dirname(__file__), "data", "Vektor")
solver = EvacuationABMSolver(vektor_dir=vektor_dir)
solver.build_caches()

# Manually create swe_result with grid metadata
swe_result = {
    "wave_path": [],
    "max_inundation_m": 5.0,
    "arrival_time_min": 10,
    "affected_area_km2": 50.0,
    "runup_m": 24.0,
    "inundation_geojson": {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [110.25, -8.00]},
                "properties": {"flood_depth": 2.5, "risk": "TINGGI"}
            }
        ] * 100,  # 100 points untuk test
        # Grid metadata
        "lat_min": -8.03,
        "lat_max": -7.95,
        "lon_min": 110.21,
        "lon_max": 110.35,
        "ny": 100,
        "nx": 150,
        "lats": [-8.03 + i*0.0008 for i in range(100)],
        "lons": [110.21 + i*0.0008 for i in range(150)],
    }
}

print("\n" + "=" * 70)
print("TEST: Setting SWE results with grid metadata")
print("=" * 70)
solver.set_swe_results(swe_result)

print("\n" + "=" * 70)
print("TEST: Generating agents")
print("=" * 70)
agents = solver._generate_agents(agents_per_desa=50, panic_factor=0.5)

print(f"\n✅ SUCCESS: Generated {len(agents)} agents")
if agents:
    print(f"   First agent: ID={agents[0].id}, desa={agents[0].desa_name}, "
          f"speed={agents[0].speed_mps:.2f} m/s, transport={agents[0].transport_mode}")
else:
    print("   ❌ FAILED: No agents generated!")
    sys.exit(1)
