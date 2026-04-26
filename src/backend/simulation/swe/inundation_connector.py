"""
============================================================================
INUNDATION CONNECTOR — Jembatan SWE Results → Evacuation ABM
============================================================================
Modul ini mengkonversi hasil SWE tsunami simulation menjadi format
yang dibutuhkan EvacuationABMSolver:

  SWEResults  →  InundationData  →  EvacuationABMSolver.set_swe_results()

Data yang dihasilkan:
  - flood_polygons: List poligon area tergenang (untuk ABM router)
  - per_desa_flood: Dict<nama_desa, { wave_height_m, inundated, danger_zone }>
  - inundation_grid: Grid 2D status genangan per sel (untuk visualisasi)
  - coastline_mask: Mask batas darat/laut berdasarkan DEMNAS + garis pantai

Metodologi:
  - Bathtub model: sel darat dengan elevasi < runup dianggap tergenang
  - Batas darat/laut: depth >= 0 (dari grid bathymetry DEMNAS/BATNAS)
  - Village impact: nearest-neighbor dari grid ke centroid desa
============================================================================
"""

import logging
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# ── Opsional: Shapely untuk polygon operations ──────────────────────────────
try:
    from shapely.geometry import shape, Point, MultiPolygon, Polygon, mapping
    from shapely.ops import unary_union
    import shapely
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False

# ── Opsional: rasterio untuk baca DEMNAS langsung ───────────────────────────
try:
    import rasterio
    from rasterio.features import shapes as rasterio_shapes
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

# ── Opsional: scipy untuk interpolasi dan filtering ──────────────────────────
try:
    from scipy.ndimage import distance_transform_edt, uniform_filter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class VillageFloodInfo:
    """Info genangan per desa — diteruskan ke ABM."""
    name: str
    lat: float
    lon: float
    wave_height_m: float
    danger_zone: str          # Ekstrem / Sangat Tinggi / Tinggi / Sedang / Rendah / Aman
    inundated: bool
    dist_coast_km: float = 0.0
    population: int = 0
    terdampak: int = 0


@dataclass
class InundationData:
    """
    Output dari InundationConnector — siap dipakai EvacuationABMSolver.
    """
    # Untuk ABM router flood blocking
    flood_polygons: List[List[Tuple[float, float]]]   # List polygon [(lon, lat), ...]

    # Untuk village-level assessment
    per_desa_flood: Dict[str, VillageFloodInfo]

    # Grid status (untuk export ke frontend)
    inundation_grid: Optional[np.ndarray]             # 2D bool: True = tergenang
    lats: List[float]
    lons: List[float]
    shape: Tuple[int, int]

    # Statistik ringkasan
    max_wave_height_m: float
    max_runup_m: float
    inundation_area_km2: float
    n_villages_affected: int

    # GeoJSON siap kirim ke frontend
    inundation_geojson: Dict


# ============================================================================
# DANGER ZONE CLASSIFIER
# ============================================================================

def classify_danger_zone(wave_height_m: float) -> str:
    """Klasifikasi zona bahaya berdasarkan tinggi gelombang."""
    if wave_height_m >= 6.0:
        return "Ekstrem"
    elif wave_height_m >= 3.0:
        return "Sangat Tinggi"
    elif wave_height_m >= 1.5:
        return "Tinggi"
    elif wave_height_m >= 0.5:
        return "Sedang"
    elif wave_height_m >= 0.1:
        return "Rendah"
    return "Aman"


DANGER_COLORS = {
    "Ekstrem":      "#7B0000",
    "Sangat Tinggi":"#f87171",
    "Tinggi":       "#FF4500",
    "Sedang":       "#FF8C00",
    "Rendah":       "#FFD700",
    "Aman":         "#4ade80",
}


# ============================================================================
# INUNDATION CONNECTOR
# ============================================================================

class InundationConnector:
    """
    Konversi SWEResults → InundationData untuk EvacuationABMSolver.

    Usage:
        connector = InundationConnector(
            desa_shp_path="path/to/Administrasi_Desa.shp",
            dem_manager=dem_manager,
            study_area_objectids=[3830, 3831, 3832, 3893, 3912, 3922, 3952, 3977, 3978, 3981]
        )
        inundation = connector.process(swe_results, bathy_grid)
        abm_solver.set_swe_results(inundation.to_abm_dict())
    """

    # Desa pesisir Bantul yang relevan (fallback jika shapefile tidak ada)
    BANTUL_COASTAL_VILLAGES = [
        {"name": "Gadingsari",  "lat": -7.998, "lon": 110.267, "population": 4250},
        {"name": "Srigading",   "lat": -7.985, "lon": 110.285, "population": 3820},
        {"name": "Tirtosari",   "lat": -7.975, "lon": 110.255, "population": 3100},
        {"name": "Poncosari",   "lat": -7.963, "lon": 110.298, "population": 5640},
        {"name": "Trimurti",    "lat": -7.952, "lon": 110.244, "population": 2900},
        {"name": "Banaran",     "lat": -7.941, "lon": 110.311, "population": 4100},
        {"name": "Palbapang",   "lat": -7.930, "lon": 110.280, "population": 3600},
        {"name": "Sabdodadi",   "lat": -7.920, "lon": 110.262, "population": 2800},
        {"name": "Srandakan",   "lat": -7.935, "lon": 110.253, "population": 3200},
        {"name": "Srihardono",  "lat": -7.912, "lon": 110.278, "population": 3500},
    ]

    # Populasi statis per desa Bantul (BPS 2023) — fallback jika shapefile tidak punya
    BANTUL_POP_FALLBACK = {
        'Parangtritis': 7100, 'Tirtosari': 3100, 'Tirtohargo': 2800,
        'Srigading': 3820, 'Gadingsari': 4250, 'Poncosari': 5640,
        'Trimurti': 2900, 'Gadingharjo': 3200, 'Murtigading': 4100,
        'Tirtomulyo': 5200, 'Donotirto': 4800, 'Seloharjo': 3500,
        'Panjangrejo': 4600, 'Sidomulyo': 5100, 'Mulyodadi': 4900,
        'Caturharjo': 3800, 'Srihardono': 3500, 'Sumberagung': 4200,
        'Selopamioro': 3700, 'Imogiri': 5800, 'Bantul': 6200,
    }

    # Target OBJECTIDs untuk study area (Bantul coastal villages)
    STUDY_AREA_OBJECTIDS = [3830, 3831, 3832, 3893, 3912, 3922, 3952, 3977, 3978, 3981]

    def __init__(self, desa_shp_path: Optional[str] = None, dem_manager=None,
                 study_area_objectids: Optional[List[int]] = None):
        self.desa_shp_path = desa_shp_path
        self.dem_manager = dem_manager
        self._desa_cache: Optional[List[Dict]] = None
        # Gunakan OBJECTIDs yang diberikan, atau default ke study area Bantul
        self.study_area_objectids = (study_area_objectids if study_area_objectids is not None
                                     else self.STUDY_AREA_OBJECTIDS)

    # ── Public API ───────────────────────────────────────────────────────────

    def process(self,
                swe_results,            # SWEResults dataclass dari swe_solver
                bathy_grid: Dict,       # {'lons', 'lats', 'depth', 'shape'}
                wave_threshold_m: float = 0.1,
                magnitude: float = 0.0) -> InundationData:
        """
        Proses hasil SWE menjadi InundationData lengkap.

        Args:
            swe_results : SWEResults dari TsunamiSWESolver.simulate()
            bathy_grid  : Grid bathymetry (termasuk depth > 0 = daratan)
            wave_threshold_m: Ambang batas tinggi gelombang dianggap tergenang
            magnitude   : Magnitude gempa (Mw) — digunakan untuk runup empiris
        """
        lons = np.array(bathy_grid['lons'])
        lats = np.array(bathy_grid['lats'])
        depth = bathy_grid['depth']              # negatif = laut, positif = darat
        max_eta = swe_results.max_wave_height    # 2D array

        ny, nx = max_eta.shape

        # 1. Buat inundation mask (sel DARAT yang tergenang)
        land_mask = depth >= 0
        inundation_mask = land_mask & (max_eta >= wave_threshold_m)

        logger.info(f"[Connector] Inundated land cells: {np.sum(inundation_mask)} / {np.sum(land_mask)}")

        # 2. Build flood polygons untuk ABM
        flood_polygons = self._extract_flood_polygons(inundation_mask, lats, lons)

        # 3. Assess desa — juga hitung runup aktual (sekarang magnitude-aware)
        desa_list = self._load_desa()
        per_desa, actual_runup_m = self._assess_villages(max_eta, lats, lons, depth, desa_list, magnitude=magnitude)

        # 4. Area inundasi (km²)
        lat_mid = float(np.mean(lats))
        dlat = float(lats[1] - lats[0]) if len(lats) > 1 else 0.002
        dlon = float(lons[1] - lons[0]) if len(lons) > 1 else 0.002
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_mid))
        cell_area_km2 = (dlat * m_per_deg_lat * dlon * m_per_deg_lon) / 1e6
        inundation_area_km2 = float(np.sum(inundation_mask)) * cell_area_km2

        # 5. GeoJSON untuk frontend — gunakan actual runup
        inundation_geojson = self._build_geojson(per_desa, flood_polygons=flood_polygons, runup_m=actual_runup_m)

        n_affected = sum(1 for v in per_desa.values() if v.inundated)

        return InundationData(
            flood_polygons=flood_polygons,
            per_desa_flood=per_desa,
            inundation_grid=inundation_mask,
            lats=lats.tolist(),
            lons=lons.tolist(),
            shape=(ny, nx),
            max_wave_height_m=float(np.max(max_eta)),
            max_runup_m=swe_results.max_runup_m,
            inundation_area_km2=inundation_area_km2,
            n_villages_affected=n_affected,
            inundation_geojson=inundation_geojson,
        )

    def process_from_dict(self, swe_dict: Dict, wave_threshold_m: float = 0.1) -> Optional['InundationData']:
        """
        Proses dari dict (format cache server) — dipakai saat ABM dipanggil
        SETELAH simulasi selesai dan data sudah tersimpan di app_state.
        """
        if not swe_dict:
            return None

        max_wave = swe_dict.get('max_wave_height')
        grid_info = swe_dict.get('grid_info', {})
        if max_wave is None or not grid_info:
            logger.warning("[Connector] process_from_dict: max_wave_height atau grid_info kosong")
            return None

        max_eta = np.array(max_wave, dtype=np.float32)
        lats_raw = grid_info.get('lats', [])
        lons_raw = grid_info.get('lons', [])

        if not lats_raw or not lons_raw:
            logger.warning("[Connector] grid_info tidak memiliki lats/lons")
            return None

        lats = np.array(lats_raw)
        lons = np.array(lons_raw)

        # Buat depth proxy dari max_eta (negatif = laut, positif = darat)
        # Gunakan dem_manager jika tersedia untuk depth asli
        depth = self._build_depth_proxy(max_eta, lats, lons)

        ny, nx = max_eta.shape
        land_mask = depth >= 0
        inundation_mask = land_mask & (max_eta >= wave_threshold_m)

        flood_polygons = self._extract_flood_polygons(inundation_mask, lats, lons)
        desa_list = self._load_desa()
        per_desa, actual_runup_m = self._assess_villages(max_eta, lats, lons, depth, desa_list)

        lat_mid = float(np.mean(lats))
        dlat = float(abs(lats[1] - lats[0])) if len(lats) > 1 else 0.002
        dlon = float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.002
        cell_area_km2 = (dlat * 111320 * dlon * 111320 * math.cos(math.radians(lat_mid))) / 1e6
        inundation_area_km2 = float(np.sum(inundation_mask)) * cell_area_km2

        return InundationData(
            flood_polygons=flood_polygons,
            per_desa_flood=per_desa,
            inundation_grid=inundation_mask,
            lats=lats.tolist(),
            lons=lons.tolist(),
            shape=(ny, nx),
            max_wave_height_m=float(np.max(max_eta)),
            max_runup_m=swe_dict.get('max_runup_m', 0.0),
            inundation_area_km2=inundation_area_km2,
            n_villages_affected=sum(1 for v in per_desa.values() if v.inundated),
            inundation_geojson=self._build_geojson(per_desa, flood_polygons=flood_polygons, runup_m=actual_runup_m),
        )

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_depth_proxy(self, max_eta: np.ndarray,
                           lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """
        Buat depth proxy jika tidak ada bathy_grid asli.
        Gunakan DEM manager jika tersedia, else heuristik dari max_eta.
        """
        ny, nx = max_eta.shape
        depth = np.zeros((ny, nx), dtype=np.float32)

        if self.dem_manager is not None:
            # Query DEM per sel (bulk jika tersedia)
            try:
                if hasattr(self.dem_manager, 'query_grid_bulk'):
                    grid = self.dem_manager.query_grid_bulk(lats, lons)
                    # DEM positif = darat, negatif/nodata = laut
                    depth = np.where(grid > -900, grid.astype(np.float32), -100.0)
                    logger.info("[Connector] Depth proxy dari DEM manager (bulk)")
                    return depth
            except Exception as e:
                logger.warning(f"[Connector] DEM bulk query gagal: {e}")

        # Fallback: heuristik — area dengan max_eta tinggi cenderung laut
        # Batas kasar: zona -7.8°S ke atas = darat Bantul
        lat_grid, _ = np.meshgrid(lats, lons, indexing='ij')
        # Bantul pesisir: lat > -8.05 = kemungkinan darat
        depth = np.where(lat_grid > -8.05, 5.0, -100.0).astype(np.float32)
        logger.info("[Connector] Depth proxy menggunakan heuristik lat boundary")
        return depth

    def _extract_flood_polygons(self, inundation_mask: np.ndarray,
                                lats: np.ndarray, lons: np.ndarray
                                ) -> List[List[Tuple[float, float]]]:
        """
        Konversi inundation_mask grid → list poligon [(lon, lat), ...].
        Digunakan ABM router untuk memblokir edge yang tergenang.
        """
        polygons = []

        if SHAPELY_AVAILABLE and RASTERIO_AVAILABLE and np.any(inundation_mask):
            try:
                from rasterio.transform import from_bounds
                ny, nx = inundation_mask.shape

                if len(lats) >= 2 and len(lons) >= 2:
                    lat_min, lat_max = float(lats.min()), float(lats.max())
                    lon_min, lon_max = float(lons.min()), float(lons.max())
                else:
                    return polygons

                transform = from_bounds(lon_min, lat_min, lon_max, lat_max, nx, ny)
                mask_u8 = inundation_mask.astype(np.uint8)

                geoms = []
                for geom, val in rasterio_shapes(mask_u8, transform=transform):
                    if val == 1:
                        geoms.append(shape(geom))

                if geoms:
                    merged = unary_union(geoms)
                    if merged.geom_type == 'Polygon':
                        polygons.append(list(merged.exterior.coords))
                    elif merged.geom_type == 'MultiPolygon':
                        for p in merged.geoms:
                            polygons.append(list(p.exterior.coords))

                logger.info(f"[Connector] Extracted {len(polygons)} flood polygons via rasterio+shapely")
                return polygons
            except Exception as e:
                logger.warning(f"[Connector] Shapely polygon extraction gagal: {e}")

        # Fallback: bounding box sel-sel tergenang per baris
        if not np.any(inundation_mask):
            return polygons

        ny, nx = inundation_mask.shape
        dlat = float(abs(lats[1] - lats[0])) if len(lats) > 1 else 0.002
        dlon = float(abs(lons[1] - lons[0])) if len(lons) > 1 else 0.002

        # Sample setiap 5 sel untuk efisiensi
        for j in range(0, ny, 5):
            for i in range(0, nx, 5):
                if not inundation_mask[j, i]:
                    continue
                lat0 = float(lats[j])
                lon0 = float(lons[i])
                poly = [
                    (lon0, lat0), (lon0 + dlon * 5, lat0),
                    (lon0 + dlon * 5, lat0 + dlat * 5),
                    (lon0, lat0 + dlat * 5), (lon0, lat0)
                ]
                polygons.append(poly)

        logger.info(f"[Connector] Fallback: {len(polygons)} flood bboxes")
        return polygons

    def _load_desa(self) -> List[Dict]:
        """Load data desa dari shapefile atau fallback statis Bantul.
        Menyimpan polygon geometry untuk visualisasi inundasi per-desa.

        Filter hanya desa dalam study area berdasarkan OBJECTID.
        """
        if self._desa_cache is not None:
            return self._desa_cache

        if self.desa_shp_path:
            try:
                import geopandas as gpd
                gdf = gpd.read_file(self.desa_shp_path)
                gdf = gdf.to_crs(epsg=4326)

                # Filter hanya study area villages berdasarkan OBJECTID
                if 'OBJECTID' in gdf.columns and self.study_area_objectids:
                    gdf_filtered = gdf[gdf['OBJECTID'].isin(self.study_area_objectids)]
                    logger.info(f"[Connector] Filtered to {len(gdf_filtered)} villages "
                               f"from {len(gdf)} total (OBJECTIDs: {self.study_area_objectids})")
                    gdf = gdf_filtered
                else:
                    logger.warning(f"[Connector] OBJECTID column not found or no filter specified, "
                                 f"loading all {len(gdf)} villages")

                desa_list = []
                for _, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None:
                        continue
                    centroid = geom.centroid
                    name = (row.get('NAMOBJ') or row.get('DESA') or
                            row.get('NAMA') or row.get('name') or 'Desa')
                    pop = (row.get('Penduduk') or row.get('JIWA') or
                           row.get('POPULATION') or 0)
                    try:
                        pop = int(pop)
                    except Exception:
                        pop = 0

                    # Fallback ke tabel populasi statis jika 0
                    if pop == 0:
                        pop = self.BANTUL_POP_FALLBACK.get(str(name), 0)

                    # Simpan polygon geometry untuk GeoJSON inundasi
                    geom_dict = None
                    if SHAPELY_AVAILABLE:
                        try:
                            geom_dict = mapping(geom)
                        except Exception:
                            pass

                    desa_list.append({
                        'name': str(name),
                        'lat': centroid.y,
                        'lon': centroid.x,
                        'population': pop,
                        'geometry': geom_dict,  # Polygon/MultiPolygon GeoJSON dict
                    })

                if desa_list:
                    logger.info(f"[Connector] Loaded {len(desa_list)} desa dari shapefile (dengan polygon geometry)")
                    self._desa_cache = desa_list
                    return desa_list
            except Exception as e:
                logger.warning(f"[Connector] Gagal load desa shapefile: {e}")

        # Fallback statis Bantul pesisir
        self._desa_cache = self.BANTUL_COASTAL_VILLAGES
        logger.info("[Connector] Menggunakan desa Bantul statis (fallback)")
        return self._desa_cache

    def _assess_villages(self, max_eta: np.ndarray,
                          lats: np.ndarray, lons: np.ndarray,
                          depth: np.ndarray,
                          desa_list: List[Dict],
                          magnitude: float = 0.0) -> Tuple[Dict[str, VillageFloodInfo], float]:
        """
        Nilai dampak genangan per desa — MAGNITUDE-AWARE.

        Metodologi:
        1. Hitung runup menggunakan Abe (1979) empiris + SWE h_nearshore cross-check
        2. Skala atenuasi Manning berdasarkan magnitude
        3. Kurva kontinu untuk estimasi populasi terdampak

        Returns:
            Tuple of (per_desa_flood dict, actual_runup_m float)
        """
        result: Dict[str, VillageFloodInfo] = {}

        if max_eta is None or max_eta.size == 0:
            return result, 0.0

        # ── 1. Hitung h_nearshore dari SWE grid ──
        shoreline_mask = (depth >= -10) & (depth <= 2)
        if np.any(shoreline_mask):
            shore_eta = max_eta[shoreline_mask]
            shore_positive = shore_eta[shore_eta > 0.1]
            if shore_positive.size > 0:
                h_nearshore = float(np.percentile(shore_positive, 95))
            else:
                h_nearshore = float(np.max(max_eta)) * 0.3
        else:
            h_nearshore = float(np.max(max_eta)) * 0.3

        # ── 2. Runup menggunakan DUA metode, ambil yang lebih realistis ──
        # Metode A: Abe (1979) empiris — langsung dari magnitude
        # R_abe = 10^(0.5*Mw - 3.3) untuk near-field
        mw = magnitude if magnitude > 0 else 8.0
        runup_abe = 10 ** (0.5 * mw - 3.3)

        # Metode B: Synolakis (1987) dari h_nearshore SWE
        try:
            from spatial_utils import synolakis_runup
            runup_synolakis = synolakis_runup(h_nearshore, beach_slope=0.04, d_ref=10.0)
        except Exception:
            runup_synolakis = h_nearshore * 2.5

        # Cross-check: gunakan rata-rata tertimbang (Abe 60%, Synolakis 40%)
        # Abe lebih stabil terhadap magnitude, Synolakis lebih sensitif terhadap topografi
        runup_m = runup_abe * 0.6 + min(runup_synolakis, runup_abe * 2.0) * 0.4

        # Safety cap berdasarkan magnitude (fisika realistis)
        # Mw 7.0 → max 8m, Mw 8.0 → max 18m, Mw 9.0 → max 35m, Mw 9.5 → max 50m
        max_runup_by_mw = 10 ** (0.5 * mw - 3.1)  # sedikit lebih tinggi dari Abe
        runup_m = min(runup_m, max_runup_by_mw)
        runup_m = max(runup_m, 0.5)  # minimum 0.5m

        logger.info(f"[Connector] Mw={mw:.1f}, h_nearshore={h_nearshore:.2f}m, "
                    f"R_abe={runup_abe:.2f}m, R_synolakis={runup_synolakis:.2f}m → "
                    f"runup_final={runup_m:.2f}m (cap={max_runup_by_mw:.1f}m)")

        # ── 3. Atenuasi Manning — SKALA dengan magnitude ──
        # Gempa lebih kecil → energi lebih cepat habis di darat
        # Mw 7.0: alpha=0.18/km (cepat decay), Mw 9.0: alpha=0.06/km (lambat decay)
        alpha_base = 0.35 - 0.03 * mw  # Mw7→0.14, Mw8→0.11, Mw9→0.08, Mw9.5→0.065
        alpha_eff = max(alpha_base, 0.05)  # minimum 0.05/km

        # ── 4. Penetrasi maksimum berdasarkan magnitude ──
        # Mw 7.0 → max 3km, Mw 8.0 → max 6km, Mw 9.0 → max 12km
        max_penetration_km = runup_m * 0.5  # Empiris: penetrasi ≈ 0.5 * runup (km)

        # ── 5. Referensi garis pantai ──
        COASTLINE_REF_LAT = -8.02

        lat_min, lat_max = float(lats.min()), float(lats.max())
        lon_min, lon_max = float(lons.min()), float(lons.max())

        for d in desa_list:
            vlat = d.get('lat', 0.0)
            vlon = d.get('lon', 0.0)
            name = d.get('name', 'Desa')
            pop  = d.get('population', 0)

            if not (lat_min - 0.1 <= vlat <= lat_max + 0.1 and
                    lon_min - 0.1 <= vlon <= lon_max + 0.1):
                continue

            coast_lat = COASTLINE_REF_LAT - (vlon - 110.3) * 0.08
            dist_coast_km = max(0.0, (vlat - coast_lat) * 111.32)

            # Batas penetrasi — desa di luar jangkauan pasti aman
            if dist_coast_km > max_penetration_km:
                result[name] = VillageFloodInfo(
                    name=name, lat=vlat, lon=vlon,
                    wave_height_m=0.0,
                    danger_zone="Aman",
                    inundated=False,
                    dist_coast_km=round(dist_coast_km, 2),
                    population=pop,
                    terdampak=0,
                )
                continue

            elev_m = None
            if self.dem_manager is not None:
                try:
                    dem_elev, _ = self.dem_manager.query(vlon, vlat)
                    if dem_elev is not None:
                        elev_m = float(dem_elev)
                except Exception:
                    pass

            if elev_m is None:
                if dist_coast_km < 3:
                    elev_m = dist_coast_km * 1.2
                elif dist_coast_km < 6:
                    elev_m = 3.6 + (dist_coast_km - 3) * 2.0
                else:
                    elev_m = 9.6 + (dist_coast_km - 6) * 3.5

            eff_runup = runup_m * math.exp(-alpha_eff * dist_coast_km)
            flood_depth = eff_runup - max(0.0, elev_m)

            if flood_depth < 0.1:
                result[name] = VillageFloodInfo(
                    name=name, lat=vlat, lon=vlon,
                    wave_height_m=0.0,
                    danger_zone="Aman",
                    inundated=False,
                    dist_coast_km=round(dist_coast_km, 2),
                    population=pop,
                    terdampak=0,
                )
                continue

            zone = classify_danger_zone(flood_depth)

            # ✅ Kurva KONTINU untuk populasi terdampak
            # f(d) = min(95, 10 + 85 * (1 - exp(-0.3 * d)))
            # d=0.5→21%, d=1→33%, d=3→56%, d=5→72%, d=10→90%, d=15→95%
            pct_terdampak = min(95.0, 10.0 + 85.0 * (1.0 - math.exp(-0.3 * flood_depth)))
            terdampak = int(pop * pct_terdampak / 100.0)

            result[name] = VillageFloodInfo(
                name=name, lat=vlat, lon=vlon,
                wave_height_m=round(flood_depth, 2),
                danger_zone=zone,
                inundated=True,
                dist_coast_km=round(dist_coast_km, 2),
                population=pop,
                terdampak=terdampak,
            )

        n_affected = sum(1 for v in result.values() if v.inundated)
        n_safe = sum(1 for v in result.values() if not v.inundated)
        logger.info(f"[Connector] Assessed {len(result)} villages: "
                    f"{n_affected} tergenang, {n_safe} aman (runup={runup_m:.1f}m)")
        return result, runup_m

    def _build_geojson(self, per_desa: Dict[str, VillageFloodInfo],
                        flood_polygons: Optional[List] = None,
                        runup_m: float = 0.0) -> Dict:
        """Build GeoJSON inundasi menggunakan BFS flood-fill pada grid DEM resolusi tinggi.

        Strategi (mengikuti BMKG reference):
          1. Bangun grid elevasi hi-res (~89m) dari DEMNAS/DEM
          2. Identifikasi sel pantai (land adjacent to ocean) → seed BFS
          3. BFS flood-fill dari pantai ke daratan dengan atenuasi Manning
          4. Setiap sel tergenang → Point GeoJSON feature dengan depth + risk color
          5. Mask admin boundary agar hanya area Kabupaten Bantul yang diproses

        Args:
          runup_m: Runup aktual dari _assess_villages (proporsional terhadap magnitude).
                   Ini yang menentukan SEBERAPA LUAS area inundasi.
        """
        from collections import deque

        # ✅ Gunakan runup yang diberikan — BUKAN hardcode
        if runup_m < 0.5:
            # Jika runup sangat kecil, tidak perlu BFS flood-fill
            logger.info(f"[Inundasi] Runup terlalu kecil ({runup_m:.2f}m), skip BFS flood-fill")
            return {"type": "FeatureCollection", "features": []}
        
        logger.info(f"[Inundasi] BFS flood-fill dengan runup={runup_m:.2f}m")

        # ── Admin mask (Kabupaten Bantul) ──
        admin_union = None
        admin_bbox = (110.05, -8.15, 110.60, -7.85)  # Fallback bbox
        if SHAPELY_AVAILABLE and self._desa_cache:
            try:
                admin_geoms = []
                for d in self._desa_cache:
                    g = d.get('geometry')
                    if g:
                        s = shape(g)
                        if s.is_valid and not s.is_empty:
                            admin_geoms.append(s)
                if admin_geoms:
                    admin_union = unary_union(admin_geoms)
                    if not admin_union.is_valid:
                        admin_union = admin_union.buffer(0)
                    admin_bbox = admin_union.bounds  # (minx, miny, maxx, maxy)
                    logger.info(f"[Inundasi] Admin mask: {len(admin_geoms)} desa, "
                               f"bbox=({admin_bbox[0]:.4f},{admin_bbox[1]:.4f},"
                               f"{admin_bbox[2]:.4f},{admin_bbox[3]:.4f})")
            except Exception as e:
                logger.warning(f"[Inundasi] Gagal buat admin union: {e}")

        prepared_mask = None
        if SHAPELY_AVAILABLE and admin_union is not None:
            try:
                from shapely.prepared import prep
                prepared_mask = prep(admin_union)
                logger.info(f"[Inundasi] ✅ Admin mask prepared successfully (type: {type(admin_union).__name__})")
            except Exception as e:
                logger.warning(f"[Inundasi] ❌ Failed to prepare admin mask: {e}")
        else:
            logger.warning(f"[Inundasi] ❌ Admin mask NOT created: SHAPELY_AVAILABLE={SHAPELY_AVAILABLE}, admin_union={'exists' if admin_union is not None else 'None'}")

        # ── Grid hi-res untuk flood-fill ──
        FILL_DX = 0.0008   # ~89m per sel (balance resolusi vs performa)
        FILL_DX_KM = FILL_DX * 111.0 * math.cos(math.radians(8.0))

        buf = 0.01  # ~1km buffer
        fill_lon_min = admin_bbox[0] - buf
        fill_lat_min = admin_bbox[1] - buf
        fill_lon_max = admin_bbox[2] + buf
        fill_lat_max = admin_bbox[3] + buf

        fill_lat_arr = np.arange(fill_lat_min, fill_lat_max, FILL_DX)
        fill_lon_arr = np.arange(fill_lon_min, fill_lon_max, FILL_DX)
        fill_ny = len(fill_lat_arr)
        fill_nx = len(fill_lon_arr)

        total_cells = fill_ny * fill_nx
        logger.info(f"[Inundasi] Grid hi-res: {fill_ny}×{fill_nx} = {total_cells:,} sel "
                    f"(dx={FILL_DX}°, ~{FILL_DX*111000:.0f}m)")

        # ── Step 1: Bangun grid elevasi dari DEM ──
        elev_grid = np.full((fill_ny, fill_nx), np.nan, dtype=np.float32)

        if self.dem_manager is not None:
            if hasattr(self.dem_manager, 'query_grid_bulk'):
                logger.info(f"[Inundasi] Batch-reading DEM untuk {total_cells:,} sel...")
                raw_grid = self.dem_manager.query_grid_bulk(fill_lat_arr, fill_lon_arr)
                # query_grid_bulk returns -1000 for missing data
                valid = (raw_grid > -900) & (raw_grid < 10000)
                elev_grid = np.where(valid, raw_grid.astype(np.float32), np.nan)
                dem_hits = int(np.sum(valid))
                logger.info(f"[Inundasi] DEM hits: {dem_hits}/{total_cells} "
                           f"({dem_hits*100//max(1,total_cells)}%)")
            elif hasattr(self.dem_manager, 'query_elevation'):
                # Fallback: individual queries (slow but works)
                logger.info(f"[Inundasi] Querying DEM individual (fallback)...")
                dem_hits = 0
                for j in range(0, fill_ny, 3):  # sample every 3 for speed
                    lat = float(fill_lat_arr[j])
                    for i in range(0, fill_nx, 3):
                        lon = float(fill_lon_arr[i])
                        elev = self.dem_manager.query_elevation(lat, lon)
                        if elev is not None:
                            elev_grid[j, i] = float(elev)
                            dem_hits += 1
                logger.info(f"[Inundasi] DEM hits (sampled): {dem_hits}")

        # ── FALLBACK ELEVATION (jika DEM tidak tersedia) ──
        # Gunakan model elevasi sederhana berdasarkan latitude & jarak dari pantai
        nan_count_before = int(np.isnan(elev_grid).sum())
        if nan_count_before == total_cells:
            logger.warning("[Inundasi] ⚠️  DEM tidak tersedia, menggunakan fallback elevation model")
            logger.warning("[Inundasi] ⚠️  Hasil mungkin tidak akurat untuk area non-pesisir!")

            # Buat simple elevation model:
            # - Lat < -8.02 = laut (negatif)
            # - Lat > -8.02 = darat (positif, meningkat ke utara)
            lat_grid, lon_grid = np.meshgrid(fill_lat_arr, fill_lon_arr, indexing='ij')

            # Referensi coastline (garis pantai Bantul)
            coast_lat_ref = -8.02

            # Elevasi dasar berdasarkan latitude dengan slope lebih curam
            # Di selatan coast: negatif (laut)
            # Di utara coast: positif (darat), semakin utara semakin tinggi
            # FIX: Gunakan slope 200m/derajat (lebih realistis) bukan 100m
            elev_from_lat = (lat_grid - coast_lat_ref) * 200.0  # 200m per 1 derajat lat

            # Tambahan topografi lokal dengan variasi lebih besar
            # Gunakan kombinasi sinus untuk bukit-bukit kecil
            elev_from_lon = np.sin((lon_grid - 110.3) * 15) * 5.0 + \
                           np.cos((lat_grid - coast_lat_ref) * 80) * 3.0  # ±5-8m variasi

            # Gabungkan
            elev_grid = elev_from_lat + elev_from_lon

            # Smoothing dengan simple average (jika scipy tersedia)
            if SCIPY_AVAILABLE:
                elev_grid = uniform_filter(elev_grid, size=3, mode='nearest')
                logger.info("[Inundasi] Applied scipy smoothing")
            else:
                # Manual smoothing tanpa scipy - skip untuk sekarang
                logger.warning("[Inundasi] scipy tidak tersedia, skipping elevation smoothing")

            logger.info(f"[Inundasi] Fallback elevation model: min={elev_grid.min():.1f}m, max={elev_grid.max():.1f}m")
            logger.warning("[Inundasi] ⚠️  DENGAN FALLBACK: inundasi mungkin overestimate di daratan tinggi!")

        # ── PERBAIKI: Set NaN cells di laut ke nilai negatif ──
        # Ini mencegah flood-fill menyebar ke laut
        nan_count = int(np.isnan(elev_grid).sum())
        if nan_count > 0:
            logger.info(f"[Inundasi] {nan_count} NaN cells ditemukan")

            # Gunakan latitude sebagai proxy untuk menentukan laut vs darat
            # Referensi coastline dari analisis garis pantai: ~ -8.02
            coast_lat_ref = -8.02
            lat_grid, _ = np.meshgrid(fill_lat_arr, fill_lon_arr, indexing='ij')

            # Cells di selatan coastline → laut (set ke -10m)
            # Cells di utara coastline → tetap NaN (akan diinterpolasi)
            ocean_mask = (lat_grid < coast_lat_ref) & np.isnan(elev_grid)
            land_nan_mask = (lat_grid >= coast_lat_ref) & np.isnan(elev_grid)

            ocean_count = int(np.sum(ocean_mask))
            land_nan_count = int(np.sum(land_nan_mask))

            if ocean_count > 0:
                elev_grid[ocean_mask] = -10.0  # Set laut ke -10m
                logger.info(f"[Inundasi] {ocean_count} NaN cells di laut set ke -10m")

            # Interpolasi NaN cells di darat (jika scipy tersedia)
            if land_nan_count > 0:
                if SCIPY_AVAILABLE:
                    try:
                        mask = np.isnan(elev_grid)
                        ind = distance_transform_edt(mask, return_distances=False, return_indices=True)
                        elev_grid = elev_grid[tuple(ind)]
                        logger.info(f"[Inundasi] Interpolasi {land_nan_count} sel NaN darat via nearest-neighbor")
                    except Exception as e:
                        logger.warning(f"[Inundasi] Interpolasi gagal: {e}")
                        # Fallback: set ke 5m (darat rata-rata)
                        elev_grid[land_nan_mask] = 5.0
                        logger.warning(f"[Inundasi] {land_nan_count} NaN darat set ke 5m (fallback)")
                else:
                    logger.warning(f"[Inundasi] {land_nan_count} NaN darat tapi scipy tidak terinstall")
                    # Fallback: set ke 5m (darat rata-rata)
                    elev_grid[land_nan_mask] = 5.0
                    logger.warning(f"[Inundasi] {land_nan_count} NaN darat set ke 5m (fallback)")

        # ── Step 2: Identifikasi sel pantai (seed BFS) ──
        is_land = np.where(~np.isnan(elev_grid), elev_grid >= 0, False)
        is_ocean = np.where(~np.isnan(elev_grid), elev_grid < 0, False)

        # Land cells adjacent to ocean (4-connectivity)
        ocean_neighbor = np.zeros_like(is_land)
        ocean_neighbor[1:, :] |= is_ocean[:-1, :]
        ocean_neighbor[:-1, :] |= is_ocean[1:, :]
        ocean_neighbor[:, 1:] |= is_ocean[:, :-1]
        ocean_neighbor[:, :-1] |= is_ocean[:, 1:]

        coast_mask = is_land & ocean_neighbor
        coast_mask[0, :] = False; coast_mask[-1, :] = False
        coast_mask[:, 0] = False; coast_mask[:, -1] = False
        coast_j, coast_i = np.where(coast_mask)
        coast_seeds = list(zip(coast_j.tolist(), coast_i.tolist()))

        logger.info(f"[Inundasi] Sel pantai (seed): {len(coast_seeds)}")

        # ── Step 3: BFS flood-fill dari pantai dengan atenuasi Manning ──
        K_ATEN = 0.30      # atenuasi per km (mengikuti reference)
        N_LAND = 0.045      # Manning's n untuk daratan berpenghuni

        flood_grid = np.full((fill_ny, fill_nx), -1.0, dtype=np.float32)
        dist_grid = np.full((fill_ny, fill_nx), -1.0, dtype=np.float32)
        visited = np.zeros((fill_ny, fill_nx), dtype=bool)

        queue = deque()
        for j, i in coast_seeds:
            elev = elev_grid[j, i]
            if np.isnan(elev) or elev > runup_m:
                continue
            flood_d = runup_m - elev
            if flood_d > 0.05:
                flood_grid[j, i] = flood_d
                dist_grid[j, i] = 0.0
                visited[j, i] = True
                queue.append((j, i, 0.0))

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        while queue:
            cj, ci, dist_km = queue.popleft()
            for dj, di in directions:
                nj, ni = cj + dj, ci + di
                if nj < 0 or nj >= fill_ny or ni < 0 or ni >= fill_nx:
                    continue
                if visited[nj, ni]:
                    continue

                elev = elev_grid[nj, ni]
                if np.isnan(elev):
                    visited[nj, ni] = True
                    continue

                # Admin mask check
                if prepared_mask:
                    lon_n = float(fill_lon_arr[ni])
                    lat_n = float(fill_lat_arr[nj])
                    if not prepared_mask.contains(Point(lon_n, lat_n)):
                        visited[nj, ni] = True
                        continue

                new_dist = dist_km + FILL_DX_KM
                alpha_eff = K_ATEN * (N_LAND / 0.025)
                eff_runup = runup_m * math.exp(-alpha_eff * new_dist)

                if elev > eff_runup:
                    visited[nj, ni] = True
                    continue
                if elev < 0:  # strictly land only
                    visited[nj, ni] = True
                    continue

                flood_d = eff_runup - elev
                if flood_d < 0.05:
                    visited[nj, ni] = True
                    continue

                flood_grid[nj, ni] = flood_d
                dist_grid[nj, ni] = new_dist
                visited[nj, ni] = True
                queue.append((nj, ni, new_dist))

        # ── Step 4: Konversi flood_grid ke GeoJSON (Points) ──
        COLOR_MAP = {
            "EKSTREM": "#ff0000",
            "TINGGI":  "#ff6400",
            "SEDANG":  "#ffb400",
            "RENDAH":  "#ffe650",
        }

        features = []
        for j in range(fill_ny):
            for i in range(fill_nx):
                fd = flood_grid[j, i]
                if fd <= 0.05:
                    continue

                lon = float(fill_lon_arr[i])
                lat = float(fill_lat_arr[j])

                # Final admin mask check
                if prepared_mask:
                    if not prepared_mask.contains(Point(lon, lat)):
                        continue

                # Only output points on land
                if elev_grid[j, i] < 0:
                    continue

                risk = ("EKSTREM" if fd >= 10 else
                        "TINGGI"  if fd >= 5  else
                        "SEDANG"  if fd >= 2  else "RENDAH")

                elev = float(elev_grid[j, i])
                d_km = float(dist_grid[j, i])
                if d_km < 0:
                    d_km = 0.0

                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "flood_depth": round(float(fd), 2),
                        "elev_m":      round(elev, 1),
                        "dist_km":     round(d_km, 2),
                        "risk":        risk,
                        "color":       COLOR_MAP[risk],
                    }
                })

        logger.info(f"[Inundasi] ✅ Hi-res BFS flood-fill: {len(features)} sel tergenang "
                    f"(runup={runup_m:.1f}m, grid={fill_ny}×{fill_nx})")

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "runup_m":     round(runup_m, 2),
                "total_cells": len(features),
                "format":      "points",
                "fill_dx_deg": FILL_DX,
                "fill_grid":   f"{fill_ny}x{fill_nx}",
                "model":       "SWE + DEM_HiRes_BFS_FloodFill + Manning_Attenuation",
            }
        }


# ============================================================================
# InundationData helpers
# ============================================================================

def inundation_to_abm_dict(data: InundationData) -> Dict:
    """
    Konversi InundationData ke format yang diharapkan
    EvacuationABMSolver.set_swe_results().
    """
    return {
        "flood_polygons":     data.flood_polygons,
        "max_wave_height":    data.inundation_grid.tolist() if data.inundation_grid is not None else [],
        "grid_info": {
            "lats":  data.lats,
            "lons":  data.lons,
            "shape": list(data.shape),
        },
        "per_desa_flood": {
            name: {
                "wave_height_m": v.wave_height_m,
                "danger_zone":   v.danger_zone,
                "inundated":     v.inundated,
                "terdampak":     v.terdampak,
                "population":    v.population,
            }
            for name, v in data.per_desa_flood.items()
        },
        "max_runup_m":         data.max_runup_m,
        "inundation_area_km2": data.inundation_area_km2,
    }


def affected_villages_from_inundation(data: InundationData) -> List[Dict]:
    """
    Konversi per_desa_flood → list affected_villages (format frontend).
    """
    villages = []
    for name, info in data.per_desa_flood.items():
        villages.append({
            "desa":          name,
            "name":          name,
            "lat":           info.lat,
            "lon":           info.lon,
            "latitude":      info.lat,
            "longitude":     info.lon,
            "wave_height_m": info.wave_height_m,
            "danger_zone":   info.danger_zone,
            "zona_bahaya":   info.danger_zone,
            "color":         DANGER_COLORS.get(info.danger_zone, "#3388ff"),
            "population":    info.population,
            "terdampak":     info.terdampak,
            "percentage":    min(100, int(info.wave_height_m * 20)),
            "dist_km":       info.dist_coast_km,
            "coordinates":   [info.lat, info.lon],
        })
    return villages


__all__ = [
    "InundationConnector",
    "InundationData",
    "VillageFloodInfo",
    "inundation_to_abm_dict",
    "affected_villages_from_inundation",
    "classify_danger_zone",
    "DANGER_COLORS",
]
