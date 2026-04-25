import math
import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def wrapper(func): return func
        return wrapper if not args else args[0]
    prange = range

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

def select_strategy(dx_m: float) -> str:
    """Pilih teknik otomatis berdasarkan resolusi, prioritas GPU."""
    if CUPY_AVAILABLE:
        return 'cupy'
    elif NUMBA_AVAILABLE:
        return 'numba'
    return 'numpy'

def warmup_numba():
    """Pre-compile JIT — panggil saat server startup."""
    if not NUMBA_AVAILABLE:
        return
    dummy = np.zeros((10,10), dtype=np.float32)
    H_d   = np.ones((10,10),  dtype=np.float32) * 100.0
    m_d   = np.ones((10,10),  dtype=np.float32) * 0.025
    swe_step_numba(dummy, dummy.copy(), dummy.copy(), H_d, m_d, 1.0, 185.0, 185.0, 9.81, True)

def swe_step_numpy(eta: np.ndarray, u: np.ndarray, v: np.ndarray,
                   H: np.ndarray, manning: np.ndarray,
                   dt: float, dx: float, dy: float, g: float,
                   use_friction: bool):
    eta_new = eta.copy()
    u_new = u.copy()
    v_new = v.copy()
    
    H_u = 0.5 * (H[:, :-1] + H[:, 1:])
    mask_u = H_u > 0.01
    deta_dx = (eta[:, 1:] - eta[:, :-1]) / dx
    
    if use_friction:
        n_u = 0.5 * (manning[:, :-1] + manning[:, 1:])
        speed = np.sqrt(u[:, :-1]**2 + v[:, :-1]**2)
        fric = g * n_u**2 * speed / (H_u**(4.0/3.0) + 1e-6)
        u_new[:, 1:][mask_u] = (u[:, 1:][mask_u] - g * dt * deta_dx[mask_u]) / (1.0 + dt * fric[mask_u])
    else:
        u_new[:, 1:][mask_u] = u[:, 1:][mask_u] - g * dt * deta_dx[mask_u]

    H_v = 0.5 * (H[:-1, :] + H[1:, :])
    mask_v = H_v > 0.01
    deta_dy = (eta[1:, :] - eta[:-1, :]) / dy
    
    if use_friction:
        n_v = 0.5 * (manning[:-1, :] + manning[1:, :])
        speed = np.sqrt(u[:-1, :]**2 + v[:-1, :]**2)
        fric = g * n_v**2 * speed / (H_v**(4.0/3.0) + 1e-6)
        v_new[1:, :][mask_v] = (v[1:, :][mask_v] - g * dt * deta_dy[mask_v]) / (1.0 + dt * fric[mask_v])
    else:
        v_new[1:, :][mask_v] = v[1:, :][mask_v] - g * dt * deta_dy[mask_v]

    H_e = 0.5 * (H[1:-1, 1:-1] + H[1:-1, 2:])
    H_w = 0.5 * (H[1:-1, 1:-1] + H[1:-1, :-2])
    H_n = 0.5 * (H[1:-1, 1:-1] + H[2:, 1:-1])
    H_s = 0.5 * (H[1:-1, 1:-1] + H[:-2, 1:-1])
    
    flux_x = (H_e * u_new[1:-1, 2:] - H_w * u_new[1:-1, 1:-1]) / dx
    flux_y = (H_n * v_new[2:, 1:-1] - H_s * v_new[1:-1, 1:-1]) / dy
    
    eta_new[1:-1, 1:-1] = eta[1:-1, 1:-1] - dt * (flux_x + flux_y)
    
    return eta_new, u_new, v_new

@njit(cache=True, parallel=True)
def swe_step_numba(eta: np.ndarray, u: np.ndarray, v: np.ndarray,
                   H: np.ndarray, manning: np.ndarray,
                   dt: float, dx: float, dy: float, g: float,
                   use_friction: bool):
    ny, nx = eta.shape
    eta_new = eta.copy()
    u_new = u.copy()
    v_new = v.copy()
    
    for i in prange(1, ny - 1):
        for j in range(1, nx - 1):
            H_u = 0.5 * (H[i, j] + H[i, j - 1])
            if H_u > 0.01:
                deta_dx = (eta[i, j] - eta[i, j - 1]) / dx
                u_new[i, j] = u[i, j] - g * dt * deta_dx
                if use_friction:
                    n = 0.5 * (manning[i, j] + manning[i, j - 1])
                    speed = math.sqrt(u[i, j] ** 2 + v[i, j] ** 2)
                    fric = g * n ** 2 * speed / (H_u ** (4.0 / 3.0) + 1e-6)
                    u_new[i, j] /= (1.0 + dt * fric)
            
            H_v = 0.5 * (H[i, j] + H[i - 1, j])
            if H_v > 0.01:
                deta_dy = (eta[i, j] - eta[i - 1, j]) / dy
                v_new[i, j] = v[i, j] - g * dt * deta_dy
                if use_friction:
                    n = 0.5 * (manning[i, j] + manning[i - 1, j])
                    speed = math.sqrt(u[i, j] ** 2 + v[i, j] ** 2)
                    fric = g * n ** 2 * speed / (H_v ** (4.0 / 3.0) + 1e-6)
                    v_new[i, j] /= (1.0 + dt * fric)
    
    for i in prange(1, ny - 1):
        for j in range(1, nx - 1):
            H_e = 0.5 * (H[i, j] + H[i, j + 1])
            H_w = 0.5 * (H[i, j] + H[i, j - 1])
            H_n = 0.5 * (H[i, j] + H[i + 1, j])
            H_s = 0.5 * (H[i, j] + H[i - 1, j])
            flux_x = (H_e * u_new[i, j + 1] - H_w * u_new[i, j]) / dx
            flux_y = (H_n * v_new[i + 1, j] - H_s * v_new[i, j]) / dy
            eta_new[i, j] = eta[i, j] - dt * (flux_x + flux_y)
    
    return eta_new, u_new, v_new

def swe_step_cupy(eta, u, v, H, manning, dt, dx, dy, g, use_friction):
    if not CUPY_AVAILABLE:
        raise ImportError("CuPy is not available.")
    
    eta_new = eta.copy()
    u_new = u.copy()
    v_new = v.copy()
    
    H_u = 0.5 * (H[:, :-1] + H[:, 1:])
    mask_u = H_u > 0.01
    deta_dx = (eta[:, 1:] - eta[:, :-1]) / dx
    
    if use_friction:
        n_u = 0.5 * (manning[:, :-1] + manning[:, 1:])
        speed = cp.sqrt(u[:, :-1]**2 + v[:, :-1]**2)
        fric = g * n_u**2 * speed / (H_u**(4.0/3.0) + 1e-6)
        u_new[:, 1:][mask_u] = (u[:, 1:][mask_u] - g * dt * deta_dx[mask_u]) / (1.0 + dt * fric[mask_u])
    else:
        u_new[:, 1:][mask_u] = u[:, 1:][mask_u] - g * dt * deta_dx[mask_u]

    H_v = 0.5 * (H[:-1, :] + H[1:, :])
    mask_v = H_v > 0.01
    deta_dy = (eta[1:, :] - eta[:-1, :]) / dy
    
    if use_friction:
        n_v = 0.5 * (manning[:-1, :] + manning[1:, :])
        speed = cp.sqrt(u[:-1, :]**2 + v[:-1, :]**2)
        fric = g * n_v**2 * speed / (H_v**(4.0/3.0) + 1e-6)
        v_new[1:, :][mask_v] = (v[1:, :][mask_v] - g * dt * deta_dy[mask_v]) / (1.0 + dt * fric[mask_v])
    else:
        v_new[1:, :][mask_v] = v[1:, :][mask_v] - g * dt * deta_dy[mask_v]

    H_e = 0.5 * (H[1:-1, 1:-1] + H[1:-1, 2:])
    H_w = 0.5 * (H[1:-1, 1:-1] + H[1:-1, :-2])
    H_n = 0.5 * (H[1:-1, 1:-1] + H[2:, 1:-1])
    H_s = 0.5 * (H[1:-1, 1:-1] + H[:-2, 1:-1])
    
    flux_x = (H_e * u_new[1:-1, 2:] - H_w * u_new[1:-1, 1:-1]) / dx
    flux_y = (H_n * v_new[2:, 1:-1] - H_s * v_new[1:-1, 1:-1]) / dy
    
    eta_new[1:-1, 1:-1] = eta[1:-1, 1:-1] - dt * (flux_x + flux_y)
    
    return eta_new, u_new, v_new

class SpatialTilerDEMNAS:
    """Bagi domain DEMNAS (666M sel) -> tile 5x5km -> proses di GPU"""
    pass

class BathyCache:
    """Cache raster ke RAM — baca file SEKALI saja"""
    _instance = None
    _cache = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_or_load(self, key, lat_arr, lon_arr, manager):
        # Incorporate domain extent into cache key to avoid stale data
        cache_key = f"{key}_{len(lat_arr)}_{len(lon_arr)}_{lat_arr[0]:.4f}_{lon_arr[0]:.4f}"
        if cache_key in self._cache:
            return self._cache[cache_key]          # HIT: langsung return
        grid = manager.query_grid_bulk(lat_arr, lon_arr)
        self._cache[cache_key] = grid.astype(np.float32)
        return grid
