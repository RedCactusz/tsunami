"""SWE (Shallow Water Equations) Tsunami Simulation Module."""

from .swe_solver import (
    TsunamiSWESolver, FaultParameters, SimulationConfig,
    wells_coppersmith_scaling, blaser_scaling
)
from .fault_data import (
    FAULT_PUBLIC_LABELS, JAVA_FAULTS, JAVA_MEGATHRUST
)
from .inundation_connector import (
    InundationConnector, InundationData,
    inundation_to_abm_dict, affected_villages_from_inundation,
    classify_danger_zone
)

try:
    from .swe_accelerated import warmup_numba
except ImportError:
    def warmup_numba():
        pass

__all__ = [
    'TsunamiSWESolver', 'FaultParameters', 'SimulationConfig',
    'wells_coppersmith_scaling', 'blaser_scaling',
    'FAULT_PUBLIC_LABELS', 'JAVA_FAULTS', 'JAVA_MEGATHRUST',
    'InundationConnector', 'InundationData',
    'inundation_to_abm_dict', 'affected_villages_from_inundation',
    'classify_danger_zone', 'warmup_numba'
]
