# Restructuring Plan - Cross-Check

## Current Structure
```
simulation/core/
├── swe_solver.py
├── swe_accelerated.py
├── fault_data.py
├── inundation_connector.py
├── evacuation_abm.py
├── abm_accelerated.py
├── osm_router.py
├── spatial_utils.py       ← SHARED
└── cache.py               ← SHARED
```

## Proposed New Structure

### 1. **simulation/core/** (Shared Utils - KEEP)
```
simulation/core/
├── spatial_utils.py     ✅ KEEP (used by both SWE & ABM)
├── cache.py             ✅ KEEP (used by both)
└── __init__.py
```

### 2. **simulation/swe/** (SWE Logic - NEW FOLDER)
```
simulation/swe/
├── swe_solver.py             ← MOVE from core
├── swe_accelerated.py        ← MOVE from core
├── fault_data.py             ← MOVE from core
├── inundation_connector.py   ← MOVE from core
├── controller.py             ← NEW (SWE FastAPI router)
└── __init__.py
```

### 3. **simulation/abm/** (ABM Logic - NEW FOLDER)
```
simulation/abm/
├── evacuation_abm.py         ← MOVE from core
├── abm_accelerated.py        ← MOVE from core
├── osm_router.py             ← MOVE from core
├── controller.py             ← NEW (ABM FastAPI router)
└── __init__.py
```

### 4. **server.py** (Orchestrator Only - SIMPLIFIED)
```python
# HIGH LEVEL:
from simulation.swe.controller import swe_router
from simulation.abm.controller import abm_router

app = FastAPI()
app.include_router(swe_router, prefix="/api/swe", tags=["SWE"])
app.include_router(abm_router, prefix="/api/abm", tags=["ABM"])

# Minimal setup, controllers handle their own endpoints
```

---

## File Movement Summary

### TO: simulation/swe/
1. ✅ swe_solver.py
2. ✅ swe_accelerated.py
3. ✅ fault_data.py
4. ✅ inundation_connector.py

### TO: simulation/abm/
1. ✅ evacuation_abm.py
2. ✅ abm_accelerated.py
3. ✅ osm_router.py

### KEEP in simulation/core/ (Shared):
1. ✅ spatial_utils.py
2. ✅ cache.py

### NEW FILES TO CREATE:
1. ✅ simulation/swe/controller.py (SWE endpoints/router)
2. ✅ simulation/abm/controller.py (ABM endpoints/router)
3. ✅ simulation/__init__.py
4. ✅ simulation/core/__init__.py
5. ✅ simulation/swe/__init__.py
6. ✅ simulation/abm/__init__.py

---

## API Endpoint Changes

### OLD (Current)
```
POST /api/simulate           → SWE simulation
POST /api/abm/simulate       → ABM simulation
GET /api/depth              → Bathymetry
GET /api/health             → Health
```

### NEW (Proposed)
```
POST /api/swe/simulate       → SWE simulation
POST /api/swe/depth          → Bathymetry (moved to SWE)
GET /api/swe/health          → SWE health

POST /api/abm/simulate       → ABM simulation
GET /api/abm/health          → ABM health

GET /health                  → Main server health
```

---

## Import Changes Required

### In simulation/swe/__init__.py:
```python
from .swe_solver import TsunamiSWESolver
from .fault_data import FAULT_PUBLIC_LABELS, JAVA_FAULTS, JAVA_MEGATHRUST
# etc
```

### In simulation/abm/__init__.py:
```python
from .evacuation_abm import EvacuationABMSolver
from .osm_router import OSMRouter
# etc
```

### In server.py:
```python
from simulation.swe.controller import swe_router
from simulation.abm.controller import abm_router
from simulation.core.spatial_utils import validate_coordinates
```

---

## Benefits of This Restructuring

✅ **Clarity**: Easy to find which code belongs to which algorithm
✅ **Isolation**: Team SWE focuses on simulation/swe/, Team ABM on simulation/abm/
✅ **Maintainability**: Controllers handle their own routes (not mixed in server.py)
✅ **Scalability**: Easy to add new algorithms (just create simulation/xxx/)
✅ **Testing**: Each algorithm can have isolated tests
✅ **Server Simplicity**: server.py becomes <300 lines (was 1000+)

---

## Questions for You (Cross-Check)

1. **Is this structure clear?** Yes / No / Need changes
2. **Should we move bathymetry endpoints to SWE?** (since it's SWE-specific)
3. **Should health check be per-algorithm or global?** (Recommended: both)
4. **OK to create controllers.py for each?** (New files - yes/no)
5. **Anything else you want moved/reorganized?**

---

## Execution Plan (if approved)

1. ✅ Create new folder structure
2. ✅ Move files (copy then verify, then delete old)
3. ✅ Create __init__.py files with proper imports
4. ✅ Create controller.py files (SWE & ABM endpoints)
5. ✅ Rewrite server.py (router orchestration only)
6. ✅ Update imports in all files
7. ✅ Test all endpoints with pytest/curl
8. ✅ Delete old simulation/core files (except shared ones)
9. ✅ Verify no broken imports

---

## Estimated Impact

| Item | Effort | Risk |
|------|--------|------|
| Reorganize folders | Low | Low |
| Move files | Very Low | Very Low |
| Create controllers | Medium | Medium |
| Update server.py | Medium | Low |
| Update imports | Low | Very Low |
| Test | Medium | High |
| **Total** | **Medium** | **Low-Medium** |

---

## READY TO EXECUTE?

Make sure you confirm the questions above before proceeding!
