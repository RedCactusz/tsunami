"""ABM (Agent-Based Model) Evacuation Simulation Module."""

from .evacuation_abm import EvacuationABMSolver
from .osm_router import OSMEvacuationRouter as OSMRouter

try:
    from .abm_accelerated import get_abm_gpu_status
except ImportError:
    def get_abm_gpu_status():
        return {"available": False}

__all__ = [
    'EvacuationABMSolver',
    'OSMRouter',
    'get_abm_gpu_status'
]
