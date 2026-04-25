"""
Dynamic Fault Loader
====================
Scan dan load semua fault shapefile dari Pusgen 2016 data.
Membaca fault geometry, parameters, dan metadata secara dinamis.

Author: WebGIS Tsunami Team
Version: 1.0.0
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger("fault_loader")

try:
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import Point, LineString
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    logger.warning("geopandas not available - fault loading disabled")


@dataclass
class FaultSegment:
    """Representasi satu segmen fault."""
    id: str
    name: str
    type: str  # SS, R45S, Norm60S, dll
    mmax_d: float  # Magnitude maksimum design
    slip_rate: float  # mm/year
    geometry: LineString  # Shapely LineString
    length_km: float
    centroid_lat: float
    centroid_lon: float
    source: str  # Nama shapefile


@dataclass
class FaultInfo:
    """Informasi lengkap tentang sebuah fault (dari 1 atau lebih segmen)."""
    id: str  # Unique ID (lowercase, underscored)
    name: str  # Nama fault
    category: str  # 'fault' atau 'megathrust'
    type: str  # Dominant fault type
    segments: List[FaultSegment]
    mmax_d: float  # Magnitude maksimum dari semua segmen
    slip_rate: float  # Rata-rata slip rate
    total_length_km: float  # Total panjang semua segmen
    epicenter_lat: float  # Weighted centroid
    epicenter_lon: float  # Weighted centroid
    strike: Optional[float] = None  # Akan dihitung dari geometry
    dip: Optional[float] = None  # Dari tipe fault
    rake: Optional[float] = None  # Dari tipe fault
    source_file: str = ""


class FaultLoader:
    """
    Dynamic fault loader - scan dan load fault dari shapefile.

    OPTIMIZATION: Cache ke disk untuk loading super cepat (< 1 detik)
    """

    # Cache file
    CACHE_FILE = "fault_cache.json"

    # Fault type mapping dari Pusgen 2016
    FAULT_TYPE_MAPPING = {
        'SS': {'type': 'strike_slip', 'dip': 90.0, 'rake': 0.0, 'name': 'Strike-Slip'},
        'R45S': {'type': 'reverse', 'dip': 45.0, 'rake': 90.0, 'name': 'Reverse 45°'},
        'R60S': {'type': 'reverse', 'dip': 60.0, 'rake': 90.0, 'name': 'Reverse 60°'},
        'R30S': {'type': 'reverse', 'dip': 30.0, 'rake': 90.0, 'name': 'Reverse 30°'},
        'Norm60S': {'type': 'normal', 'dip': 60.0, 'rake': -90.0, 'name': 'Normal 60°'},
        'Norm60W': {'type': 'normal', 'dip': 60.0, 'rake': -90.0, 'name': 'Normal 60°'},
        'Thrust': {'type': 'thrust', 'dip': 15.0, 'rake': 90.0, 'name': 'Thrust'},
        'Unknown': {'type': 'strike_slip', 'dip': 90.0, 'rake': 0.0, 'name': 'Unknown'},
    }

    def __init__(self, data_dir: str):
        """
        Initialize fault loader.

        Args:
            data_dir: Path ke direktori data/Vektor
        """
        self.data_dir = data_dir
        self.faults: Dict[str, FaultInfo] = {}
        self.public_labels: Dict[str, dict] = {}

    def scan_and_load_all(self, force_reload: bool = False) -> int:
        """
        Scan semua shapefile dan load fault data.

        Args:
            force_reload: Jika True, skip cache dan reload dari shapefile

        Returns:
            Jumlah fault yang berhasil di-load
        """
        if not GEOPANDAS_AVAILABLE:
            logger.error("Cannot load faults: geopandas not available")
            return 0

        # Coba load dari cache dulu (SUPER CEPAT!)
        if not force_reload:
            cached = self._load_from_cache()
            if cached is not None:
                self.faults = cached
                self._build_public_labels()
                logger.info(f"[FaultLoader] ✅ Loaded from cache: {len(self.faults)} faults (< 1 detik!)")
                return len(self.faults)

        # Cache tidak ada atau force_reload → scan shapefile
        logger.info(f"[FaultLoader] Scanning fault data in {self.data_dir}...")

        # Cari semua shapefile yang relevan
        shapefiles = self._find_fault_shapefiles()

        logger.info(f"[FaultLoader] Found {len(shapefiles)} shapefiles")

        # Load setiap shapefile
        total_faults = 0
        for shp_path, category in shapefiles:
            count = self._load_shapefile(shp_path, category)
            total_faults += count

        logger.info(f"[FaultLoader] Total faults loaded: {total_faults}")
        self._build_public_labels()

        # Simpan ke cache untuk next time (SUPER CEPAT!)
        self._save_to_cache()
        logger.info(f"[FaultLoader] ✅ Saved to cache: {len(self.faults)} faults")

        return total_faults

    def _load_from_cache(self) -> Optional[Dict[str, FaultInfo]]:
        """Load fault data dari cache file (JSON)."""
        cache_path = os.path.join(self.data_dir, self.CACHE_FILE)

        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)

            # Check cache age (max 7 days)
            cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            age = (datetime.now() - cache_time).days

            if age > 7:
                logger.info(f"[FaultLoader] Cache expired ({age} days old)")
                return None

            # Reconstruct FaultInfo objects
            faults = {}
            for fault_id, fault_dict in cache_data.get('faults', {}).items():
                # Reconstruct segments
                segments = []
                for seg_dict in fault_dict.get('segments', []):
                    # Reconstruct LineString geometry
                    from shapely.geometry import LineString
                    coords = seg_dict['geometry']
                    geom = LineString(coords)

                    segment = FaultSegment(
                        id=seg_dict['id'],
                        name=seg_dict['name'],
                        type=seg_dict['type'],
                        mmax_d=seg_dict['mmax_d'],
                        slip_rate=seg_dict['slip_rate'],
                        geometry=geom,
                        length_km=seg_dict['length_km'],
                        centroid_lat=seg_dict['centroid_lat'],
                        centroid_lon=seg_dict['centroid_lon'],
                        source=seg_dict['source']
                    )
                    segments.append(segment)

                # Reconstruct FaultInfo
                fault_info = FaultInfo(
                    id=fault_dict['id'],
                    name=fault_dict['name'],
                    category=fault_dict['category'],
                    type=fault_dict['type'],
                    segments=segments,
                    mmax_d=fault_dict['mmax_d'],
                    slip_rate=fault_dict['slip_rate'],
                    total_length_km=fault_dict['total_length_km'],
                    epicenter_lat=fault_dict['epicenter_lat'],
                    epicenter_lon=fault_dict['epicenter_lon'],
                    strike=fault_dict.get('strike'),
                    dip=fault_dict.get('dip'),
                    rake=fault_dict.get('rake'),
                    source_file=fault_dict.get('source_file', '')
                )
                faults[fault_id] = fault_info

            return faults

        except Exception as e:
            logger.warning(f"[FaultLoader] Failed to load cache: {e}")
            return None

    def _save_to_cache(self):
        """Save fault data ke cache file (JSON)."""
        cache_path = os.path.join(self.data_dir, self.CACHE_FILE)

        try:
            # Convert FaultInfo → dict (serializable)
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'count': len(self.faults),
                'faults': {}
            }

            for fault_id, fault in self.faults.items():
                # Convert segments → dict
                segments_data = []
                for seg in fault.segments:
                    seg_dict = {
                        'id': seg.id,
                        'name': seg.name,
                        'type': seg.type,
                        'mmax_d': seg.mmax_d,
                        'slip_rate': seg.slip_rate,
                        'geometry': list(seg.geometry.coords),  # LineString → list of tuples
                        'length_km': seg.length_km,
                        'centroid_lat': seg.centroid_lat,
                        'centroid_lon': seg.centroid_lon,
                        'source': seg.source
                    }
                    segments_data.append(seg_dict)

                # Convert fault → dict
                cache_data['faults'][fault_id] = {
                    'id': fault.id,
                    'name': fault.name,
                    'category': fault.category,
                    'type': fault.type,
                    'segments': segments_data,
                    'mmax_d': fault.mmax_d,
                    'slip_rate': fault.slip_rate,
                    'total_length_km': fault.total_length_km,
                    'epicenter_lat': fault.epicenter_lat,
                    'epicenter_lon': fault.epicenter_lon,
                    'strike': fault.strike,
                    'dip': fault.dip,
                    'rake': fault.rake,
                    'source_file': fault.source_file
                }

            # Save to JSON
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.warning(f"[FaultLoader] Failed to save cache: {e}")

    def _find_fault_shapefiles(self) -> List[Tuple[str, str]]:
        """
        Cari semua shapefile fault di direktori data.

        Returns:
            List of (shapefile_path, category) tuples
        """
        shapefiles = []

        # Keywords untuk mencari fault shapefile
        fault_keywords = ['fault', 'sesar', 'megathrust', 'pusgen']

        if not os.path.isdir(self.data_dir):
            logger.warning(f"[FaultLoader] Data directory not found: {self.data_dir}")
            return shapefiles

        # Scan semua folder dan subfolder
        for root, dirs, files in os.walk(self.data_dir):
            # Skip hidden folders dan venv
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'venv']

            for fname in files:
                if not fname.lower().endswith('.shp'):
                    continue

                # Cek apakah file ini fault-related
                full_path = os.path.join(root, fname)
                fname_lower = fname.lower()

                # Tentukan category
                if any(kw in fname_lower for kw in fault_keywords):
                    category = 'megathrust' if 'megathrust' in fname_lower else 'fault'
                    shapefiles.append((full_path, category))

        return shapefiles

    def _load_shapefile(self, shp_path: str, category: str) -> int:
        """
        Load satu shapefile dan extract fault data.

        Args:
            shp_path: Path ke shapefile
            category: 'fault' atau 'megathrust'

        Returns:
            Jumlah fault yang di-load
        """
        try:
            logger.info(f"[FaultLoader] Loading: {os.path.basename(shp_path)}")

            # Load shapefile
            gdf = gpd.read_file(shp_path, engine='pyogrio')

            # Pastikan CRS WGS84
            if gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)

            # Filter hanya LineString
            gdf = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]

            logger.info(f"[FaultLoader]   {len(gdf)} fault segments found")

            # Group segments by fault name
            fault_groups = self._group_by_fault_name(gdf)

            # Convert ke FaultInfo
            count = 0
            for fault_name, segments_gdf in fault_groups.items():
                # 🔧 FIX: Create fault PER SEGMENT (bukan per fault name)
                # Agar ID match dengan frontend (baribis-1, baribis-2, dll)

                # Cek apakah ada field Segment
                if 'Segment' in segments_gdf.columns and not segments_gdf['Segment'].isna().all():
                    # Group by Segment → create individual fault per segment
                    segment_groups = segments_gdf.groupby('Segment')

                    for segment_name, seg_gdf in segment_groups:
                        fault_info = self._create_fault_info(fault_name, seg_gdf, category, shp_path,
                                                                segment_name=segment_name)
                        if fault_info:
                            self.faults[fault_info.id] = fault_info
                            count += 1
                else:
                    # Tidak ada segment → buat 1 fault untuk semua
                    fault_info = self._create_fault_info(fault_name, segments_gdf, category, shp_path)
                    if fault_info:
                        self.faults[fault_info.id] = fault_info
                        count += 1

            logger.info(f"[FaultLoader]   {count} faults loaded")
            return count

        except Exception as e:
            logger.error(f"[FaultLoader] Error loading {shp_path}: {e}")
            return 0

    def _group_by_fault_name(self, gdf: gpd.GeoDataFrame) -> Dict[str, gpd.GeoDataFrame]:
        """Group segments by fault name."""
        # Cari column yang berisi nama fault
        name_column = None
        for col in gdf.columns:
            col_lower = col.lower()
            if 'name' in col_lower or 'namobj' in col_lower or 'fault' in col_lower:
                name_column = col
                break

        if name_column is None:
            # Fallback: gunakan semua sebagai 1 fault
            return {"Unknown": gdf}

        # Group by name
        groups = defaultdict(list)
        for idx, row in gdf.iterrows():
            fault_name = str(row[name_column])
            if not fault_name or fault_name == '' or fault_name == 'None':
                fault_name = f"Unknown_{idx}"
            groups[fault_name].append(idx)

        # Create GeoDataFrame for each group
        result = {}
        for fault_name, indices in groups.items():
            result[fault_name] = gdf.iloc[indices]

        return result

    def _create_fault_info(self, fault_name: str, segments_gdf: gpd.GeoDataFrame,
                         category: str, source_file: str, segment_name: Optional[str] = None) -> Optional[FaultInfo]:
        """
        Create FaultInfo from fault segments.

        Args:
            fault_name: Nama fault (dari shapefile)
            segments_gdf: GeoDataFrame berisi segments
            category: 'fault' atau 'megathrust'
            source_file: Path ke shapefile
            segment_name: Nama segment (opsional) untuk membuat fault per segment
        """
        try:
            # Generate fault ID (lowercase, underscored)
            base_id = fault_name.lower().replace(' ', '_').replace('-', '_').replace('/', '_')

            if segment_name:
                # Tambah segment ke ID
                seg_id = segment_name.lower().replace(' ', '_').replace('-', '_').replace('/', '_')
                fault_id = f"{base_id}_{seg_id}"
            else:
                fault_id = base_id

            # Extract segments
            segments = []
            total_length = 0
            weighted_lat = 0
            weighted_lon = 0
            mmax_values = []
            sliprate_values = []

            for idx, row in segments_gdf.iterrows():
                geom = row.geometry

                # Handle MultiLineString
                if geom.geom_type == 'MultiLineString':
                    lines = list(geom.geoms)
                else:
                    lines = [geom]

                for line in lines:
                    # Calculate length in km
                    length_m = line.length
                    length_km = length_m / 1000

                    # Get centroid
                    centroid = line.centroid
                    centroid_lat = centroid.y
                    centroid_lon = centroid.x

                    # Extract parameters
                    mmax = self._extract_mmax(row)
                    sliprate = self._extract_sliprate(row)
                    fault_type = self._extract_type(row)

                    segment = FaultSegment(
                        id=f"{fault_id}_{len(segments)}",
                        name=fault_name,
                        type=fault_type,
                        mmax_d=mmax,
                        slip_rate=sliprate,
                        geometry=line,
                        length_km=length_km,
                        centroid_lat=centroid_lat,
                        centroid_lon=centroid_lon,
                        source=os.path.basename(source_file)
                    )
                    segments.append(segment)

                    total_length += length_km
                    weighted_lat += centroid_lat * length_km
                    weighted_lon += centroid_lon * length_km
                    mmax_values.append(mmax)
                    sliprate_values.append(sliprate)

            if not segments:
                return None

            # Calculate aggregate values
            epicenter_lat = weighted_lat / total_length
            epicenter_lon = weighted_lon / total_length
            avg_mmax = max(mmax_values)  # Use max Mmax
            avg_sliprate = np.mean(sliprate_values)

            # Determine dominant fault type
            type_counts = defaultdict(int)
            for seg in segments:
                type_counts[seg.type] += 1
            dominant_type = max(type_counts, key=type_counts.get)

            # Get fault parameters
            fault_params = self.FAULT_TYPE_MAPPING.get(
                dominant_type,
                self.FAULT_TYPE_MAPPING['Unknown']
            )

            fault_info = FaultInfo(
                id=fault_id,
                name=fault_name,
                category=category,
                type=dominant_type,
                segments=segments,
                mmax_d=avg_mmax,
                slip_rate=avg_sliprate,
                total_length_km=total_length,
                epicenter_lat=epicenter_lat,
                epicenter_lon=epicenter_lon,
                strike=fault_params.get('strike'),  # TODO: Calculate from geometry
                dip=fault_params.get('dip'),
                rake=fault_params.get('rake'),
                source_file=os.path.basename(source_file)
            )

            return fault_info

        except Exception as e:
            logger.error(f"[FaultLoader] Error creating fault info for {fault_name}: {e}")
            return None

    def _extract_mmax(self, row) -> float:
        """Extract Mmax (magnitude maksimum) dari row."""
        for col in row.index:
            if 'mmax' in col.lower():
                try:
                    val = float(row[col])
                    return max(5.0, min(9.5, val))  # Clamp
                except:
                    continue
        return 7.0  # Default

    def _extract_sliprate(self, row) -> float:
        """Extract slip rate dari row."""
        for col in row.index:
            if 'slip' in col.lower():
                try:
                    val = float(row[col])
                    return max(0.0, val)
                except:
                    continue
        return 1.0  # Default mm/year

    def _extract_type(self, row) -> str:
        """Extract fault type dari row."""
        for col in row.index:
            if 'type' in col.lower():
                val = str(row[col])
                if val and val != '' and val != 'None':
                    return val
        return 'Unknown'

    def get_fault(self, fault_id: str) -> Optional[FaultInfo]:
        """
        Get fault by ID.

        Args:
            fault_id: Fault ID (e.g. 'opak', 'lembang', 'baribis_kendengf')

        Returns:
            FaultInfo object atau None jika tidak ditemukan
        """
        return self.faults.get(fault_id.lower())

    def list_faults(self, category: Optional[str] = None) -> List[str]:
        """
        List semua fault ID.

        Args:
            category: Filter by category ('fault', 'megathrust', atau None untuk semua)

        Returns:
            List of fault IDs
        """
        if category:
            return [fid for fid, f in self.faults.items() if f.category == category]
        return list(self.faults.keys())

    def _build_public_labels(self):
        """Build public labels (safe to send to frontend)."""
        self.public_labels = {}

        for fault_id, fault in self.faults.items():
            # Tentukan recurrence/period untuk megathrust
            recurrence = self._infer_recurrence(fault)

            self.public_labels[fault_id] = {
                "label": fault.name,
                "mw": fault.mmax_d,
                "category": fault.category,
                "recurrence": recurrence,
                "view_lat": fault.epicenter_lat,
                "view_lon": fault.epicenter_lon,
                "view_zoom": 10 if fault.category == 'fault' else 8
            }

    def _infer_recurrence(self, fault: FaultInfo) -> str:
        """Infer recurrence period untuk fault."""
        if fault.category == 'megathrust':
            # Megathrust: berdasarkan panjang
            if fault.total_length_km > 500:
                return "500+ tahun"
            elif fault.total_length_km > 300:
                return "200-500 tahun"
            else:
                return "100-200 tahun"
        else:
            # Regular fault: berdasarkan slip rate
            if fault.slip_rate > 2.0:
                return "Aktif"
            elif fault.slip_rate > 0.5:
                return "Sedang"
            else:
                return "Rendah"

    def get_public_labels(self) -> Dict[str, dict]:
        """Get public labels (aman untuk frontend)."""
        return self.public_labels


# Global cache instance
_fault_loader_cache: Optional[FaultLoader] = None


def get_fault_loader(data_dir: str = None) -> Optional[FaultLoader]:
    """
    Get atau buat FaultLoader instance.

    Args:
        data_dir: Path ke data/Vektor directory

    Returns:
        FaultLoader instance atau None jika geopandas tidak tersedia
    """
    global _fault_loader_cache

    if _fault_loader_cache is not None:
        return _fault_loader_cache

    if data_dir is None:
        # Default path
        current_dir = os.path.dirname(__file__)
        data_dir = os.path.join(current_dir, "..", "..", "..", "data", "Vektor")
        data_dir = os.path.abspath(data_dir)

    if not GEOPANDAS_AVAILABLE:
        return None

    _fault_loader_cache = FaultLoader(data_dir)
    return _fault_loader_cache
