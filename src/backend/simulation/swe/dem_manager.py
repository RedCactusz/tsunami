"""
============================================================================
DEM MANAGER - Read elevation from DEMNAS/GEBCO raster files
============================================================================
Manages elevation queries from raster files using rasterio.

Author: Mini Project Komputasi Geospasial S2 Geomatika UGM
============================================================================
"""

import logging
import os
from typing import Tuple, Optional, List
import numpy as np

logger = logging.getLogger(__name__)

# Optional: rasterio for raster I/O
try:
    import rasterio
    from rasterio.transform import rowcol
    from rasterio.warp import transform_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    logger.warning("rasterio not available - DEM queries will fail")


class DEMManager:
    """
    Manages elevation data from raster files (DEMNAS, GEBCO, etc).

    Usage:
        dem_manager = DEMManager("path/to/DEM_Bantul.tif")
        elevation, crs = dem_manager.query(lon, lat)
    """

    def __init__(self, raster_path: str):
        """
        Initialize DEM manager with raster file.

        Args:
            raster_path: Path to GeoTIFF or other raster format
        """
        self.raster_path = raster_path
        self.dataset = None
        self.crs = None
        self.bounds = None
        self.transform = None
        self.shape = None
        self.nodata = None

        if not RASTERIO_AVAILABLE:
            raise ImportError("rasterio is required for DEMManager")

        if not os.path.exists(raster_path):
            raise FileNotFoundError(f"DEM file not found: {raster_path}")

        self._open_dataset()

    def _open_dataset(self):
        """Open raster dataset and cache metadata."""
        try:
            self.dataset = rasterio.open(self.raster_path)
            self.crs = self.dataset.crs
            self.bounds = self.dataset.bounds  # (left, bottom, right, top)
            self.transform = self.dataset.transform
            self.shape = (self.dataset.height, self.dataset.width)
            self.nodata = self.dataset.nodata

            logger.info(f"[DEM] Loaded {self.raster_path}")
            logger.info(f"[DEM]   Bounds: {self.bounds}")
            logger.info(f"[DEM]   Shape: {self.shape}")
            logger.info(f"[DEM]   CRS: {self.crs}")
            logger.info(f"[DEM]   NoData: {self.nodata}")

        except Exception as e:
            logger.error(f"[DEM] Failed to open raster: {e}")
            raise

    def query(self, lon: float, lat: float) -> Tuple[Optional[float], Optional[str]]:
        """
        Query elevation at a single point.

        Args:
            lon: Longitude
            lat: Latitude

        Returns:
            (elevation_m, crs) tuple
            elevation_m: Elevation in meters (None if outside bounds or NoData)
            crs: Coordinate reference system string
        """
        if self.dataset is None:
            return None, None

        # Check if point is within bounds
        if not (self.bounds.left <= lon <= self.bounds.right and
                self.bounds.bottom <= lat <= self.bounds.top):
            return None, None

        try:
            # Convert lat/lon to row/col
            row, col = rowcol(self.transform, lon, lat)

            # Check if row/col is within dataset bounds
            if not (0 <= row < self.shape[0] and 0 <= col < self.shape[1]):
                return None, None

            # Read single pixel value
            window = ((row, row + 1), (col, col + 1))
            value = self.dataset.read(1, window=window)[0, 0]

            # Check for NoData
            if value == self.nodata or value < -900:  # Allow small negative for ocean
                return None, str(self.crs) if self.crs else None

            return float(value), str(self.crs) if self.crs else None

        except Exception as e:
            logger.warning(f"[DEM] Query failed at ({lon}, {lat}): {e}")
            return None, None

    def query_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        Query elevation (alias for query with lat/lon swapped).

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Elevation in meters or None if not found
        """
        elev, _ = self.query(lon, lat)
        return elev

    def query_grid_bulk(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """
        Query elevation for a grid of points (vectorized).

        Args:
            lats: Array of latitudes
            lons: Array of longitudes

        Returns:
            2D array of elevations (same shape as lats × lons)
            NoData values are set to -1000
        """
        if self.dataset is None:
            return np.full((len(lats), len(lons)), -1000, dtype=np.float32)

        try:
            # Create meshgrid for vectorized lookup
            lat_grid, lon_grid = np.meshgrid(lats, lons, indexing='ij')

            # Convert all points to row/col
            rows, cols = rowcol(self.transform, lon_grid.ravel(), lat_grid.ravel())

            # Clip to dataset bounds
            valid_mask = (
                (rows >= 0) & (rows < self.shape[0]) &
                (cols >= 0) & (cols < self.shape[1])
            )

            # Initialize result array with NoData
            elevations = np.full(lat_grid.shape, -1000, dtype=np.float32)

            # Read only valid pixels
            if np.any(valid_mask):
                valid_rows = rows[valid_mask]
                valid_cols = cols[valid_mask]

                # Use rasterio's efficient windowed reading
                # For very large grids, read in chunks
                window = ((valid_rows.min(), valid_rows.max() + 1),
                         (valid_cols.min(), valid_cols.max() + 1))

                data = self.dataset.read(1, window=window)

                # Map back to elevation grid
                window_row_offset = window[0][0]
                window_col_offset = window[1][0]

                local_rows = valid_rows - window_row_offset
                local_cols = valid_cols - window_col_offset

                # Extract values and check NoData
                values = data[local_rows, local_cols]
                nodata_mask = (values == self.nodata) | (values < -900)

                # Set NoData to -1000
                values[nodata_mask] = -1000

                # Fill elevation grid
                elev_flat = elevations.ravel()
                elev_flat[valid_mask] = values

            return elevations

        except Exception as e:
            logger.error(f"[DEM] Bulk query failed: {e}")
            return np.full((len(lats), len(lons)), -1000, dtype=np.float32)

    def get_profile(self) -> dict:
        """Get raster profile metadata."""
        if self.dataset is None:
            return {}
        return {
            'crs': str(self.crs) if self.crs else None,
            'bounds': self.bounds,
            'shape': self.shape,
            'nodata': self.nodata,
            'transform': self.transform,
        }

    def close(self):
        """Close the raster dataset."""
        if self.dataset is not None:
            self.dataset.close()
            self.dataset = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = ['DEMManager']
