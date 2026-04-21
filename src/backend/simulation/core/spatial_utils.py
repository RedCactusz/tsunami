"""
spatial_utils.py — Utilitas Spasial & Batimetri Terpusat
========================================================
Single Source of Truth untuk semua logika spasial, masking, dan routing.
"""
import os, sys, glob, struct, math, json
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from shapely.geometry import shape, Point, Polygon
    from shapely.prepared import prep
    from shapely.ops import unary_union
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

try:
    import rasterio
    from rasterio.transform import rowcol
    USE_RASTERIO = True
except ImportError:
    USE_RASTERIO = False

try:
    import geopandas as gpd
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False

DEG2RAD    = math.pi / 180
RAD2DEG    = 180 / math.pi
EARTH_R    = 6371000.0     # jari-jari bumi (m)

# Manning roughness (COMCOT default)
N_OCEAN    = 0.013         # laut terbuka
N_SHORE    = 0.025         # pantai (default fallback daratan)

# Referensi Koefisien Kekasaran Tutupan Lahan - Penelitian Bantul 2024
BANTUL_ROUGHNESS_LULC = {
    "Badan Air"                    : 0.007,
    "Belukar / Semak"              : 0.040,
    "Hutan"                        : 0.070,
    "Kebun / Perkebunan"           : 0.035,
    "Lahan Kosong / Terbuka"       : 0.015,
    "Lahan Pertanian"              : 0.025,
    "Permukiman / Lahan Terbangun" : 0.045,
    "Mangrove"                     : 0.025,
    "Tambak / Empang"              : 0.010,
}

# Domain default — Fokus area Bantul (palung Jawa → daratan Bantul)
# Diperkecil dari domain lama (Jawa Selatan luas) untuk efisiensi
DOMAIN_DEFAULT = {
    "lat_min": -10.0,      # mencakup palung Jawa (sumber gempa)
    "lat_max":  -7.5,      # mencakup daratan Bantul
    "lon_min": 109.5,      # barat Bantul + buffer propagasi
    "lon_max": 111.0,      # timur Bantul + buffer propagasi
    "dx_deg" :   0.004,    # ~460m (resolusi tinggi, setara GEBCO)
}

# Zona nearshore (kedalaman < batas ini → nonlinear SWE)
NEARSHORE_DEPTH_M = 50.0


# ═══════════════════════════════════════════════════════════════════════════
def haversine_km(lat1: float, lon1: float,
                 lat2: float, lon2: float) -> float:
    """
    Hitung jarak antara dua titik di permukaan bumi menggunakan formula
    Haversine. Hasil dalam kilometer.

    Parameters
    ----------
    lat1, lon1 : float — koordinat titik pertama (derajat)
    lat2, lon2 : float — koordinat titik kedua  (derajat)

    Returns
    -------
    float — jarak dalam km
    """
    dlat = (lat2 - lat1) * DEG2RAD
    dlon = (lon2 - lon1) * DEG2RAD
    a    = (math.sin(dlat / 2) ** 2
            + math.cos(lat1 * DEG2RAD) * math.cos(lat2 * DEG2RAD)
            * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_R / 1000 * math.asin(math.sqrt(a))


# Alias dengan underscore untuk kompatibilitas internal swe_solver
_haversine_km = haversine_km


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Hitung jarak antara dua titik di permukaan bumi menggunakan formula
    Haversine. Hasil dalam meter.

    Parameters
    ----------
    lat1, lon1 : float — koordinat titik pertama (derajat)
    lat2, lon2 : float — koordinat titik kedua  (derajat)

    Returns
    -------
    float — jarak dalam meter
    """
    phi1  = math.radians(lat1)
    phi2  = math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a     = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return EARTH_R * 2 * math.asin(math.sqrt(a))


# ═══════════════════════════════════════════════════════════════════════════
class CoastlineMask:
    """
    Memuat shapefile garis pantai (polyline) dan menyediakan is_ocean(lon, lat).

    Metode: Coast Profile
    ─────────────────────
    Untuk setiap bin longitude (resolusi 0.002°), kita simpan semua nilai
    latitude dari titik-titik garis pantai. Kemudian untuk query:

      lat < min(coast_lat di bin lon ini)  →  LAUT   (selatan garis pantai Jawa)
      lat > min(coast_lat di bin lon ini)  →  DARAT  (utara garis pantai Jawa)

    Metode ini lebih reliable daripada ray-casting untuk polyline (bukan polygon),
    dan sudah divalidasi dengan data Garis_Pantai_Bantul.shp.

    Untuk area di luar bbox coverage coastline → return None
    (masking hanya dari Layer 1+2).
    """

    BIN_SIZE     = 0.002    # resolusi bin lon ~220m
    SEARCH_RANGE = 5        # cari ±5 bin (~1.1km) jika bin kosong
    COAST_BUFFER = 0.0005   # ~55m buffer di batas pantai untuk hindari noise

    def __init__(self, shp_path: str):
        self.segments: List[List[Tuple[float,float]]] = []
        self.bbox: Optional[Tuple]  = None
        self._profile: dict         = {}   # lon_bin → [lat, lat, ...]
        self._load(shp_path)

    def _load(self, path: str):
        print(f"\n📍 Memuat coastline mask: {path}")
        try:
            with open(path, 'rb') as f:
                data = f.read()

            pos = 100
            while pos < len(data) - 8:
                if pos + 8 > len(data): break
                content_len = struct.unpack_from('>I', data, pos+4)[0] * 2
                pos += 8
                if pos + 4 > len(data): break
                stype = struct.unpack_from('<I', data, pos)[0]
                if stype in (3, 5):
                    num_parts  = struct.unpack_from('<I', data, pos+36)[0]
                    num_points = struct.unpack_from('<I', data, pos+40)[0]
                    parts = list(struct.unpack_from(f'<{num_parts}I', data, pos+44))
                    parts.append(num_points)
                    coords = struct.unpack_from(f'<{num_points*2}d', data, pos+44+num_parts*4)
                    for i in range(num_parts):
                        s, e = parts[i], parts[i+1]
                        seg = [(coords[j*2], coords[j*2+1]) for j in range(s, e)]
                        self.segments.append(seg)
                pos += content_len

            if self.segments:
                all_lons = [p[0] for seg in self.segments for p in seg]
                all_lats = [p[1] for seg in self.segments for p in seg]
                if all_lons and all_lats:
                    self.bbox = (min(all_lons), min(all_lats), max(all_lons), max(all_lats))
                else:
                    self.bbox = None
            else:
                self.bbox = None

            # Bangun profil: lon_bin → list of coast latitudes
            for seg in self.segments:
                for lon, lat in seg:
                    key = round(round(lon / self.BIN_SIZE) * self.BIN_SIZE, 6)
                    self._profile.setdefault(key, []).append(lat)

            print(f"  ✓ {len(self.segments)} segmen, {sum(len(v) for v in self._profile.values())} sel")
            print(f"  ✓ {len(self._profile)} bin longitude (resolusi {self.BIN_SIZE}°)")
            if self.bbox:
                print(f"  bbox: lon {self.bbox[0]:.4f}–{self.bbox[2]:.4f}, lat {self.bbox[1]:.4f}–{self.bbox[3]:.4f}")
            else:
                print(f"  ⚠ Coastline bbox kosong")

        except Exception as e:
            print(f"  ✗ Gagal load coastline: {e}")
            self.segments = []; self.bbox = None

    def in_coverage(self, lon: float, lat: float) -> bool:
        if not self.bbox: return False
        buf = 0.05
        return (self.bbox[0]-buf <= lon <= self.bbox[2]+buf and
                self.bbox[1]-buf <= lat <= self.bbox[3]+buf)

    def _get_coast_lats(self, lon: float) -> Optional[List[float]]:
        """Cari semua coast lat di sekitar longitude ini."""
        lon_bin = round(round(lon / self.BIN_SIZE) * self.BIN_SIZE, 6)
        lats = []
        for i in range(-self.SEARCH_RANGE, self.SEARCH_RANGE+1):
            key = round(lon_bin + i * self.BIN_SIZE, 6)
            if key in self._profile:
                lats.extend(self._profile[key])
        return lats if lats else None

    def is_ocean(self, lon: float, lat: float) -> Optional[bool]:
        """
        Return:
          True  → LAUT   (gunakan BATNAS)
          False → DARAT  (skip BATNAS → fallback GEBCO)
          None  → di luar coverage shapefile (Layer 1+2 saja)
        """
        if not self.in_coverage(lon, lat):
            return None

        coast_lats = self._get_coast_lats(lon)
        if coast_lats is None:
            return None

        # Untuk Jawa Selatan: laut di selatan garis pantai
        # → lat titik < min(coast_lat) = laut
        min_coast_lat = min(coast_lats)
        return lat < (min_coast_lat + self.COAST_BUFFER)

    def debug_info(self, lon: float, lat: float) -> dict:
        in_cov     = self.in_coverage(lon, lat)
        coast_lats = self._get_coast_lats(lon)
        result     = self.is_ocean(lon, lat)
        return {
            "in_coverage":       in_cov,
            "coast_lats_nearby": len(coast_lats) if coast_lats else 0,
            "min_coast_lat":     min(coast_lats) if coast_lats else None,
            "query_lat":         lat,
            "result":            result,
            "interpretation":    "laut" if result is True else ("daratan" if result is False else "di_luar_coverage")
        }


# ═══════════════════════════════════════════════════════════════
def is_valid_ocean_depth(
    val: float,
    lon: float,
    lat: float,
    coast_mask=None,
    nodata_values: tuple = (32767, -32768, -9999, 0),
) -> tuple:
    """
    Cek apakah nilai BATNAS merupakan kedalaman laut yang valid.
    Dipindahkan dari server.py.

    Lapisan pengecekan:
      Layer 1 — Threshold  : val harus < -0.5 m
      Layer 2 — Sanity     : -7500 < val < -0.5 (kedalaman valid Samudra Hindia)
      Layer 3 — Coastline  : konfirmasi posisi laut via CoastlineMask (opsional)

    Parameters
    ----------
    val          : float — nilai raw dari raster BATNAS
    lon, lat     : float — koordinat titik (derajat)
    coast_mask   : CoastlineMask | None — objek masking garis pantai (opsional)
    nodata_values: tuple — nilai yang dianggap nodata

    Returns
    -------
    (is_valid: bool, reason: str)
    """
    if val in nodata_values or val is None:
        return False, "nodata"

    # Layer 1: nilai harus negatif (laut)
    if val > 0.1:
        return False, f"layer1_positive_elevation({val:.1f}m)"

    # Layer 2: sanity range untuk region Jawa
    if val < -7500:
        return False, f"layer2_too_deep({val:.0f}m)"

    # Layer 3: coastline mask (opsional)
    if coast_mask is not None:
        ocean_status = coast_mask.is_ocean(lon, lat)
        if ocean_status is False:
            return False, "layer3_land_by_coastline"

    return True, "valid_ocean"


# ═══════════════════════════════════════════════════════════════════════════
class ManualTiffReader:
    def __init__(self, path: str):
        self.path = path
        with open(path, 'rb') as f:
            self.data = f.read()
        self._parse()

    def _u(self, fmt, off):
        return struct.unpack_from(self.endian + fmt, self.data, off)

    def _parse(self):
        self.endian = '<' if self.data[:2] == b'II' else '>'
        ifd = self._u('I', 4)[0]
        n   = self._u('H', ifd)[0]
        tags = {}
        p = ifd + 2
        for _ in range(n):
            tag, dtype, count, vraw = self._u('HHII', p)
            tags[tag] = (dtype, count, vraw)
            p += 12

        def tv(tag, default=0):
            if tag not in tags: return default
            d, c, v = tags[tag]
            if d == 3:  return struct.unpack_from(self.endian+'H', struct.pack(self.endian+'I', v))[0] if c==1 else v
            if d == 4:  return v
            if d == 5:  a,b = self._u('II', v); return a/b if b else 0
            if d == 12: return self._u('d', struct.pack(self.endian+'I',v)+b'\x00'*4)[0]
            return v

        self.width  = tags[256][2]; self.height = tags[257][2]
        self.bits   = tv(258, 16);  self.tile_w = tv(322, 0)
        self.tile_h = tv(323, 0);   self.tiled  = self.tile_w > 0
        self.sfmt   = 'h' if self.bits==16 else ('f' if self.bits==32 else 'h')

        if self.tiled:
            d,c,o = tags[324]; self.tile_offs = list(self._u(f'{c}I', o))
            d,c,o = tags[325]; self.tile_lens = list(self._u(f'{c}I', o))
        else:
            d,c,o = tags.get(273,(0,1,0)); self.strip_offs = list(self._u(f'{c}I', o)) if c>1 else [o]
            self.rows_per_strip = tv(278, self.height)

        # Geo: scale + tiepoint
        if 33550 in tags and tags[33550][1]>=3:
            sc = self._u('3d', tags[33550][2]); self.dx=sc[0]; self.dy=-sc[1]
        else:
            self.dx=self.dy=None

        if 33922 in tags and tags[33922][1]>=6:
            tp = self._u('6d', tags[33922][2])
            self.lon0=tp[3]-tp[0]*(self.dx or 0)
            self.lat0=tp[4]-tp[1]*(self.dy or 0)
        else:
            self.lon0=self.lat0=None

        # Fallback TFW
        if self.lon0 is None:
            tfw = Path(self.path).with_suffix('.tfw')
            if tfw.exists():
                v=[float(l.strip()) for l in tfw.read_text().splitlines() if l.strip()]
                if len(v)>=6:
                    self.dx=v[0]; self.dy=v[3]; self.lon0=v[4]; self.lat0=v[5]

        self.bbox = (
            self.lon0,
            self.lat0 + self.height*self.dy,
            self.lon0 + self.width*self.dx,
            self.lat0
        ) if self.lon0 else None

    def contains(self, lon, lat):
        if not self.bbox: return False
        return self.bbox[0]<=lon<=self.bbox[2] and self.bbox[1]<=lat<=self.bbox[3]

    def read_value(self, lon, lat):
        if not self.contains(lon, lat): return None
        col = int((lon-self.lon0)/self.dx)
        row = int((lat-self.lat0)/self.dy)
        col = max(0, min(col, self.width-1))
        row = max(0, min(row, self.height-1))

        if self.tiled:
            tx = col//self.tile_w; ty = row//self.tile_h
            tidx = ty*math.ceil(self.width/self.tile_w)+tx
            if tidx>=len(self.tile_offs): return None
            off=self.tile_offs[tidx]; nb=self.tile_lens[tidx]
            if off==0 or nb==0: return None
            tile=self.data[off:off+nb]
            pidx=(row%self.tile_h)*self.tile_w+(col%self.tile_w)
            bpp=self.bits//8
            if pidx*bpp+bpp>len(tile): return None
            return float(struct.unpack_from(self.endian+self.sfmt, tile, pidx*bpp)[0])
        else:
            si=row//self.rows_per_strip
            if si>=len(self.strip_offs): return None
            pidx=(row%self.rows_per_strip)*self.width+col
            bpp=self.bits//8
            return float(struct.unpack_from(self.endian+self.sfmt,
                         self.data, self.strip_offs[si]+pidx*bpp)[0])


# ═══════════════════════════════════════════════════════════════
class RasterioReader:
    def __init__(self, path):
        self.path = path
        self.ds   = rasterio.open(path)
        b = self.ds.bounds
        self.bbox    = (b.left, b.bottom, b.right, b.top)
        self.nodata  = self.ds.nodata

    def contains(self, lon, lat):
        return self.bbox[0]<=lon<=self.bbox[2] and self.bbox[1]<=lat<=self.bbox[3]

    def read_value(self, lon, lat):
        if not self.contains(lon, lat): return None
        try:
            r, c = rowcol(self.ds.transform, lon, lat)
            v = float(self.ds.read(1, window=rasterio.windows.Window(c,r,1,1))[0][0])
            return None if (self.nodata and v==self.nodata) else v
        except: return None


# ═══════════════════════════════════════════════════════════════
class BATNASTileManager:
    def __init__(self, tile_dir: str, coast_mask: Optional[CoastlineMask]=None):
        self.coast_mask = coast_mask
        self.tiles: list = []
        self._masked_land  = 0   # counter: berapa kali layer3 memblok daratan
        self._masked_value = 0   # counter: layer1+2
        self._valid_hits   = 0
        self._load(tile_dir)

    def _load(self, d):
        paths = []
        for pat in ['*.tif','*.tiff','*.TIF','*.TIFF']:
            paths.extend(glob.glob(os.path.join(d,'**',pat), recursive=True))
        print(f"\n📂 BATNAS tiles: {len(paths)} file ditemukan")
        for p in sorted(paths):
            try:
                r = RasterioReader(p) if USE_RASTERIO else ManualTiffReader(p)
                if r.bbox:
                    self.tiles.append(r)
                    print(f"  ✓ {Path(p).name:40s} {[round(x,4) for x in r.bbox]}")
                else:
                    print(f"  ⚠ {Path(p).name} — bbox tidak terbaca")
            except Exception as e:
                print(f"  ✗ {Path(p).name} — {e}")
        print(f"\n✓ {len(self.tiles)} tile siap\n")

    def query(self, lon: float, lat: float) -> Tuple[Optional[float], str]:
        """
        Return: (depth_meters, source_label) atau (None, reason)
        depth_meters positif = laut, None = daratan/nodata
        """
        for tile in self.tiles:
            if not tile.contains(lon, lat):
                continue

            raw = tile.read_value(lon, lat)
            if raw is None:
                continue

            valid, reason = is_valid_ocean_depth(raw, lon, lat, self.coast_mask)

            if valid:
                self._valid_hits += 1
                return abs(raw), f"batnas({Path(tile.path).stem})"
            else:
                if 'layer3' in reason:
                    self._masked_land += 1
                else:
                    self._masked_value += 1
                # Tidak break — coba tile lain jika ada overlap
                continue

        return None, "not_in_batnas"

    def stats(self):
        return {
            "valid_hits":    self._valid_hits,
            "masked_land":   self._masked_land,   # layer 3 blocked
            "masked_value":  self._masked_value,  # layer 1+2 blocked
        }

    def coverage_bbox(self):
        if not self.tiles: return None
        lons = [t.bbox[0] for t in self.tiles]+[t.bbox[2] for t in self.tiles]
        lats = [t.bbox[1] for t in self.tiles]+[t.bbox[3] for t in self.tiles]
        return (min(lons), min(lats), max(lons), max(lats))

    def tile_info(self):
        return [{"file": Path(t.path).name,
                 "bbox": {"lon_min":round(t.bbox[0],6),"lat_min":round(t.bbox[1],6),
                          "lon_max":round(t.bbox[2],6),"lat_max":round(t.bbox[3],6)}}
                for t in self.tiles]




# ═══════════════════════════════════════════════════════════════
class DEMManager:
    """
    Memuat satu atau lebih file DEM (GeoTIFF) untuk elevasi daratan.
    Nilai positif = elevasi mdpl, nilai negatif = abaikan (biarkan BATNAS).
    Dipakai untuk:
      - Zona inundasi (elevasi daratan vs runup)
      - Override kedalaman di daratan agar tidak salah masuk BATNAS
    """

    def __init__(self, dem_dir: str):
        self.tiles: list = []
        self._load(dem_dir)

    def _load(self, d: str):
        paths = []
        for pat in ['*.tif', '*.tiff', '*.TIF', '*.TIFF', '*.jp2', '*.JP2']:
            paths.extend(glob.glob(os.path.join(d, '**', pat), recursive=True))
        # Hanya file yang namanya mengandung 'dem' atau 'DEM'
        paths = [p for p in paths if 'dem' in Path(p).name.lower()]
        print(f"\n📂 DEM tiles: {len(paths)} file ditemukan")
        for p in sorted(paths):
            try:
                r = RasterioReader(p) if USE_RASTERIO else ManualTiffReader(p)
                if r.bbox:
                    self.tiles.append(r)
                    print(f"  ✓ {Path(p).name:40s} bbox={[round(x,4) for x in r.bbox]}")
                else:
                    print(f"  ⚠ {Path(p).name} — bbox tidak terbaca")
            except Exception as e:
                print(f"  ✗ {Path(p).name} — {e}")
        print(f"  → {len(self.tiles)} DEM tile siap")

    def query(self, lon: float, lat: float) -> Tuple[Optional[float], str]:
        """
        Kembalikan (elevasi_mdpl, sumber) atau (None, 'not_in_dem').
        Hanya kembalikan nilai jika tile ada — tidak ada fallback sintetis.
        """
        for tile in self.tiles:
            if not tile.contains(lon, lat):
                continue
            val = tile.read_value(lon, lat)
            if val is None:
                continue
            # Nodata check (DEMNAS biasanya -9999 atau 3.4e38)
            if abs(val) > 9000 or val < -500:
                continue
            return float(val), f"dem({Path(tile.path).stem})"
        return None, "not_in_dem"

    def coverage_bbox(self):
        if not self.tiles: return None
        lons = [t.bbox[0] for t in self.tiles] + [t.bbox[2] for t in self.tiles]
        lats = [t.bbox[1] for t in self.tiles] + [t.bbox[3] for t in self.tiles]
        return (min(lons), min(lats), max(lons), max(lats))

    def tile_info(self):
        return [{"file": Path(t.path).name,
                 "bbox": {"lon_min": round(t.bbox[0],6), "lat_min": round(t.bbox[1],6),
                          "lon_max": round(t.bbox[2],6), "lat_max": round(t.bbox[3],6)}}
                for t in self.tiles]

# ═══════════════════════════════════════════════════════════════
def synthetic_depth(lon: float, lat: float) -> float:
    """
    Estimasi kedalaman sintetis (meter, positif = bawah permukaan laut)
    untuk area Jawa Selatan, dipakai sebagai fallback terakhir jika
    BATNAS dan GEBCO tidak tersedia.

    Dipindahkan dari server.py (_synthetic).

    Parameters
    ----------
    lon : float — bujur (derajat)
    lat : float — lintang (derajat, negatif = selatan)

    Returns
    -------
    float — kedalaman positif dalam meter
    """
    tr = -9.5 - (lon - 110) * 0.03
    if lat > -7.8:
        return -(30 + abs(lon - 110) * 15 + (lat + 7.8) * 40)
    if lat > -8.5:
        return -(200 + 1800 * max(0, min(1, (-8.5 - lat) / 0.7)))
    if lat > -9.5:
        return -(2000 + 3000 * max(0, min(1, (-9.5 - lat) / 1)))
    if lat > -10.5:
        d = abs(lat - (tr - 0.3))
        return -(7000 + 450 * max(0, 0.5 - d))
    return -(5000 - (lat + 10.5) * 300)


# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# MASTER BATHYMETRY (Single Source of Truth)
# ═══════════════════════════════════════════════════════════════════════════
class MasterBathymetry:
    """
    Pengelola batimetri terpusat. Resolusi prioritas:
    1. BATNAS (High-res local, 3-layer masked)
    2. GEBCO Lokal (GeoTIFF)
    3. Synthetic Fallback
    """
    def __init__(self, batnas_dir: str, gebco_dir: str, coast_mask: Optional[CoastlineMask] = None):
        self.coast_mask = coast_mask
        self.batnas = BATNASTileManager(batnas_dir, coast_mask) if batnas_dir else None
        self.gebco_ds = None
        self._init_gebco(gebco_dir)

    def _init_gebco(self, gebco_dir: str):
        if not gebco_dir: return
        patterns = [
            os.path.join(gebco_dir, '**', 'gebco*.tif'),
            os.path.join(gebco_dir, '**', 'GEBCO*.tif'),
        ]
        for pat in patterns:
            files = glob.glob(pat, recursive=True)
            if files:
                p = files[0]
                try:
                    if USE_RASTERIO:
                        self.gebco_ds = RasterioReader(p)
                    else:
                        self.gebco_ds = ManualTiffReader(p)
                    print(f"  ✓ MasterBathymetry: GEBCO lokal siap ({Path(p).name})")
                    return
                except Exception as e:
                    print(f"  ⚠ Gagal muat GEBCO: {e}")

    def query(self, lon: float, lat: float) -> Tuple[Optional[float], str]:
        if self.batnas:
            d, src = self.batnas.query(lon, lat)
            if d is not None:
                # Batnas query gives positive for ocean
                return d, src

        if self.gebco_ds and self.gebco_ds.contains(lon, lat):
            val = self.gebco_ds.read_value(lon, lat)
            if val is not None:
                # GEBCO uses negative for ocean depth, but we want positive for SWE depth
                # However, for land we need negative elevation for solver masking
                # So if it's < 0, it's ocean -> return abs(val) -> positive
                # If it's > 0, it's land -> return -val -> negative
                return -val if val > 0 else abs(val), "gebco_local"

        # Synthetic depth: returns positive for ocean, negative for land
        return synthetic_depth(lon, lat), "synthetic"

    def depth_grid(self, lat_arr: np.ndarray, lon_arr: np.ndarray) -> np.ndarray:
        """Vectorized grid builder for SWE Solver"""
        ny = len(lat_arr)
        nx = len(lon_arr)
        grid = np.zeros((ny, nx))
        
        print(f"  Membangun grid batimetri {ny}x{nx} dari MasterBathymetry...")
        for j in range(ny):
            lat = float(lat_arr[j])
            for i in range(nx):
                lon = float(lon_arr[i])
                d, _ = self.query(lon, lat)
                if d is not None:
                    grid[j, i] = d
                else:
                    grid[j, i] = -10.0 # Land default if None
        return grid
def read_dbf_attrs(path: str) -> List[dict]:
    """Geopandas akan menangani ini secara otomatis, fungsi ini dipertahankan hanya jika ada pemanggilan eksternal."""
    try:
        gdf = gpd.read_file(path)
        return gdf.drop(columns='geometry').to_dict('records')
    except:
        return []

def shp_to_geojson(shp_path: str, simplify: bool = True, max_pts: int = 400) -> Optional[dict]:
    """Menggunakan Geopandas untuk konversi Shapefile ke GeoJSON dengan dukungan CRS & PolygonZ."""
    try:
        gdf = gpd.read_file(shp_path)
        if gdf.empty: return None

        # ── Transformasi CRS ke WGS84 (derajat) ──
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            print(f"  [CRS] Transformasi {shp_path} ke EPSG:4326...")
            gdf = gdf.to_crs("EPSG:4326")
        
        # ── Ambil Bounding Box ──
        bbox = list(gdf.total_bounds)
        bbox = [round(x, 5) for x in bbox]

        # ── Pastikan format GeoJSON standar ──
        return {
            "features": json.loads(gdf.to_json())['features'],
            "bbox": bbox
        }
    except Exception as e:
        print(f"  ✗ Gagal membaca {shp_path} dengan Geopandas: {e}")
        return None


def detect_layer_style(filename: str, geom_type: str) -> dict:
    fn = filename.lower(); stem = Path(filename).stem

    # ── Label manusiawi berdasarkan stem ─────────────────────────
    LABEL_MAP = {
        "administrasi_desa":    "Administrasi Desa",
        "garis_pantai_selatan": "Garis Pantai Selatan",
        "jalan_bantul":         "Jalan Bantul",
        "koordinat_tes":        "Koordinat TES",
        "tes_bantul":           "TES Bantul",
        "2016_java-faultmodel_v1_2":         "Sesar Jawa (PUSGEN)",
        "ina_megathrust":                    "Megathrust Indonesia",
        "2016-nmaluccufaults-latlong_v1_2":  "Sesar N.Maluku",
        "2016_kalimantanfaultmod_v1_2":      "Sesar Kalimantan",
        "2016_nt-banda-fault_v1.2_simplified": "Sesar NT-Banda",
        "2016_sulawesifaultmod_v1_2":        "Sesar Sulawesi",
        "2016_sum_faultmodel_v1_2":          "Sesar Sumatera",
    }
    label = LABEL_MAP.get(stem.lower(), stem)

    # ── Administrasi wilayah ──────────────────────────────────────
    if any(k in fn for k in ['kecamatan', 'kec_']):
        return {"color":"#ff9900","weight":1.5,"fillOpacity":0.08,"fillColor":"#ff9900","label":"Kecamatan","order":2}
    if any(k in fn for k in ['administrasi_desa','desa','kelurahan','kel_']):
        return {"color":"#ffdd55","weight":1,"fillOpacity":0.07,"fillColor":"#ffdd55","label":"Administrasi Desa","order":3}
    if any(k in fn for k in ['kabupaten','kab_']):
        return {"color":"#ff6600","weight":2.5,"fillOpacity":0.07,"fillColor":"#ff6600","label":"Kabupaten","order":1}
    if any(k in fn for k in ['provinsi','prov_']):
        return {"color":"#ff3300","weight":3,"fillOpacity":0.05,"fillColor":"#ff3300","label":"Provinsi","order":0}

    # ── Hidrologi & infrastruktur ─────────────────────────────────
    if any(k in fn for k in ['sungai','river','hidrologi']):
        return {"color":"#33aaff","weight":1.5,"fillOpacity":0,"fillColor":"transparent","label":"Sungai","order":10}
    if any(k in fn for k in ['jalan','road']):
        return {"color":"#ffe566","weight":1,"fillOpacity":0,"fillColor":"transparent","label":label,"order":11}

    # ── Garis pantai ──────────────────────────────────────────────
    if any(k in fn for k in ['pantai','coast','garis_pantai']):
        return {"color":"#00d4ff","weight":2,"fillOpacity":0,"fillColor":"transparent","label":label,"order":5}

    # ── TES / Titik Evakuasi ──────────────────────────────────────
    if any(k in fn for k in ['tes_','tes_bantul','koordinat_tes','evakuasi']):
        return {"color":"#00ff88","weight":2,"fillOpacity":0.9,"fillColor":"#00ff88","label":label,"order":4}

    # ── Sesar / Fault (PUSGEN) ────────────────────────────────────
    if any(k in fn for k in ['sesar','fault','pusgen','megathrust','java-fault',
                              'sumatera','sulawesi','kalimantan','maluku','nt-banda']):
        return {"color":"#ff4444","weight":1.5,"fillOpacity":0,"fillColor":"transparent","label":label,"order":6}

    # ── Default berdasarkan geometri ──────────────────────────────
    defaults = {
        "Polygon":         {"color":"#cc88ff","weight":1.5,"fillOpacity":0.08,"fillColor":"#cc88ff","label":label,"order":99},
        "MultiPolygon":    {"color":"#cc88ff","weight":1.5,"fillOpacity":0.08,"fillColor":"#cc88ff","label":label,"order":99},
        "LineString":      {"color":"#aaaacc","weight":1.5,"fillOpacity":0,"fillColor":"transparent","label":label,"order":99},
        "MultiLineString": {"color":"#aaaacc","weight":1.5,"fillOpacity":0,"fillColor":"transparent","label":label,"order":99},
        "Point":           {"color":"#ffffff","weight":1,"fillOpacity":0.85,"fillColor":"#ffffff","label":label,"order":99},
    }
    return defaults.get(geom_type, defaults["Polygon"])


OSM_MANNING_MAP: dict = {
    # Permukiman / Lahan Terbangun
    "residential" : 0.045,
    "commercial"  : 0.045,
    "industrial"  : 0.045,
    "retail"      : 0.045,
    "cemetery"    : 0.045,
    # Hutan
    "forest"      : 0.070,
    "wood"        : 0.070,
    # Belukar / Semak
    "scrub"       : 0.040,
    "heath"       : 0.040,
    # Kebun / Perkebunan
    "orchard"     : 0.035,
    "vineyard"    : 0.035,
    # Lahan Pertanian
    "farmland"    : 0.025,
    "farmyard"    : 0.025,
    "meadow"      : 0.025,
    "grass"       : 0.025,
    "village_green": 0.025,
    "allotments"  : 0.025,
    # Mangrove
    "wetland"     : 0.025,
    # Lahan Kosong / Terbuka
    "brownfield"  : 0.015,
    "sand"        : 0.015,
    "beach"       : 0.015,
    "bare_rock"   : 0.015,
    # Tambak / Empang
    "salt_pond"   : 0.010,
    "aquaculture" : 0.010,
    # Badan Air
    "water"       : 0.007,
    "river"       : 0.007,
    "basin"       : 0.007,
    "reservoir"   : 0.007,
}


def build_roughness_grid(
    ny: int,
    nx: int,
    lat_arr: np.ndarray,
    lon_arr: np.ndarray,
    osm_data: dict,
) -> np.ndarray:
    """
    Rasterisasi poligon landuse dari data OSM ke dalam grid Manning's n
    berukuran (ny × nx). Dipakai oleh SWE solver untuk memperhitungkan
    gesekan dasar per tutupan lahan.

    Dipindahkan dari server.py (_build_roughness_grid_sync).

    Parameters
    ----------
    ny, nx   : int          — dimensi grid (baris, kolom)
    lat_arr  : np.ndarray   — array lintang (panjang ny)
    lon_arr  : np.ndarray   — array bujur   (panjang nx)
    osm_data : dict         — hasil fetch_osm_landuse (kunci "features")

    Returns
    -------
    np.ndarray shape (ny, nx) — nilai Manning's n per sel grid
    """
    grid = np.full((ny, nx), 0.025)           # default: lautan/permukaan halus
    if not osm_data or "features" not in osm_data:
        return grid

    try:
        from shapely.geometry import Point, Polygon
        from shapely.prepared import prep

        features = osm_data["features"]
        print(f"    Rasterizing {len(features)} landuse features into roughness grid...")

        # Fitur dengan n lebih kasar menimpa yang lebih halus (urut ascending)
        sorted_features = sorted(features, key=lambda x: x["n"])

        dx = float(lon_arr[1] - lon_arr[0]) if len(lon_arr) > 1 else 0.001
        dy = float(lat_arr[1] - lat_arr[0]) if len(lat_arr) > 1 else 0.001

        for feat in sorted_features:
            coords  = feat["coords"]
            n_val   = feat["n"]
            poly    = Polygon([(lon, lat) for lat, lon in coords])
            prep_poly = prep(poly)

            b     = poly.bounds   # (minx, miny, maxx, maxy)
            i_min = max(0,    int((b[0] - lon_arr[0]) / dx))
            i_max = min(nx-1, int((b[2] - lon_arr[0]) / dx) + 1)
            j_min = max(0,    int((b[1] - lat_arr[0]) / dy))
            j_max = min(ny-1, int((b[3] - lat_arr[0]) / dy) + 1)

            for j in range(j_min, j_max + 1):
                lat = lat_arr[j]
                for i in range(i_min, i_max + 1):
                    lon = lon_arr[i]
                    if prep_poly.contains(Point(lon, lat)):
                        grid[j, i] = n_val

        print(f"    Roughness grid siap (n_mean={np.mean(grid):.4f})")
    except Exception as e:
        print(f"    Gagal rasterisasi landuse: {e}")

    return grid


# ═══════════════════════════════════════════════════════════════════════════
# GRAPH ROUTING — JARINGAN JALAN UNTUK EVAKUASI
# ═══════════════════════════════════════════════════════════════════════════

def build_road_graph(roads: list, dem_mgr=None) -> dict:
    """
    Bangun adjacency graph dari daftar jalan OSM (hasil fetch_osm_roads atau
    cache shapefile lokal). Dipakai oleh modul evakuasi ABM (Dijkstra/A*).

    Dipindahkan dari server.py (build_graph).

    Node  : (lat, lon, elev_m)
    Edge  : (neighbor_idx, dist_m, time_min, highway, capacity,
             composite_cost, slope_pct, src_elev)

    composite_cost = w_dist*dist_norm + w_time*time_norm
                   + w_elev*elev_pen + w_slope*slope_pen

    Penalti elevasi rendah mendorong Dijkstra memilih rute naik ke
    elevasi lebih aman (menjauhi zona inundasi).

    Parameters
    ----------
    roads   : list  — daftar dict jalan (highway, coords, speed_kmh, capacity, oneway)
    dem_mgr : DEMManager | None — opsional, untuk bobot elevasi per node

    Returns
    -------
    dict — {"nodes": [(lat, lon, elev), ...], "edges": {idx: [edge, ...]}}
    """
    W_DIST  = 0.30
    W_TIME  = 0.30
    W_ELEV  = 0.25
    W_SLOPE = 0.15

    ELEV_DANGER_MAX = 20.0
    SLOPE_MAX_PCT   = 40.0

    nodes_list: list  = []
    nodes_idx:  dict  = {}

    def _get_or_add(lat, lon):
        key = (round(lat, 5), round(lon, 5))
        if key not in nodes_idx:
            elev = 0.0
            if dem_mgr:
                e, _ = dem_mgr.query(lon, lat)
                if e is not None:
                    elev = float(e)
            nodes_idx[key] = len(nodes_list)
            nodes_list.append((lat, lon, elev))
        return nodes_idx[key]

    edges: dict = {}

    for road in roads:
        coords = road["coords"]
        speed  = road.get("speed_kmh", 20)
        hw     = road.get("highway", "residential")
        cap    = road.get("capacity", 1000)
        oneway = road.get("oneway", "no") in ("yes", "true", "1")

        prev_idx = None
        for lat, lon in coords:
            idx = _get_or_add(lat, lon)
            if prev_idx is not None:
                plat, plon, pelev = nodes_list[prev_idx]
                clat, clon, celev = nodes_list[idx]
                dist  = haversine_m(plat, plon, clat, clon)
                t_min = (dist / 1000) / speed * 60 if speed > 0 else 999

                slope_pct  = (abs(celev - pelev) / dist * 100.0) if dist > 0 else 0.0
                elev_pen   = max(0.0, min(1.0, 1.0 - pelev / ELEV_DANGER_MAX))
                slope_pen  = min(1.0, slope_pct / SLOPE_MAX_PCT)
                dist_norm  = (dist / 1000) / 10.0
                time_norm  = t_min / 60.0
                composite  = (W_DIST  * dist_norm +
                              W_TIME  * time_norm  +
                              W_ELEV  * elev_pen   +
                              W_SLOPE * slope_pen)

                edges.setdefault(prev_idx, []).append(
                    (idx, dist, t_min, hw, cap, composite, slope_pct, pelev)
                )
                if not oneway:
                    elev_pen2   = max(0.0, min(1.0, 1.0 - celev / ELEV_DANGER_MAX))
                    composite2  = (W_DIST  * dist_norm +
                                   W_TIME  * time_norm  +
                                   W_ELEV  * elev_pen2  +
                                   W_SLOPE * slope_pen)
                    edges.setdefault(idx, []).append(
                        (prev_idx, dist, t_min, hw, cap, composite2, slope_pct, celev)
                    )
            prev_idx = idx

    return {"nodes": nodes_list, "edges": edges}


def nearest_node(nodes_list: list, lat: float, lon: float) -> tuple:
    """
    Temukan node terdekat dalam graph road dari posisi (lat, lon).
    Dipindahkan dari server.py.

    Parameters
    ----------
    nodes_list : list — daftar (lat, lon) atau (lat, lon, elev)
    lat, lon   : float — posisi query (derajat)

    Returns
    -------
    (idx: int, distance_m: float)
    """
    best_idx, best_d = 0, 1e18
    for i, node in enumerate(nodes_list):
        nlat, nlon = node[0], node[1]
        d = haversine_m(lat, lon, nlat, nlon)
        if d < best_d:
            best_d, best_idx = d, i
    return best_idx, best_d


def dijkstra(graph: dict, start_idx: int, end_idx: int,
             weight: str = "composite") -> tuple:
    """
    Cari jalur terpendek antara dua node menggunakan algoritma Dijkstra.
    Dipindahkan dari server.py.

    Parameters
    ----------
    graph     : dict — output build_road_graph (kunci "nodes" dan "edges")
    start_idx : int  — indeks node awal
    end_idx   : int  — indeks node tujuan
    weight    : str  — "composite" | "time" | "distance"

    Returns
    -------
    (cost: float, path: [(lat, lon), ...])
    cost = None dan path = [] jika tidak ada rute.
    """
    import heapq
    nodes = graph["nodes"]
    edges = graph["edges"]
    dist  = {start_idx: 0.0}
    prev  : dict = {}
    pq    = [(0.0, start_idx)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        if u == end_idx:
            break
        for edge in edges.get(u, []):
            v, dist_m, t_min = edge[0], edge[1], edge[2]
            comp = edge[5] if len(edge) > 5 else t_min / 60.0
            w    = t_min if weight == "time" else (dist_m / 1000 if weight == "distance" else comp)
            nd   = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    if end_idx not in prev and end_idx != start_idx:
        return None, []

    path, cur = [], end_idx
    while cur in prev:
        path.append(cur)
        cur = prev[cur]
    path.append(start_idx)
    path.reverse()
    return dist.get(end_idx, 1e18), [(nodes[i][0], nodes[i][1]) for i in path]


def astar(graph: dict, start_idx: int, end_idx: int,
          weight: str = "composite", transport_speed_kmh: float = 30.0) -> tuple:
    """
    Cari jalur terpendek menggunakan algoritma A* dengan heuristik Haversine.
    Lebih cepat dari Dijkstra untuk graph besar.
    Dipindahkan dari server.py.

    Parameters
    ----------
    graph               : dict  — output build_road_graph
    start_idx           : int   — indeks node awal
    end_idx             : int   — indeks node tujuan
    weight              : str   — "composite" | "time" | "distance"
    transport_speed_kmh : float — kecepatan asumsi untuk heuristik waktu (km/jam)

    Returns
    -------
    (cost: float, path: [(lat, lon), ...])
    """
    import heapq
    nodes = graph["nodes"]
    edges = graph["edges"]
    elat, elon = nodes[end_idx][0], nodes[end_idx][1]

    def _heuristic(idx: int) -> float:
        lat, lon = nodes[idx][0], nodes[idx][1]
        d = haversine_m(lat, lon, elat, elon)
        if weight == "time":
            return (d / 1000) / transport_speed_kmh * 60
        elif weight == "distance":
            return d / 1000
        else:
            return (d / 1000) / transport_speed_kmh

    g    = {start_idx: 0.0}
    prev : dict = {}
    pq   = [(_heuristic(start_idx), 0.0, start_idx)]

    while pq:
        _, gn, u = heapq.heappop(pq)
        if u == end_idx:
            break
        if gn > g.get(u, 1e18):
            continue
        for edge in edges.get(u, []):
            v, dist_m, t_min = edge[0], edge[1], edge[2]
            comp = edge[5] if len(edge) > 5 else t_min / 60.0
            w    = t_min if weight == "time" else (dist_m / 1000 if weight == "distance" else comp)
            ng   = gn + w
            if ng < g.get(v, 1e18):
                g[v]    = ng
                prev[v] = u
                heapq.heappush(pq, (ng + _heuristic(v), ng, v))

    if end_idx not in prev and end_idx != start_idx:
        return None, []

    path, cur = [], end_idx
    while cur in prev:
        path.append(cur)
        cur = prev[cur]
    path.append(start_idx)
    path.reverse()
    return g.get(end_idx, 1e18), [(nodes[i][0], nodes[i][1]) for i in path]
